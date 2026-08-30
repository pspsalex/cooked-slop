#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Recipe Deduplication Tool
=========================
Ingests schema.org JSON-LD recipes into SQLite and identifies duplicates
using two complementary signals:

  1. Exact-match via SHA-256 content hash  (identical recipes)
  2. Exact-match via SHA-256 ingredient hash (same ingredients, any instructions)
  3. Fuzzy-match via MinHash / LSH          (near-duplicate recipes)

Two MinHash signatures are stored per recipe:
  - combined : ingredient tokens + instruction text  → overall similarity
  - ingredient: ingredient tokens only               → ingredient-only similarity

Usage (typical workflow for 600 K recipes):

    # 1. Ingest — skip files already seen, safe to re-run
    find output/ -name "*.json" | python dedup.py ingest --stdin
    # or: python dedup.py ingest output/recipe1.json output/recipe2.json ...

    # 2. Quick exact stats
    python dedup.py stats

    # 3. Exact and ingredient-only duplicates (no extra deps needed)
    python dedup.py exact-dupes
    python dedup.py ingredient-dupes

    # 4. Build fuzzy pairs (run once; stores results in DB)
    python dedup.py build-pairs --threshold 0.80

    # 5. Inspect fuzzy matches
    python dedup.py fuzzy-dupes --threshold 0.80

    # 6. Cluster everything into groups (transitive closure)
    python dedup.py build-groups --threshold 0.80

    # 7. Browse / manage clusters
    python dedup.py show-groups --min-size 2
    python dedup.py set-canonical <id>

    # 8. Export one recipe per cluster
    python dedup.py export-unique --out unique_recipes.json

    # 9. Ad-hoc comparison
    python dedup.py compare <id1> <id2>
    python dedup.py sql-examples

Dependencies (stdlib + optional):
    pip install datasketch unidecode   # enables fuzzy matching
"""

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------

try:
    from datasketch import MinHash, MinHashLSH
    import numpy as np
    HAVE_MINHASH = True
except ImportError:
    HAVE_MINHASH = False
    print(
        "WARNING: 'datasketch' not installed — fuzzy matching disabled.\n"
        "         Install with:  pip install datasketch\n",
        file=sys.stderr,
    )

try:
    from unidecode import unidecode as _unidecode
except ImportError:
    def _unidecode(s: str) -> str:  # type: ignore[misc]
        return s.encode("ascii", "ignore").decode()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB = "recipes_dedup.db"
MINHASH_PERMS = 128
DEFAULT_THRESHOLD = 0.80

# Measurement units — stripped from ingredient text before tokenising
_UNITS: frozenset[str] = frozenset({
    "cup", "cups", "tbsp", "tsp", "tablespoon", "tablespoons",
    "teaspoon", "teaspoons", "pound", "pounds", "lb", "lbs",
    "oz", "ounce", "ounces", "gram", "grams", "kg",
    "ml", "milliliter", "milliliters", "liter", "liters",
    "clove", "cloves", "slice", "slices", "bunch", "bunches",
    "head", "heads", "can", "cans", "pkg", "package", "packages",
    "pinch", "dash", "handful", "handfuls", "sprig", "sprigs",
    "stalk", "stalks", "piece", "pieces", "stick", "sticks",
    "quart", "quarts", "pint", "pints",
})

# Cooking adjectives that add noise without identifying the ingredient
_COOKING_ADJ: frozenset[str] = frozenset({
    "fresh", "dried", "chopped", "minced", "diced", "sliced",
    "grated", "peeled", "cooked", "raw", "frozen", "thawed",
    "softened", "melted", "shredded", "ground", "whole",
    "large", "medium", "small", "heaping", "level",
    "extra", "about", "approximately",
})

_STOPWORDS: frozenset[str] = frozenset({
    "and", "or", "the", "a", "an", "to", "of", "with",
    "in", "for", "on", "at", "by", "as", "is", "it",
}) | _UNITS | _COOKING_ADJ

# ---------------------------------------------------------------------------
# DB schema
# ---------------------------------------------------------------------------

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS recipes (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT,
    source_file            TEXT NOT NULL,
    content_hash           TEXT NOT NULL,
    ingredient_hash        TEXT NOT NULL,
    minhash_hex            TEXT,
    ingredient_minhash_hex TEXT,
    ingredient_count       INTEGER,
    total_time             TEXT,
    recipe_yield           TEXT,
    raw_json               TEXT NOT NULL,
    ingredient_tokens      TEXT,
    instruction_text       TEXT,
    ingested_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uidx_source_file ON recipes(source_file);
CREATE        INDEX IF NOT EXISTS idx_content_hash ON recipes(content_hash);
CREATE        INDEX IF NOT EXISTS idx_ing_hash     ON recipes(ingredient_hash);
CREATE        INDEX IF NOT EXISTS idx_name         ON recipes(name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS dup_pairs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id_1   INTEGER NOT NULL REFERENCES recipes(id),
    recipe_id_2   INTEGER NOT NULL REFERENCES recipes(id),
    similarity    REAL    NOT NULL,
    ing_similarity REAL,
    match_type    TEXT    NOT NULL DEFAULT 'fuzzy',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(recipe_id_1, recipe_id_2)
);

CREATE INDEX IF NOT EXISTS idx_pairs_r1  ON dup_pairs(recipe_id_1);
CREATE INDEX IF NOT EXISTS idx_pairs_r2  ON dup_pairs(recipe_id_2);
CREATE INDEX IF NOT EXISTS idx_pairs_sim ON dup_pairs(similarity);

CREATE TABLE IF NOT EXISTS dup_groups (
    group_id     INTEGER NOT NULL,
    recipe_id    INTEGER NOT NULL REFERENCES recipes(id),
    is_canonical INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, recipe_id)
);

CREATE INDEX IF NOT EXISTS idx_groups_recipe ON dup_groups(recipe_id);
CREATE INDEX IF NOT EXISTS idx_groups_group  ON dup_groups(group_id);
"""


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

# Strip leading numeric quantities / fractions before tokenising
_QUANTITY_RE = re.compile(
    r"""^[\s]*
        (?:\d[\d\s]*/\s*\d+\s*)?   # optional fraction like 1/2 or 1 1/2
        (?:\d+[\.,]?\d*\s*)?        # optional integer / decimal
        (?:to\s+\d+\s*)?            # optional range "2 to 3"
    """,
    re.VERBOSE,
)


def _extract_ingredient_text(ing: Any) -> str:
    """Return a plain text representation of a single ingredient entry.

    Handles both bare strings and schema.org PropertyValue dicts
    (``{"@type": "PropertyValue", "name": "flour", "value": 2, "unitText": "cups"}``).
    """
    if isinstance(ing, dict):
        name = ing.get("name", "")
        unit = ing.get("unitText", "")
        value = str(ing.get("value", ""))
        return f"{value} {unit} {name}".strip()
    return str(ing)


def _ingredient_words(raw: str) -> list[str]:
    """Return content-bearing word tokens from one raw ingredient string.

    Pipeline:
      1. Transliterate to ASCII
      2. Lowercase
      3. Strip leading quantity / fraction
      4. Keep only [a-z ] characters
      5. Split on whitespace
      6. Drop tokens shorter than 3 characters
      7. Drop stopwords / unit words / cooking adjectives
    """
    text = _unidecode(raw).lower()
    text = _QUANTITY_RE.sub("", text, count=1)
    text = re.sub(r"[^a-z ]", " ", text)
    return [w for w in text.split() if len(w) >= 3 and w not in _STOPWORDS]


def _normalize_instructions(recipe: dict) -> str:
    """Flatten and normalise recipeInstructions to a single ASCII string."""
    inst = recipe.get("recipeInstructions", "")
    parts: list[str] = []
    if isinstance(inst, str):
        parts = [inst]
    elif isinstance(inst, list):
        for item in inst:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", item.get("name", "")))
    text = _unidecode(" ".join(parts)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _ingredient_tokens(recipe: dict) -> list[str]:
    """Return sorted, deduplicated content words from all ingredients."""
    words: set[str] = set()
    for ing in recipe.get("recipeIngredient", []):
        words.update(_ingredient_words(_extract_ingredient_text(ing)))
    return sorted(words)


def _content_hash(recipe: dict) -> str:
    """SHA-256 fingerprint of normalised ingredients + instructions + yield.

    Uses per-ingredient normalized strings (preserving ingredient boundaries),
    which differs from _ingredient_tokens (global dedup). Intentionally
    excludes: name, URL, dates, source metadata.
    """
    ings = sorted(
        " ".join(_ingredient_words(_extract_ingredient_text(i)))
        for i in recipe.get("recipeIngredient", [])
    )
    payload = json.dumps(
        {
            "ingredients": ings,
            "instructions": _normalize_instructions(recipe),
            "yield": re.sub(r"\s+", " ", str(recipe.get("recipeYield", ""))).strip().lower(),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _ingredient_hash(tokens: list[str]) -> str:
    """SHA-256 fingerprint of pre-computed ingredient tokens (no instructions).

    Two recipes that differ only in instruction wording will share this hash.
    Pass the result of _ingredient_tokens(recipe) as the argument.
    """
    return hashlib.sha256(" ".join(tokens).encode()).hexdigest()


# ---------------------------------------------------------------------------
# MinHash helpers
# ---------------------------------------------------------------------------

def _shingles(text: str, k: int = 3) -> set[str]:
    return {text[i : i + k] for i in range(len(text) - k + 1)} if len(text) >= k else set()


def _build_minhash(token_string: str) -> "MinHash | None":
    if not HAVE_MINHASH:
        return None
    m = MinHash(num_perm=MINHASH_PERMS)
    for sh in _shingles(token_string):
        m.update(sh.encode("utf8"))
    return m


def _minhash_to_hex(m: "MinHash") -> str:
    return m.hashvalues.tobytes().hex()


def _minhash_from_hex(h: str) -> "MinHash | None":
    if not HAVE_MINHASH or not h:
        return None
    m = MinHash(num_perm=MINHASH_PERMS)
    m.hashvalues = np.frombuffer(bytes.fromhex(h), dtype=np.uint64).copy()
    return m


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def _load_recipes(path: str) -> list[dict]:
    """Load schema.org Recipe dicts from a JSON / JSON-LD file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [i for i in data if isinstance(i, dict)]
    if isinstance(data, dict):
        if "@graph" in data:
            return [i for i in data["@graph"] if isinstance(i, dict)]
        return [data]
    return []


# ---------------------------------------------------------------------------
# Shared display helper
# ---------------------------------------------------------------------------

def _print_header(title: str) -> None:
    sep = "=" * 70
    print(f"\n{sep}\n{title}\n{sep}")


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------

def cmd_ingest(args: argparse.Namespace) -> None:
    """Ingest recipe JSON files into the database (idempotent)."""
    conn = _get_conn(args.db)
    new_count = skip_count = err_count = 0

    if args.stdin:
        paths: list[Path] = [Path(line.strip()) for line in sys.stdin if line.strip()]
    else:
        paths = [Path(p) for p in args.files]

    total = len(paths)
    for i, path in enumerate(paths, 1):
        if i % 5000 == 0:
            print(f"  {i:,}/{total:,} files — {new_count:,} new", file=sys.stderr)

        try:
            recipes = _load_recipes(str(path))
        except Exception as exc:
            print(f"  ERROR {path}: {exc}", file=sys.stderr)
            err_count += 1
            continue

        for recipe in recipes:
            src = str(path)
            chash = _content_hash(recipe)
            tokens = _ingredient_tokens(recipe)
            tok_str = " ".join(tokens)
            ihash = _ingredient_hash(tokens)
            instr = _normalize_instructions(recipe)

            mh_combined = _build_minhash(tok_str + " " + instr)
            mh_ing = _build_minhash(tok_str)

            conn.execute(
                """
                INSERT OR IGNORE INTO recipes
                    (name, source_file, content_hash, ingredient_hash,
                     minhash_hex, ingredient_minhash_hex,
                     ingredient_count, total_time, recipe_yield,
                     raw_json, ingredient_tokens, instruction_text)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    recipe.get("name", ""),
                    src,
                    chash,
                    ihash,
                    _minhash_to_hex(mh_combined) if mh_combined else None,
                    _minhash_to_hex(mh_ing) if mh_ing else None,
                    len(recipe.get("recipeIngredient", [])),
                    str(recipe.get("totalTime", recipe.get("cookTime", ""))),
                    str(recipe.get("recipeYield", "")),
                    json.dumps(recipe, ensure_ascii=False),
                    tok_str,
                    instr[:4000],
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                new_count += 1
            else:
                skip_count += 1

        if i % 1000 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    print(f"Ingest done: {new_count:,} new, {skip_count:,} skipped, {err_count:,} errors.")


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def cmd_stats(args: argparse.Namespace) -> None:
    conn = _get_conn(args.db)
    total = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    exact_grps = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT 1 FROM recipes GROUP BY content_hash HAVING COUNT(*)>1"
        ")"
    ).fetchone()[0]
    ing_grps = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT 1 FROM recipes GROUP BY ingredient_hash HAVING COUNT(*)>1"
        ")"
    ).fetchone()[0]
    pairs = conn.execute("SELECT COUNT(*) FROM dup_pairs").fetchone()[0]
    clusters = conn.execute(
        "SELECT COUNT(DISTINCT group_id) FROM dup_groups "
        "WHERE group_id IN ("
        "  SELECT group_id FROM dup_groups GROUP BY group_id HAVING COUNT(*)>1"
        ")"
    ).fetchone()[0]
    conn.close()
    print(f"Recipes ingested      : {total:,}")
    print(f"Exact dup groups      : {exact_grps:,}  (same content_hash)")
    print(f"Ingredient dup groups : {ing_grps:,}  (same ingredient_hash)")
    print(f"Fuzzy pairs stored    : {pairs:,}  (run build-pairs to populate)")
    print(f"Clusters built        : {clusters:,}  (run build-groups to populate)")


# ---------------------------------------------------------------------------
# exact-dupes
# ---------------------------------------------------------------------------

def cmd_exact_dupes(args: argparse.Namespace) -> None:
    conn = _get_conn(args.db)
    rows = conn.execute(
        """
        SELECT content_hash, COUNT(*) cnt,
               GROUP_CONCAT(id, ',') ids,
               GROUP_CONCAT(name, ' | ') names,
               GROUP_CONCAT(source_file, ' | ') files
        FROM recipes
        GROUP BY content_hash HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    conn.close()
    if not rows:
        print("No exact duplicates found.")
        return
    _print_header(f"EXACT DUPLICATES ({len(rows)} groups)")
    for row in rows:
        print(f"\nHash: {row['content_hash'][:16]}…  [{row['cnt']} copies]")
        print(f"  IDs   : {row['ids']}")
        print(f"  Names : {(row['names'] or '')[:120]}")
        print(f"  Files : {(row['files'] or '')[:120]}")


# ---------------------------------------------------------------------------
# ingredient-dupes
# ---------------------------------------------------------------------------

def cmd_ingredient_dupes(args: argparse.Namespace) -> None:
    """Show recipes that share identical ingredients but may differ in instructions."""
    conn = _get_conn(args.db)
    rows = conn.execute(
        """
        SELECT ingredient_hash, COUNT(*) cnt,
               GROUP_CONCAT(id, ',') ids,
               GROUP_CONCAT(name, ' | ') names
        FROM recipes
        GROUP BY ingredient_hash HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    conn.close()
    if not rows:
        print("No ingredient-only duplicates found.")
        return
    _print_header(f"INGREDIENT DUPLICATES ({len(rows)} groups)")
    for row in rows:
        print(f"\nIngHash: {row['ingredient_hash'][:16]}…  [{row['cnt']} copies]")
        print(f"  IDs   : {row['ids']}")
        print(f"  Names : {(row['names'] or '')[:120]}")


# ---------------------------------------------------------------------------
# build-pairs  (the expensive step — run once)
# ---------------------------------------------------------------------------

def cmd_build_pairs(args: argparse.Namespace) -> None:
    """Compute MinHash LSH near-duplicate pairs and persist them to dup_pairs."""
    if not HAVE_MINHASH:
        print("ERROR: datasketch not installed. Cannot run fuzzy matching.", file=sys.stderr)
        sys.exit(1)

    conn = _get_conn(args.db)
    threshold = args.threshold

    print(f"Loading signatures (threshold={threshold:.0%})…", file=sys.stderr)
    rows = conn.execute(
        "SELECT id, minhash_hex, ingredient_minhash_hex FROM recipes "
        "WHERE minhash_hex IS NOT NULL"
    ).fetchall()

    if not rows:
        print("No recipes with MinHash signatures. Did you run ingest?")
        conn.close()
        return

    lsh = MinHashLSH(threshold=threshold, num_perm=MINHASH_PERMS)
    mh_combined: dict[int, Any] = {}
    mh_ing: dict[int, Any] = {}

    print(f"Building LSH index for {len(rows):,} recipes…", file=sys.stderr)
    for i, row in enumerate(rows, 1):
        if i % 20000 == 0:
            print(f"  indexed {i:,}/{len(rows):,}", file=sys.stderr)
        rid = row["id"]
        mhc = _minhash_from_hex(row["minhash_hex"])
        mhi = _minhash_from_hex(row["ingredient_minhash_hex"])
        if mhc:
            lsh.insert(f"r{rid}", mhc)
            mh_combined[rid] = mhc
        if mhi:
            mh_ing[rid] = mhi

    print("Querying for near-duplicate pairs…", file=sys.stderr)
    inserted = 0

    for i, row in enumerate(rows, 1):
        if i % 20000 == 0:
            print(f"  {i:,}/{len(rows):,} queried, {inserted:,} pairs found", file=sys.stderr)

        rid = row["id"]
        mhc = mh_combined.get(rid)
        if not mhc:
            continue

        for nkey in lsh.query(mhc):
            nid = int(nkey[1:])
            if nid <= rid:
                continue

            sim = mhc.jaccard(mh_combined[nid]) if nid in mh_combined else 0.0
            mhi_r = mh_ing.get(rid)
            ing_sim: float | None = (
                mhi_r.jaccard(mh_ing[nid]) if (mhi_r and nid in mh_ing) else None
            )
            conn.execute(
                "INSERT OR IGNORE INTO dup_pairs "
                "  (recipe_id_1, recipe_id_2, similarity, ing_similarity, match_type) "
                "VALUES (?,?,?,?,'fuzzy')",
                (rid, nid, sim, ing_sim),
            )
            inserted += 1

        if i % 10000 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    print(f"build-pairs complete: {inserted:,} pairs stored.", file=sys.stderr)


# ---------------------------------------------------------------------------
# fuzzy-dupes  (reads from dup_pairs; run build-pairs first)
# ---------------------------------------------------------------------------

def cmd_fuzzy_dupes(args: argparse.Namespace) -> None:
    conn = _get_conn(args.db)
    rows = conn.execute(
        """
        SELECT p.recipe_id_1, p.recipe_id_2, p.similarity, p.ing_similarity,
               r1.name name1, r1.source_file file1,
               r2.name name2, r2.source_file file2
        FROM dup_pairs p
        JOIN recipes r1 ON r1.id = p.recipe_id_1
        JOIN recipes r2 ON r2.id = p.recipe_id_2
        WHERE p.similarity >= ?
        ORDER BY p.similarity DESC
        LIMIT ?
        """,
        (args.threshold, args.limit),
    ).fetchall()
    conn.close()
    if not rows:
        print(
            f"No fuzzy pairs at threshold {args.threshold:.0%}. "
            "Did you run build-pairs?"
        )
        return
    _print_header(f"FUZZY DUPLICATES (threshold={args.threshold:.0%}, {len(rows)} shown)")
    for row in rows:
        ing_s = f"{row['ing_similarity']:.1%}" if row["ing_similarity"] is not None else "N/A"
        print(
            f"\n  Combined: {row['similarity']:.1%}  Ingredients: {ing_s}"
            f"\n  [{row['recipe_id_1']}] {row['name1']}  ({row['file1']})"
            f"\n  [{row['recipe_id_2']}] {row['name2']}  ({row['file2']})"
        )


# ---------------------------------------------------------------------------
# build-groups  (union-find clustering over all pair types)
# ---------------------------------------------------------------------------

class _UnionFind:
    """Path-compressed union-find for transitive closure of duplicate pairs."""

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        if x not in self._parent:
            self._parent[x] = x
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]  # path compression
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


def _union_concat(uf: _UnionFind, conn: sqlite3.Connection, query: str, params: tuple = ()) -> None:
    """Union all id-lists returned by a GROUP_CONCAT query."""
    for row in conn.execute(query, params):
        ids = list(map(int, row[0].split(",")))
        for x in ids[1:]:
            uf.union(ids[0], x)


def cmd_build_groups(args: argparse.Namespace) -> None:
    """Cluster all duplicate signals (exact, ingredient, fuzzy) into groups."""
    conn = _get_conn(args.db)
    uf = _UnionFind()

    # Exact content-hash pairs
    _union_concat(
        uf, conn,
        "SELECT GROUP_CONCAT(id) FROM recipes GROUP BY content_hash HAVING COUNT(*)>1",
    )
    # Ingredient-hash pairs
    _union_concat(
        uf, conn,
        "SELECT GROUP_CONCAT(id) FROM recipes GROUP BY ingredient_hash HAVING COUNT(*)>1",
    )
    # Fuzzy pairs above threshold
    for row in conn.execute(
        "SELECT recipe_id_1, recipe_id_2 FROM dup_pairs WHERE similarity >= ?",
        (args.threshold,),
    ):
        uf.union(row[0], row[1])

    # Fetch all recipe IDs once; reuse for both root mapping and group insertion
    recipe_ids = [row[0] for row in conn.execute("SELECT id FROM recipes ORDER BY id")]

    root_to_gid: dict[int, int] = {}
    gid_seq = 1
    for rid in recipe_ids:
        root = uf.find(rid)
        if root not in root_to_gid:
            root_to_gid[root] = gid_seq
            gid_seq += 1

    conn.execute("DELETE FROM dup_groups")
    conn.executemany(
        "INSERT INTO dup_groups (group_id, recipe_id, is_canonical) VALUES (?,?,0)",
        ((root_to_gid[uf.find(rid)], rid) for rid in recipe_ids),
    )

    # Auto-canonicalise: lowest id per group
    conn.execute(
        "UPDATE dup_groups SET is_canonical=1 "
        "WHERE recipe_id IN (SELECT MIN(recipe_id) FROM dup_groups GROUP BY group_id)"
    )

    conn.commit()
    dup_clusters = conn.execute(
        "SELECT COUNT(DISTINCT group_id) FROM dup_groups "
        "WHERE group_id IN (SELECT group_id FROM dup_groups GROUP BY group_id HAVING COUNT(*)>1)"
    ).fetchone()[0]
    conn.close()
    print(f"Groups built. {dup_clusters:,} duplicate clusters (size ≥ 2).")


# ---------------------------------------------------------------------------
# show-groups
# ---------------------------------------------------------------------------

def cmd_show_groups(args: argparse.Namespace) -> None:
    conn = _get_conn(args.db)
    groups = conn.execute(
        """
        SELECT group_id, COUNT(*) cnt
        FROM dup_groups
        GROUP BY group_id HAVING cnt >= ?
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (args.min_size, args.limit),
    ).fetchall()
    if not groups:
        print(f"No groups with size >= {args.min_size}. Did you run build-groups?")
        conn.close()
        return
    _print_header(f"DUPLICATE GROUPS (size>={args.min_size}, {len(groups)} shown)")
    for grp in groups:
        members = conn.execute(
            """
            SELECT r.id, r.name, r.source_file, g.is_canonical
            FROM dup_groups g
            JOIN recipes r ON r.id = g.recipe_id
            WHERE g.group_id = ?
            ORDER BY g.is_canonical DESC, r.id
            """,
            (grp["group_id"],),
        ).fetchall()
        print(f"\n  Group {grp['group_id']}  ({grp['cnt']} recipes)")
        for m in members:
            canon = " [canonical]" if m["is_canonical"] else ""
            print(f"    [{m['id']:>6}] {(m['name'] or '')[:40]:<40}  {m['source_file']}{canon}")
    conn.close()


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

def cmd_compare(args: argparse.Namespace) -> None:
    conn = _get_conn(args.db)
    r1 = conn.execute("SELECT * FROM recipes WHERE id=?", (args.id1,)).fetchone()
    r2 = conn.execute("SELECT * FROM recipes WHERE id=?", (args.id2,)).fetchone()
    conn.close()
    if not r1 or not r2:
        print("One or both IDs not found.")
        return

    exact = r1["content_hash"] == r2["content_hash"]
    ing_exact = r1["ingredient_hash"] == r2["ingredient_hash"]

    t1 = set(r1["ingredient_tokens"].split()) if r1["ingredient_tokens"] else set()
    t2 = set(r2["ingredient_tokens"].split()) if r2["ingredient_tokens"] else set()
    tok_j = len(t1 & t2) / len(t1 | t2) if (t1 | t2) else 0.0

    mh_j = "N/A (datasketch not installed)"
    if HAVE_MINHASH and r1["minhash_hex"] and r2["minhash_hex"]:
        mh1 = _minhash_from_hex(r1["minhash_hex"])
        mh2 = _minhash_from_hex(r2["minhash_hex"])
        mh_j = f"{mh1.jaccard(mh2):.1%}"

    print(f"\n{'='*70}\nCOMPARE  [{args.id1}] vs [{args.id2}]\n{'='*70}")
    print(f"  [{args.id1}] {r1['name']}  ({r1['source_file']})")
    print(f"  [{args.id2}] {r2['name']}  ({r2['source_file']})")
    print(f"\n  Content hash match     : {'YES' if exact else 'no'}")
    print(f"  Ingredient hash match  : {'YES' if ing_exact else 'no'}")
    print(f"  Ingredient token Jaccard: {tok_j:.1%}")
    print(f"  MinHash Jaccard (comb.): {mh_j}")

    only1, only2, common = t1 - t2, t2 - t1, t1 & t2
    print(f"\n  Shared ({len(common)}): {', '.join(sorted(common)) or '(none)'}")
    print(f"  Only [{args.id1}] ({len(only1)}): {', '.join(sorted(only1)) or '(none)'}")
    print(f"  Only [{args.id2}] ({len(only2)}): {', '.join(sorted(only2)) or '(none)'}")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> None:
    conn = _get_conn(args.db)
    rows = conn.execute(
        "SELECT id, name, ingredient_count, total_time, recipe_yield, source_file, content_hash "
        "FROM recipes ORDER BY id LIMIT ?",
        (args.limit,),
    ).fetchall()
    conn.close()
    print(
        f"\n{'ID':<7} {'Name':<35} {'Ings':<5} {'Time':<12} {'Yield':<8} "
        f"{'Hash':<14} File\n{'-'*110}"
    )
    for r in rows:
        print(
            f"{r['id']:<7} {(r['name'] or '')[:34]:<35} {(r['ingredient_count'] or 0):<5} "
            f"{(r['total_time'] or '')[:11]:<12} {(r['recipe_yield'] or '')[:7]:<8} "
            f"{r['content_hash'][:12]:<14} {r['source_file']}"
        )
    print(f"\n{len(rows)} recipes shown.")


# ---------------------------------------------------------------------------
# set-canonical
# ---------------------------------------------------------------------------

def cmd_set_canonical(args: argparse.Namespace) -> None:
    conn = _get_conn(args.db)
    row = conn.execute(
        "SELECT group_id FROM dup_groups WHERE recipe_id=?", (args.id,)
    ).fetchone()
    if not row:
        print(f"Recipe {args.id} not found in any group. Run build-groups first.")
        conn.close()
        return
    gid = row["group_id"]
    conn.execute("UPDATE dup_groups SET is_canonical=0 WHERE group_id=?", (gid,))
    conn.execute(
        "UPDATE dup_groups SET is_canonical=1 WHERE group_id=? AND recipe_id=?",
        (gid, args.id),
    )
    conn.commit()
    conn.close()
    print(f"Recipe {args.id} set as canonical for group {gid}.")


# ---------------------------------------------------------------------------
# export-unique
# ---------------------------------------------------------------------------

def cmd_export_unique(args: argparse.Namespace) -> None:
    """Export one recipe per duplicate cluster, preferring the canonical member."""
    conn = _get_conn(args.db)
    has_groups = conn.execute("SELECT 1 FROM dup_groups LIMIT 1").fetchone()

    if has_groups:
        cursor = conn.execute(
            "SELECT r.raw_json FROM recipes r "
            "JOIN dup_groups g ON g.recipe_id=r.id AND g.is_canonical=1 "
            "ORDER BY r.id"
        )
        strategy = "group canonical"
    else:
        cursor = conn.execute(
            "SELECT raw_json FROM recipes "
            "WHERE id IN (SELECT MIN(id) FROM recipes GROUP BY content_hash) "
            "ORDER BY id"
        )
        strategy = "content_hash MIN(id)"

    count = 0
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("[\n")
        for row in cursor:
            if count > 0:
                f.write(",\n")
            json.dump(json.loads(row[0]), f, ensure_ascii=False)
            count += 1
        f.write("\n]\n")

    conn.close()
    print(f"Exported {count:,} unique recipes to {args.out}  [{strategy}]")


# ---------------------------------------------------------------------------
# sql-examples
# ---------------------------------------------------------------------------

_SQL_EXAMPLES = """
Useful SQL queries  —  recipes_dedup.db
========================================

-- All exact duplicate groups (most copies first):
SELECT content_hash, COUNT(*) cnt, GROUP_CONCAT(id) ids, GROUP_CONCAT(name, ' | ') names
FROM recipes GROUP BY content_hash HAVING cnt>1 ORDER BY cnt DESC;

-- Same ingredients, different instructions (potential editing variants):
SELECT a.id, b.id, a.name, b.name
FROM recipes a JOIN recipes b
  ON a.ingredient_hash = b.ingredient_hash AND a.id < b.id
WHERE a.content_hash != b.content_hash;

-- Largest duplicate clusters:
SELECT group_id, COUNT(*) cnt FROM dup_groups
GROUP BY group_id ORDER BY cnt DESC LIMIT 20;

-- All members of a specific cluster (replace 42 with actual group_id):
SELECT r.id, r.name, g.is_canonical, r.source_file
FROM dup_groups g JOIN recipes r ON r.id=g.recipe_id
WHERE g.group_id = 42 ORDER BY g.is_canonical DESC, r.id;

-- Pairs with high ingredient similarity but very different combined similarity
-- (same ingredients, drastically different instructions — interesting variants):
SELECT p.recipe_id_1, p.recipe_id_2, p.similarity, p.ing_similarity, r1.name, r2.name
FROM dup_pairs p
JOIN recipes r1 ON r1.id=p.recipe_id_1
JOIN recipes r2 ON r2.id=p.recipe_id_2
WHERE p.ing_similarity >= 0.90 AND p.similarity < 0.50;

-- Recipes that appear in NO duplicate cluster (truly unique):
SELECT r.id, r.name, r.source_file FROM recipes r
WHERE r.id NOT IN (
    SELECT g.recipe_id FROM dup_groups g
    WHERE g.group_id IN (
        SELECT group_id FROM dup_groups GROUP BY group_id HAVING COUNT(*)>1
    )
);

-- Recipes never seen in any fuzzy pair:
SELECT id, name FROM recipes
WHERE id NOT IN (SELECT recipe_id_1 FROM dup_pairs)
  AND id NOT IN (SELECT recipe_id_2 FROM dup_pairs);
"""


def cmd_sql_examples(_args: argparse.Namespace) -> None:
    print(_SQL_EXAMPLES)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recipe deduplication — exact + fuzzy matching backed by SQLite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="Ingest recipe JSON files (idempotent)")
    p.add_argument("files", nargs="*", help="JSON files to ingest")
    p.add_argument("--stdin", action="store_true", help="Read file paths from stdin (one per line)")

    sub.add_parser("stats", help="Overall database statistics")

    p = sub.add_parser("exact-dupes", help="Show exact content-hash duplicates")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("ingredient-dupes", help="Show same-ingredient duplicates")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("build-pairs", help="Compute MinHash LSH fuzzy pairs (run once)")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)

    p = sub.add_parser("fuzzy-dupes", help="Show fuzzy pairs (requires build-pairs)")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser("build-groups", help="Cluster all pairs into groups (union-find)")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)

    p = sub.add_parser("show-groups", help="Display duplicate clusters")
    p.add_argument("--min-size", type=int, default=2)
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("compare", help="Detailed comparison of two recipes by ID")
    p.add_argument("id1", type=int)
    p.add_argument("id2", type=int)

    p = sub.add_parser("list", help="List ingested recipes")
    p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser("set-canonical", help="Mark a recipe as the canonical version of its group")
    p.add_argument("id", type=int)

    p = sub.add_parser("export-unique", help="Export one recipe per duplicate cluster")
    p.add_argument("--out", default="unique_recipes.json")

    sub.add_parser("sql-examples", help="Print useful ad-hoc SQL queries")

    args = parser.parse_args()
    {
        "ingest":           cmd_ingest,
        "stats":            cmd_stats,
        "exact-dupes":      cmd_exact_dupes,
        "ingredient-dupes": cmd_ingredient_dupes,
        "build-pairs":      cmd_build_pairs,
        "fuzzy-dupes":      cmd_fuzzy_dupes,
        "build-groups":     cmd_build_groups,
        "show-groups":      cmd_show_groups,
        "compare":          cmd_compare,
        "list":             cmd_list,
        "set-canonical":    cmd_set_canonical,
        "export-unique":    cmd_export_unique,
        "sql-examples":     cmd_sql_examples,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
