# SPDX-License-Identifier: MIT
"""MinHash path sharding helpers."""
import re
import zlib
from pathlib import Path
from typing import Set, Union


def get_tokens(text: str) -> Set[str]:
    """Extract lowercased word tokens (3+ chars) from text.

    Args:
        text: Input text string.

    Returns:
        Set of word tokens.
    """
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower().replace("_", " ")))


def minhash_bucket(text: str, num_perm: int = 16) -> str:
    """Computes a short, fast MinHash signature prefix.

    Similar texts yield the same bucket string (xx/yy).

    Args:
        text: Input text string.
        num_perm: Number of permutations for minhash.

    Returns:
        Bucket path prefix like 'ab/cd'.
    """
    tokens = get_tokens(text)
    if not tokens:
        tokens = {"default"}

    sig = []
    for i in range(num_perm):
        min_val = float("inf")
        for token in tokens:
            val = zlib.crc32(f"{i}:{token}".encode("utf-8"))
            if val < min_val:
                min_val = val
        sig.append(min_val)

    bucket_1 = f"{sig[0] % 256:02x}"
    bucket_2 = f"{sig[1] % 256:02x}"
    return f"{bucket_1}/{bucket_2}"


def get_recipe_sharded_path(
    url: str,
    title: str,
    base_dir: Union[str, Path] = "recipes",
) -> Path:
    """Returns a MinHash-based sharded directory path for a recipe.

    Args:
        url: Recipe URL or identifier.
        title: Recipe title.
        base_dir: Base directory path.

    Returns:
        Path object pointing to the sharded subdirectory.
    """
    bucket_dir = minhash_bucket(f"{title}")
    return Path(base_dir) / bucket_dir


# Backward compatibility aliases
_get_tokens = get_tokens
_minhash_bucket = minhash_bucket
_get_recipe_sharded_path = get_recipe_sharded_path
