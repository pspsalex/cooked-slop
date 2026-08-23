# Spec: cs.cmu Usenet Recipe Archive HTML Config
## Tier: 2
## Type: html-config
## Priority: P0
## Estimated file impact: ~735 files across 25 subdirectories

## Description

The Carnegie Mellon University (CMU) School of Computer Science (SCS) Usenet Recipe Archive contains hundreds of HTML files organized into 25 thematic subdirectories (`appetizers`, `bread`, `cake`, `candy`, `casserole`, `cheese`, `cookies`, `crockpot`, `dessert`, `drink`, `ethnic`, `grain`, `meat`, `misc`, `pasta`, `pie`, `preserves`, `salad`, `sauces`, `seafood`, `souffle`, `soup`, `sourdough`, `special`, `vegetables`).

These files are static HTML wrappers around Usenet `rec.food.recipes` postings curated in the early-to-mid 1990s. The HTML document contains `<title>` and `<h1>` elements for the recipe title, standard Usenet header lines (`From:`, `Date:`), and plain text recipe contents wrapped in a `<pre>` block. A standard Carnegie Mellon SCS footer follows the closing `</pre>` tag.

The goal is to create `configs/cscmu.yaml` to detect and parse these files into valid Schema.org JSON-LD recipes.

## Input Samples

### Sample 1: `cs.cmu/appetizers/beer-battered-nuggets.html`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/cs.cmu/appetizers/beer-battered-nuggets.html`

```html
<title>Beer Battered Nuggets</title>
<h1>Beer Battered Nuggets</h1>
From: hybl@umbc.edu (Dr. Albert Hybl)<P>
Date: 11 Sep 1993 20:14:26 -0400<P>

<pre>

Preparation of the Nuggets:- A nugget is a bite-size morsel from the
list of optional nugget ingredients.  You can use one ingredient alone
or in combination with others ingredients.  (One pound of nuggets will
yield 4-6 servings.)

Optional Nugget Ingredients:-
   Raw shrimp (shelled and deveined)
   Chicken or turkey breasts (skinned and deboned); cut into nugget sizes
   Turkey or chicken thighs (skinned and deboned); cut into nugget sizes
   --------- 
   Large peeled potatoes cut into 3/16 inch thick slices
   Large peeled sweet potatoes cut into 3/16 inch thick slices 
   Mushroom caps
   Bermuda onions cut and separated into rings
   Cauliflower heads
   Broccoli heads


Preheat Canola Oil or equivalent cooking oil.  Add a few drops of
sesame oil for flavor.  Use a good thermometer and bring the cooking
oil to 370 degrees F.


Beer Battering the Nuggets:-

    1 lb. nuggets                   1 c. flour
    1 t. baking powder            1/2 t. salt
    1 whole beaten egg            1/2 c. beer

Sift flour, baking powder and salt into a bowl.  Beat in egg and
beer (Pilsner Urquell or Martiner are both good beers).  Dip nuggets
in batter, coating them well.  Fry the nuggets in cooking oil until
browned.  Drain on paper towels and keep warm.
...
</pre>

<hr><ADDRESS><A HREF="http://www.mcs.vuw.ac.nz/school/staff/Amy-Gale.html">amyl</A></ADDRESS><hr><p><b><a href="http://www.scs.cmu.edu/">Carnegie Mellon's School of Computer Science</a></b>  (SCS) graciously hosts the <b>Recipe Archive</b>. We invite you to learn about SCS <b><a href="http://www.scs.cmu.edu/education/">educational programs</a></b> and <b><a href="http://www.scs.cmu.edu/research/">research</a></b>.</p>
```

### Sample 2: `cs.cmu/ethnic/morocco-tangine.html`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/cs.cmu/ethnic/morocco-tangine.html`

```html
<title>Moroccan Tagine</title>
<h1>Moroccan Tagine</h1>
<pre>
From: blkcat!Ted.Taylor@uunet.uu.net (Ted Taylor)
Date: Sun, 31 Oct 1993 01:25:12 -0500

      Title: Lamb & Pear Tagine.

      2 lg Onions, peeled & sliced             1 ts Cumin
      1 kg Lean lamb, leg or shoulder          1 ts Ground coriander
           -cut into 4cm cubes.                1 ts Ground ginger
      4    Pears, peeled cored & cut           1 ts Cinnamon
           -into 4cm chunks                    1 ts Black pepper
    1/2 c  Sultanas                                 Water, to cover the meat
    1/2 c  Silvered almonds                         Salt, to tast
      1 tb Olive oil

  Intro.
  Tagines are Moroccan slow-cooked meat, fruit & vegetable dishes which are
  almost invariably made with mutton. Using lamb cuts down the cooking
  time, but if you can find good hogget (older than lamb, younger than
  mutton, commonly labelled "baking legs" and sold cheaply) that will do
  very well.

  1.      In a large saucepan gently fry the onion in the olive oil until
          soft, add the meat to the pan and cook until it changes color,
          then add the spices. Add water to just cover the meat and salt to
          taste.
          Cover and simmer gently until the meat is tender, about 1 1/2 - 2
          hours. (Displace the lid a little after an hour if there appears
          to be too much liquid.)

  2.      Add the pears to the meat together with the sultanas & almonds.
          Cook for a further 5 minutes or until the pears are soft.
          Serve with rice.


</pre>

<hr><ADDRESS><A HREF="http://www.mcs.vuw.ac.nz/school/staff/Amy-Gale.html">amyl</A></ADDRESS><hr><p><b><a href="http://www.scs.cmu.edu/">Carnegie Mellon's School of Computer Science</a></b>  (SCS) graciously hosts the <b>Recipe Archive</b>. We invite you to learn about SCS <b><a href="http://www.scs.cmu.edu/education/">educational programs</a></b> and <b><a href="http://www.scs.cmu.edu/research/">research</a></b>.</p>
```

### Sample 3: `cs.cmu/soup/baked-potato-soup.html`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/cs.cmu/soup/baked-potato-soup.html`

```html
<title>Baked Potato Soup</title>
<h1>Baked Potato Soup</h1>
<pre>
From: holsend@mhd.moorhead.msus.edu
Date: 17 Sep 93 08:37:50 -0600


This is a rich, but great potato soup.
4 large potatoes
2/3 cup butter
2/3 cup flour
1 1/2 quarts of milk
Salt and Pepper
4 green onions
1 cup sour cream
2 cups crisp-cooked, crumbled bacon
5 ounces of grated cheddar cheese

Procedure

Heat oven to 350 degrees and bake the potatoes until for tender.
Melt butter in a medium saucepan.  Slowly blend in flour with a wire
whisk until thoroughly blended.  Gradually add milk to the butter-flour
mixture, whisking constantly.  Whisk in salt and pepper and simmer over
low heat, stirring constantly.

Cut potatoes in half, scoop out the meat and set aside.  Chop half the
potato peels and discard the remainder.  When milk mixture is very hot,
whisk in potato.  Add green onion and potato peels.  Whisk well, add
sour cream and crumbled bacon.  Heat thoroughly.  Add cheese a little
at a time until it is all melted in.

Serve with crusty French Bread and fresh butter.  Mucho Goodo!


</pre>
```

## Expected Behavior

### YAML Layout Schema (`configs/cscmu.yaml`)

Follow the schema in [parsers/html_config.py](file:///home/alex/junk/Recipes/scripts/parsers/html_config.py):

```yaml
# SPDX-License-Identifier: MIT
name: cscmu
description: "XPath configuration for Carnegie Mellon University School of Computer Science Usenet Recipe Archive"
version: "1.0"

detection:
  path_pattern: ".*cs\\.cmu/.*\\.html?$"
  content_patterns:
    - "Carnegie Mellon's School of Computer Science"
    - "Recipe Archive"

fields:
  title:
    xpath: "//h1/text() | //title/text()"
  description:
    xpath: "//pre/text()"
  instructions:
    xpath: "//pre/text()"
```

### Field Mapping
- **Title**: Extracted from `<h1>` or `<title>`. If `Title:` exists inside `<pre>`, it takes precedence or complements `<h1>`.
- **Author / Source**: Extracted from `From:` line or SCS footer ("Carnegie Mellon SCS Usenet Recipe Archive").
- **Ingredients & Instructions**: The recipe text inside `<pre>` is unstructured plain text, single-column ingredient blocks, or two-column MealMaster layouts. Extract the text of `<pre>` and allow the downstream parser pipeline ([parsers/generic.py](file:///home/alex/junk/Recipes/scripts/parsers/generic.py) or [parsers/two_col.py](file:///home/alex/junk/Recipes/scripts/parsers/two_col.py)) to parse ingredients and instructions.

### Edge Cases
1. **Two-Column Ingredient Layouts**: Some Usenet recipes use two columns (quantity + unit on the left column, quantity + unit on the right column).
2. **Collection Files**: Certain files in subdirectories (e.g. `sand-burger-spread-coll.html`, `mp-chicken-soup-coll.html`, `enorm-appetizer-coll.html`) contain multiple recipe digests inside a single `<pre>` block.
3. **Internal Title vs H1**: Some recipes contain `Title: Lamb & Pear Tagine.` inside `<pre>`, which might be cleaner than the generic `<h1>Moroccan Tagine</h1>`.
4. **Index and FAQ Files**: Files like `index.html` and `cooking-faq` are navigation directories or text FAQs; they should not crash and should produce 0 recipes gracefully.
5. **CMU SCS Footer**: Footer text after `</pre>` contains HTML anchor links to SCS educational programs; this should not be included in recipe instructions.

## Acceptance Criteria
- [ ] `configs/cscmu.yaml` exists and conforms to the `HtmlRecipeSchema` dataclass schema
- [ ] Auto-detection successfully scores `cs.cmu` files >= 0.5 without needing explicit `--html-config`
- [ ] Running conversion on sample 1 succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/cs.cmu/appetizers/beer-battered-nuggets.html' --html-config configs/cscmu.yaml -o /tmp/test_cscmu_app.json --no-nlp
  ```
  Produces valid JSON-LD with title `"Beer Battered Nuggets"` and structured ingredients.
- [ ] Running conversion on sample 2 succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/cs.cmu/ethnic/morocco-tangine.html' --html-config configs/cscmu.yaml -o /tmp/test_cscmu_eth.json --no-nlp
  ```
- [ ] Running conversion on sample 3 succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/cs.cmu/soup/baked-potato-soup.html' --html-config configs/cscmu.yaml -o /tmp/test_cscmu_soup.json --no-nlp
  ```
- [ ] Test suite passes cleanly:
  ```bash
  ./venv/bin/python3 -m pytest tests/test_conversion.py tests/test_detection.py -v
  ```

## Deliverables
- `configs/cscmu.yaml`

## Reference
- [parsers/html_config.py](file:///home/alex/junk/Recipes/scripts/parsers/html_config.py) — HTML YAML schema dataclasses and loader
- [parsers/html_parser.py](file:///home/alex/junk/Recipes/scripts/parsers/html_parser.py) — `HtmlParser` implementation
- [configs/bbc.yaml](file:///home/alex/junk/Recipes/scripts/configs/bbc.yaml) — example HTML XPath configuration
- [parsers/two_col.py](file:///home/alex/junk/Recipes/scripts/parsers/two_col.py) — two-column ingredient layout parsing
- [parsers/generic.py](file:///home/alex/junk/Recipes/scripts/parsers/generic.py) — fallback generic text parser
