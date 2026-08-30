---
id: SPEC-006
title: "Mexican Recipe Collection"
tier: 2
type: html-config
priority: P1
status: done
impact: "TBD"
deliverables: []
---

# Spec: Mexican/BBQ/Chile/NetRelief/Coffee Shop HTML Configs (Garry Howard Sites)
## Tier: 2
## Type: html-config
## Priority: P1
## Estimated file impact: ~131 files (mexican: 39, netrelief: 57, bbq: 23, chile: 8, coffeeshop: 4)

## Description

This specification covers a family of ~131 HTML files across 5 directories created by Garry Howard (or published using identical Microsoft FrontPage / netRelief templates in the late 1990s and early 2000s):

1. `mexican/` (39 files, `.shtml`): Mexican and Tex-Mex recipes wrapped in `<blockquote>` elements with `<font size="5"><b>[Title]</b></font>`.
2. `netrelief/` (57 files, `.shtml`): General American and Southern recipes from `cooking.netrelief.com` with personal commentary, `Serving Size`, and `<blockquote>` layout.
3. `bbq/` (23 files, `.htm`): Barbecue, rubs, and mop sauces from `bbq.netrelief.com` wrapped inside `<table border="0" cellpadding="50">`.
4. `chile/` (8 files, `.shtml`): Chili recipes from `chile.netrelief.com` featuring `<h2>` titles, `<dl><dd>` ingredient lists, and `<td>` instruction blocks.
5. `The Coffee Shop Recipe Book/` (4 files, `.html`): Drink and beverage recipes from `The Coffee Shoppe` formatted with `<FONT SIZE="4"><B>` headers and multi-recipe pages.

Because each of the 5 layouts uses distinct HTML wrappers and tag structures, 5 separate YAML config files will be created in `configs/`.

## Input Samples

### Sample 1: `mexican/basic_mexican_salsa_recipe.shtml`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/mexican/basic_mexican_salsa_recipe.shtml`

```html
<p align="center"><font size="5"><b>Basic Salsa with Any Kind of Dry Chiles</b></font> </p>
...
<blockquote>
  <p><b>Recipe By : </b>Patricia Wriedt - Mexico City - pwriedt@spin.com.mx </p>
  <p><b>6 large Chiles dry *<br>
  1/2 medium Onion<br>
  1/4 cup Vinegar<br>
  1 clove garlic<br>
  Salt<br>
  Vegetable oil</b> </p>
  <p>* Morita, mulato, guajillo or any kind. If the chiles are little like jalapenos or
  serranos, use 15 chiles </p>
  <p>The kind of chiles that you use determine the final flavor... </p>
  <p>Wash the chiles in water and discard the seeds and threads of chiles...</p>
  <p>Patricia Wriedt </p>
</blockquote>

<p align="center"><img src="../images/hrwood.gif" WIDTH="600" HEIGHT="7"></p>
<p align="center"><font face="Verdana" size="2"><b><i>Garry's Home Cookin'<br>
Eat first, ask questions later!</i></b> </font></p>
```

### Sample 2: `netrelief/artichoke_dip_appetizer_recipe.shtml`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/netrelief/artichoke_dip_appetizer_recipe.shtml`

```html
<p align="center"><font size="5"><b>Artichoke Dip Appetizer </b></font></p>

<hr size="8">
<blockquote>
  <p>I downloaded this recipe off the internet years ago and I have made it numerous
  times. It is quite good. I add some chopped green chiles. </p>
  <p><i>Garry</i> </p>
  <p><b>Recipe By : </b>jbilos@labs-n.bbn.com (John Bilos)<br>
  <b>Serving Size : </b>10 </p>
  <p><b>8 ounces cream cheese<br>
  12 ounces mozzarella cheese -- shredded<br>
  1 cup mayonnaise<br>
  1 cup grated parmesan cheese<br>
  1 onion -- finely chopped<br>
  2 cloves garlic -- finely chopped<br>
  2 small jars marinated artichoke hearts -- DRAIN WELL<br>
  ...</b></p>
  <p>Tear artichokes apart with your fingers. </p>
  <p>Cut up pita bread into chip size triangles, seperate and bake on a cookie sheet until
  crisp. </p>
</blockquote>
```

### Sample 3: `bbq/achioterecado.htm`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/bbq/achioterecado.htm`

```html
<table border="0" cellpadding="50" width="550">
  <tr>
    <td><font size="5"><b>La Parilla Traditional Achiote Recado</b></font> <hr size="10">
    <p><b>Recipe By : </b>La Parilla the mexican grill by Reed Hearon </p>
    <p><b>2 Tablespoons Annatto Seeds<br>
    1/2 Cup Water<br>
    1 Teaspoon Ground Allspice<br>
    2 Teaspoons Ground Black Pepper<br>
    1/2 Cup Ancho Chile Powder<br>
    4 Teaspoons Kosher Salt<br>
    1 Tablespoon Mexican Oregano -- Toasted And Ground<br>
    3 Cloves Garlic -- Peeled<br>
    1/2 Medium White Onions -- Thickly Sliced<br>
    1/4 Cup Apple Cider Vinegar<br>
    1 1/2 Cups Freshly Squeezed Orange Juice<br>
    1/4 Cup Freshly Squeezed Lemon Juice </b></p>
    <p>This mild, citrusy red spice paste can transform the blandes of foods...</p>
    <p>Put the annatto seeds and water in a small saucepan and place over high heat...</p>
    <p>Makes about 2 1/2 cups.</p>
    </td>
  </tr>
</table>
```

### Sample 4: `chile/bad_attitude_chili_recipe.shtml`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/chile/bad_attitude_chili_recipe.shtml`

```html
<table border="0" cellpadding="30" cellspacing="0" width="750">
  <tr>
    <td align="center" valign="top" colspan="2"><h2>Bad Attitude Chili</h2>
    <p>serves 6-8 </td>
  </tr>
  <tr>
    <td colspan="2"><dl>
      <dd><b>2 lbs pork roast </b>-- cut into 1" pieces</dd>
      <dd><b>2 lbs cheap ground beef </b>-- (You'll need the fat. This isn't health food.)</dd>
      <dd><b>1/2 cup GOOD chile powder </b>-- (Your local supermarket brand tastes like
      dirt)</dd>
      ...
    </dl>
    </td>
  </tr>
  <tr>
    <td valign="top" width="375">Sautee 1/4 of the garlic and onions until translucent. Add
    1/4 of the meat, chile powder and brown. Salt the meat while cooking...</td>
    <td valign="top" width="375">As in any recipe, the amount of ingredients is variable...</td>
  </tr>
</table>
```

### Sample 5: `The Coffee Shop Recipe Book/000001-cool.html`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/The Coffee Shop Recipe Book/000001-cool.html`

```html
<P ALIGN="left"><FONT FACE="Times New Roman" SIZE="4"><B>Sweet 
Apple Cinnamon Herbal Shake<BR></B></FONT><FONT FACE="Times New Roman" SIZE="3"><B>Ingredients Needed:<BR>For each 16 
oz glass:<BR>
<UL><FONT COLOR="#836967" SIZE="1">
  <LI></FONT></UL></B></FONT><FONT FACE="Times New Roman" SIZE="3">2 cups 
  vanilla ice cream <BR><FONT COLOR="#836967" SIZE="1">
  <LI></FONT>2 The Coffee Shoppe Apple Cinnamon tea bags <BR><FONT COLOR="#836967" SIZE="1">
  <LI></FONT>1/4 tsp. cinnamon ( optional ) <BR></FONT><FONT FACE="Times New Roman" SIZE="3"><B>To Prepare:<BR></B></FONT><FONT FACE="Times New Roman" SIZE="3">In a blender, mix ingredients until 
fully blended. ( cut open tea bags and mix contents with ice cream 
)<BR></FONT><FONT FACE="Times New Roman" SIZE="3"><B>To
Serve:<BR></B></FONT><FONT FACE="Times New Roman" SIZE="3">Top with
whipped cream<BR>
</FONT></P>
```

## Expected Behavior

### 1. `configs/mexican.yaml`
```yaml
# SPDX-License-Identifier: MIT
name: mexican_recipes
description: "XPath configuration for Garry Howard's Mexican recipe archives"
version: "1.0"

detection:
  path_pattern: ".*mexican/.*\\.shtml?$"
  content_patterns:
    - "Garry's Home Cookin'"
    - "mexicancooking.netrelief.com"

fields:
  title:
    xpath: "//p[@align='center']/font[@size='5']/b/text() | //title/text()"
  description:
    xpath: "//blockquote/p[b[contains(., 'Recipe By')]]/text()"
  ingredients:
    xpath: "//blockquote/p[b and not(contains(b, 'Recipe By'))]/b//text()"
    split_delimiter: "\n"
  instructions:
    xpath: "//blockquote/p[not(b)]/text()"
```

### 2. `configs/netrelief.yaml`
```yaml
# SPDX-License-Identifier: MIT
name: netrelief_recipes
description: "XPath configuration for netRelief Home Cookin' archives"
version: "1.0"

detection:
  path_pattern: ".*netrelief/.*\\.shtml?$"
  content_patterns:
    - "Garry's Home Cookin'"
    - "cooking.netrelief.com"

fields:
  title:
    xpath: "//p[@align='center']/font[@size='5']/b/text() | //title/text()"
  yield_amount:
    xpath: "//p[b[contains(., 'Serving Size')]]/text()"
  description:
    xpath: "//blockquote/p[b[contains(., 'Recipe By')]]/text()"
  ingredients:
    xpath: "//blockquote/p[b and not(contains(b, 'Recipe By')) and not(contains(b, 'Serving Size'))]/b//text()"
    split_delimiter: "\n"
  instructions:
    xpath: "//blockquote/p[not(b) and not(i)]/text()"
```

### 3. `configs/bbq.yaml`
```yaml
# SPDX-License-Identifier: MIT
name: bbq_recipes
description: "XPath configuration for netRelief BBQ recipe archives"
version: "1.0"

detection:
  path_pattern: ".*bbq/.*\\.htm[l]?$"
  content_patterns:
    - "bbq.netrelief.com"
    - "Garry's Home Cookin'"

fields:
  title:
    xpath: "//table//font[@size='5']/b/text() | //title/text()"
  description:
    xpath: "//table//p[b[contains(., 'Recipe By')]]/text()"
  yield_amount:
    xpath: "//table//p[contains(., 'Makes')]/text()"
  ingredients:
    xpath: "//table//p[b and not(contains(b, 'Recipe By'))]/b//text()"
    split_delimiter: "\n"
  instructions:
    xpath: "//table//p[not(b) and not(contains(., 'Makes'))]/text()"
```

### 4. `configs/chile.yaml`
```yaml
# SPDX-License-Identifier: MIT
name: chile_recipes
description: "XPath configuration for netRelief Chili recipe archives"
version: "1.0"

detection:
  path_pattern: ".*chile/.*\\.shtml?$"
  content_patterns:
    - "chile.netrelief.com"
    - "Garry's Home Cookin'"

fields:
  title:
    xpath: "//h2/text() | //title/text()"
  yield_amount:
    xpath: "//p[contains(., 'serves')]/text()"
  ingredients:
    xpath: "//dl/dd//text()"
  instructions:
    xpath: "//table[last()]//tr[last()]//td/text()"
```

### 5. `configs/coffeeshop.yaml`
```yaml
# SPDX-License-Identifier: MIT
name: coffeeshop_recipes
description: "Configuration for The Coffee Shop Recipe Book archive"
version: "1.0"

detection:
  path_pattern: ".*Coffee Shop.*\\.html?$"
  content_patterns:
    - "The Coffee Shoppe"
    - "RocketLibrarian"

recipe_delimiter: '<FONT FACE="Times New Roman" SIZE="4"><B>'

fields:
  title:
    xpath: "//font[@size='4']/b/text()"
  ingredients:
    xpath: "//font[@size='3'][preceding-sibling::font[contains(., 'Ingredients Needed')] and following-sibling::font[contains(., 'To Prepare')]]//text()"
    split_delimiter: "\n"
  instructions:
    xpath: "//font[@size='3'][preceding-sibling::font[contains(., 'To Prepare')]]//text()"
```

### Edge Cases
1. **Commentary / Notes inside Ingredients**: Recipes often contain note paragraphs starting with asterisks (e.g. `* Morita, mulato, guajillo...`) immediately after the ingredient list.
2. **Google Ad Scripts**: Embedded JavaScript advertisement blocks (`google_ad_client`) exist in the body; XPath selectors must ignore script tags.
3. **Footer Navigation**: All Garry Howard pages end with a navigation bar (`Garry's Home Cookin'`, `Eat first, ask questions later!`, `garry@netrelief.com`). Selectors should constrain targets to `<blockquote>`, `<table cellpadding="50">`, or specific containers.
4. **Multiple Recipes in Coffee Shop**: Coffee Shop files contain multiple recipes per `.html` file separated by `<FONT SIZE="4"><B>`.

## Acceptance Criteria
- [ ] `configs/mexican.yaml` converts `mexican/basic_mexican_salsa_recipe.shtml`:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/mexican/basic_mexican_salsa_recipe.shtml' --html-config configs/mexican.yaml -o /tmp/test_mexican.json --no-nlp
  ```
  Produces valid JSON-LD with title `"Basic Salsa with Any Kind of Dry Chiles"`, 6 ingredients, and instructions.
- [ ] `configs/netrelief.yaml` converts `netrelief/artichoke_dip_appetizer_recipe.shtml`:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/netrelief/artichoke_dip_appetizer_recipe.shtml' --html-config configs/netrelief.yaml -o /tmp/test_netrelief.json --no-nlp
  ```
- [ ] `configs/bbq.yaml` converts `bbq/achioterecado.htm`:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/bbq/achioterecado.htm' --html-config configs/bbq.yaml -o /tmp/test_bbq.json --no-nlp
  ```
- [ ] `configs/chile.yaml` converts `chile/bad_attitude_chili_recipe.shtml`:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/chile/bad_attitude_chili_recipe.shtml' --html-config configs/chile.yaml -o /tmp/test_chile.json --no-nlp
  ```
- [ ] `configs/coffeeshop.yaml` converts `The Coffee Shop Recipe Book/000001-cool.html`:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/The Coffee Shop Recipe Book/000001-cool.html' --html-config configs/coffeeshop.yaml -o /tmp/test_coffeeshop.json --no-nlp
  ```
- [ ] Auto-detection identifies the correct configuration for each directory without explicit `--html-config` flag.
- [ ] Regression test suite passes:
  ```bash
  ./venv/bin/python3 -m pytest tests/test_conversion.py tests/test_detection.py -v
  ```

## Deliverables
- `configs/mexican.yaml`
- `configs/netrelief.yaml`
- `configs/bbq.yaml`
- `configs/chile.yaml`
- `configs/coffeeshop.yaml`

## Reference
- [parsers/html_config.py](file:///home/alex/junk/Recipes/scripts/parsers/html_config.py) — YAML configuration subsystem
- [parsers/html_parser.py](file:///home/alex/junk/Recipes/scripts/parsers/html_parser.py) — `HtmlParser` class
- [configs/bbc.yaml](file:///home/alex/junk/Recipes/scripts/configs/bbc.yaml) — reference HTML XPath config
