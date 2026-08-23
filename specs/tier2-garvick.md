# Spec: Garvick.com Recipe Collection HTML Config
## Tier: 2
## Type: html-config
## Priority: P2
## Estimated file impact: 27 files

## Description

Extract recipes from the Garvick.com recipe compilation archive located at `/home/alex/junk/Recipes/Ingest/ToDo/HTML/garvick.com/`.

The archive contains 27 HTML files (e.g., `cakes.htm`, `barbecue.htm`, `candies.htm`, `cookie-recipes.htm`, `dinners.htm`, `pies.htm`, `picnic.htm`, `valentines-recipes.htm`). Unlike single-recipe pages, each Garvick file is an article compiling **multiple distinct recipes** (typically 5 to 10 recipes per file, e.g., "7 Father's Day Recipes for Cakes", "7 Fourth of July Recipes: Barbecue").

The deliverable is a YAML layout configuration `configs/garvick.yaml` (and any required multi-recipe parsing adjustments in `parsers/html_parser.py` / `parsers/html_config.py`) to extract all individual recipes from each page into Schema.org JSON-LD format.

## Input Samples

### Sample 1: `garvick.com/cakes.htm`
Path: `/home/alex/junk/Recipes/Ingest/ToDo/HTML/garvick.com/cakes.htm`

```html
<HTML>
<HEAD>
<TITLE>7 Father's Day Recipes for Cakes</TITLE>
<META NAME="description" CONTENT="Recipes for cakes to treat dad on father's day."> 
<META NAME="keywords" CONTENT="father's day cake recipes, father's day cakes, fathers day cakes"> 
</HEAD>
<BODY BACKGROUND="../../001.jpg">
<CENTER>
<P><SCRIPT LANGUAGE="JavaScript" SRC="../../../js/BGT-468-203.js"></SCRIPT></P>
</CENTER>
<H1 ALIGN="CENTER" STYLE="font-size: 24pt"><B><FONT COLOR="#FF00FF">7 Father's
Day Recipes for Cakes</FONT></B></H1>
<BLOCKQUOTE STYLE="font-size: 12pt"><BLOCKQUOTE><P ALIGN="CENTER">Recipes for
cakes to treat dad on father's day. Some ideas include Chocolate Marble Cake,
Fresh Strawberry Cupcakes, Sock It To Me Cake, Chocolate Malted Milk Cake,
Blonde Brownies, and Chocolate Decadence Cake.</P>
</BLOCKQUOTE>
</BLOCKQUOTE>
<!--Begin Ads - Annual-->
<BLOCKQUOTE><SCRIPT LANGUAGE="JavaScript" SRC="../../../js/G00.js"></SCRIPT></BLOCKQUOTE>
<!--End Ads - Annual--><P>&nbsp;</P>
<BLOCKQUOTE STYLE="font-size: 12pt"><BLOCKQUOTE> <P><B>Chocolate Marble Cake
</B></P>
<UL>
<LI> 1/3 c butter </LI>
<LI>1 c sugar </LI>
<LI> 2 ea egg, well beaten </LI>
<LI>1 1/2 c flour </LI>
<LI> 2 ts baking powder </LI>
<LI> 1/2 c milk </LI>
<LI>1 tb butter </LI>
<LI>1 ea chocolate square, unsweetened</LI>
<LI>1 ts vanilla </LI>
</UL>
<P> Cream together the butter and sugar; add the eggs and mix well. </P>
<P>Sift together the flour and baking powder and add alternately with the milk
to the creamed mixture. </P>
<P>Put 1/3 of the combined mixture into a bowl. Melt together the butter and
chocolate and add to the combined mixture. </P>
<P>Add the vanilla to the white batter. </P>
<P>Drop the white batter, then the chocolate batter, by spoonfuls into a
well-greased, deep cake pan and bake at 350-F for about 40 minutes.</P>
<SCRIPT LANGUAGE="JavaScript" SRC="../../../js/G01.js"></SCRIPT>
<P>&nbsp;</P>
<P ALIGN="CENTER"><IMG SRC="../cpic035.gif" ALT="father's day cakes recipes"
WIDTH="90%" HEIGHT="24" BORDER="0"></P>
<P></P>
<P><B>Fresh Strawberry Cupcakes </B></P>
<UL>
<LI> 1/2 c Butter or margarine, softened </LI>
<LI> 1 1/2 c Sugar </LI>
...
```

### Sample 2: `garvick.com/barbecue.htm`
Path: `/home/alex/junk/Recipes/Ingest/ToDo/HTML/garvick.com/barbecue.htm`

```html
<HTML>
<HEAD>
<TITLE>7 Fourth of July Recipes: Barbecue</TITLE>
<META NAME="description" CONTENT="Some barbeque recipes for your 4th of July celebrations...">
</HEAD>
<BODY BACKGROUND="../../001.jpg">
...
<H1 ALIGN="CENTER" STYLE="font-size: 24pt"><B><FONT COLOR="#FF00FF">7 Fourth of
July Recipes: Barbecue</FONT></B></H1>
...
<BLOCKQUOTE STYLE="font-size: 12pt"><BLOCKQUOTE STYLE="font-size: 12pt"> 
<P STYLE="font-size: 14pt"><B>Fourth of July BBQ'd Cornish Hens </B></P>
<P> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 3 cl Garlic, minced <BR>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 1 tb Seasoned salt <BR>
&nbsp;&nbsp;&nbsp; 1/2 c&nbsp; Oil <BR>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 1 c&nbsp; Fresh lemon juice <BR>
&nbsp;&nbsp;&nbsp;&nbsp; 12 ts Italian Salad dressing <BR>
&nbsp;&nbsp;&nbsp; 1/2 c&nbsp; Chopped onions <BR>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 1&nbsp;&nbsp;&nbsp; Pepper <BR>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 1 ts Crushed thyme <BR>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 4&nbsp;&nbsp;&nbsp; Rock Cornich Hens, giblets
removed <BR>
&nbsp; <BR>
Blend garlic, seasoned salt, oil, lemon juice, dressing, onions, pepper, and
thyme. Marinate the birds overnight in the refrigerator.</P>
<P> Cut the birds lengthwise. </P>
<P>Cook on outside grill, bone side down 10 minutes, flesh side down 5 minutes...
</P>
<P> Serves 8. </P>
...
```

## Expected Behavior

### Extraction Rules & Field Mapping
- **Detection**:
  - `path_pattern`: `.*garvick\.com/.*\.htm$`
  - `content_patterns`: `["garvick", "cpic035.gif", "BGT-468-20"]`
- **Recipe Titles**:
  - Variant A: `<P><B>[Title]</B></P>` (inside `BLOCKQUOTE`)
  - Variant B: `<P STYLE="font-size: 14pt"><B>[Title]</B></P>`
  - Exclude main article `H1` ("7 Father's Day Recipes...") and introductory description paragraphs.
- **Ingredients**:
  - Variant A (`cakes.htm`, `candies.htm`): List items inside `<UL><LI>` blocks.
  - Variant B (`barbecue.htm`): `<BR>`-delimited lines inside `<P>` blocks with non-breaking space padding (`&nbsp;`).
  - Unit normalization: Correctly handles MealMaster abbreviations (`c` = cup, `tb` = tablespoon, `ts` = teaspoon, `cl` = clove, `ea` = each, `pk` = package).
- **Instructions**:
  - `<P>` elements following ingredients up to the next recipe separator or yield statement.
- **Yield**:
  - Paragraphs matching `Serves [N].` or `Makes [N].` (e.g. `<P> Serves 8. </P>`).
- **Separators Between Recipes**:
  - Image dividers (`<IMG SRC="../cpic035.gif">`), `<SCRIPT>` ad tags, or `<P>&nbsp;</P>`.

### Config Structure Example
To copy the structure from existing configs like `configs/bbc.yaml`:

```yaml
# SPDX-License-Identifier: MIT
name: garvick
description: "XPath configuration for Garvick.com recipe collection"
version: "1.0"

detection:
  path_pattern: ".*garvick\\.com/.*\\.htm$"
  content_patterns:
    - "BGT-468"
    - "cpic035.gif"

fields:
  title:
    xpath: "//p//b[not(ancestor::h1) and not(ancestor::script)]/text() | //p[@style and contains(@style, '14pt')]//b/text()"
  yield_amount:
    xpath: "//p[starts-with(normalize-space(text()), 'Serves') or starts-with(normalize-space(text()), 'Makes')]/text()"
  ingredients:
    xpath: "//ul/li | //p[contains(text(), 'cl') or contains(text(), 'tb') or contains(text(), 'ts') or contains(text(), 'c ')]"
  instructions:
    xpath: "//p[not(ancestor::h1) and not(.//b) and not(starts-with(normalize-space(text()), 'Serves'))]"
```

### Edge Cases
1. **Multiple recipes per single HTML file**: Each HTML page compiles 5–10 recipes. `parse_content` in `HtmlParser` should support yielding multiple recipes per file when a multi-recipe config is active or when repeating recipe blocks are present.
2. **Two distinct ingredient formats**: Some pages use `<ul><li>...</li></ul>` lists, while others use `<p>` blocks containing lines delimited by `<br>`.
3. **Non-breaking spaces (`&nbsp;`)**: Used heavily for column alignment in text-based ingredient blocks. Must be normalized to standard whitespace before ingredient parsing.
4. **Ad scripts and images**: Embedded `<script>` ad injection and divider GIFs between recipes must not be captured as ingredient or instruction text.
5. **Non-recipe HTML pages**: The archive contains non-food craft pages (`easter-crafts.htm`, `easter-games.htm`, `easter-gifts.htm`) and index hubs (`index.html`, `recipes.htm`). These should either yield 0 recipes or be cleanly skipped without errors.

## Acceptance Criteria
- [ ] `configs/garvick.yaml` created with valid schema.
- [ ] Multi-recipe extraction extracts at least 2 distinct recipes from `garvick.com/cakes.htm` (including "Chocolate Marble Cake" and "Fresh Strawberry Cupcakes").
- [ ] Successfully extracts recipes from `garvick.com/barbecue.htm` (including "Fourth of July BBQ'd Cornish Hens").
- [ ] Ingredient quantities and units (including abbreviations `c`, `tb`, `ts`, `cl`, `ea`) parse accurately into `Ingredient` dataclass objects.
- [ ] Non-recipe files (`easter-games.htm`, `index.html`) process without unhandled exceptions or crashes.
- [ ] Test sample(s) added to `tests/samples/` and expected JSON-LD output generated in `tests/expected/` using `--no-nlp`.
- [ ] Test commands succeed:
  ```bash
  ./venv/bin/python3 convert.py tests/samples/garvick_cakes.htm -o tests/expected/garvick_cakes.htm.json --no-nlp
  ./venv/bin/python3 -m pytest tests/ -v
  ```
- [ ] All 27 files in `/home/alex/junk/Recipes/Ingest/ToDo/HTML/garvick.com/` parse without unhandled exceptions.

## Deliverables
- `/home/alex/junk/Recipes/scripts/configs/garvick.yaml`
- `/home/alex/junk/Recipes/scripts/tests/samples/garvick_cakes.htm`
- `/home/alex/junk/Recipes/scripts/tests/expected/garvick_cakes.htm.json`

## Reference
- [configs/bbc.yaml](file:///home/alex/junk/Recipes/scripts/configs/bbc.yaml) — existing HTML YAML schema
- [parsers/html_config.py](file:///home/alex/junk/Recipes/scripts/parsers/html_config.py) — `HtmlConfigRegistry` and `HtmlRecipeSchema`
- [parsers/html_parser.py](file:///home/alex/junk/Recipes/scripts/parsers/html_parser.py) — `HtmlParser`
- [parsers/units.py](file:///home/alex/junk/Recipes/scripts/parsers/units.py) — `UNIT_MAP` for MealMaster units
- [extract/garvick1.py](file:///home/alex/junk/Recipes/scripts/extract/garvick1.py) and [extract/garvick2.py](file:///home/alex/junk/Recipes/scripts/extract/garvick2.py) — prior extraction scripts
- [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md) — project conventions
