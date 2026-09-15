from app.models import Page
from app.scraper import extract_page
from app.structured_data import fill_extract, parse_json_ld, recipe_from_markdown, recipe_from_page


JSON_LD_HTML = """
<html><head><title>Lemon cake</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {"@type": "WebSite", "name": "Example"},
    {
      "@type": "Recipe",
      "name": "Lemon cake",
      "recipeIngredient": ["200 g flour", "2 eggs"],
      "recipeInstructions": [{"@type": "HowToStep", "text": "Mix and bake."}]
    }
  ]
}
</script>
</head>
<body>
  <nav>Shop now</nav>
  <p>Read more about our merch.</p>
</body></html>
"""

FOXX_STYLE_HTML = """
<html><head><title>Foxx drink</title></head>
<body>
  <h1>Foxx drink</h1>
  <p>Buy the bottle. Czytaj więcej.</p>
  <h2>Składniki</h2>
  <ul>
    <li>200 g soku</li>
    <li>5 g mleczanu</li>
    <li>1 szklanka wody</li>
  </ul>
  <h2>Przygotowanie</h2>
  <ol>
    <li>Wymieszaj.</li>
  </ol>
</body></html>
"""


def test_parse_json_ld_flattens_graph():
    items = parse_json_ld(JSON_LD_HTML)
    types = {item.get("@type") for item in items}
    assert "Recipe" in types
    assert "WebSite" in types


def test_extract_page_exposes_json_ld_recipe():
    page = extract_page(JSON_LD_HTML, "https://example.com/cake", "markdown", 50_000)
    assert page.structured_data
    assert page.recipe is not None
    assert page.recipe["source"] == "jsonld"
    assert page.recipe["recipeIngredient"] == ["200 g flour", "2 eggs"]
    assert page.recipe["recipeInstructions"] == ["Mix and bake."]
    assert page.recipe["name"] == "Lemon cake"


def test_extract_page_parses_html_ingredient_lists():
    page = extract_page(FOXX_STYLE_HTML, "https://foxx.example/drink", "markdown", 50_000)
    assert page.recipe is not None
    assert page.recipe["source"] == "html"
    assert "200 g soku" in page.recipe["recipeIngredient"]
    assert "5 g mleczanu" in page.recipe["recipeIngredient"]
    assert page.recipe["recipeInstructions"] == ["Wymieszaj."]


def test_extract_page_does_not_invent_recipe_from_shop_chrome():
    html = """
    <html><body>
      <h1>Shop</h1>
      <ul><li>Buy now</li><li>Read more</li></ul>
    </body></html>
    """
    page = extract_page(html, "https://example.com/shop", "text", 50_000)
    assert page.recipe is None


def test_fill_extract_uses_recipe_without_llm():
    page = Page(
        url="https://example.com/cake",
        markdown="noise",
        recipe={
            "name": "Lemon cake",
            "recipeIngredient": ["200 g flour"],
            "source": "jsonld",
        },
    )
    data = fill_extract(
        page,
        {"type": "object", "properties": {"ingredients": {"type": "array"}, "name": {"type": "string"}}},
        None,
    )
    assert data == {"ingredients": ["200 g flour"], "name": "Lemon cake"}


def test_recipe_from_page_prefers_json_ld_over_html_lists():
    recipe = recipe_from_page(JSON_LD_HTML, "https://example.com/cake", "Lemon cake")
    assert recipe is not None
    assert recipe["source"] == "jsonld"


JAMIE_STYLE_MARKDOWN = """
###### 1 hr 30 mins plus marinating

###### Not Too Tricky

###### serves 4

About the recipe

nutrition per serving

Recipe From

4 x 150g skinless boneless free-range chicken breasts

250ml buttermilk

2 heaped teaspoons medium curry powder

2 cloves of garlic

120g panko breadcrumbs

1 mug of basmati rice (300g)

olive oil

KATSU CURRY SAUCE

1 onion

2 cloves of garlic
"""

GORDON_STYLE_MARKDOWN = """
### Please upgrade your browser

## Steak with Chimichurri

### Ingredients

* 180g-200g Sirloin Steak
* Olive Oil
* Salt
* Pepper

Chimichurri Ingredients

* 1 Chili, sliced
* 2 Tablespoons of Olive Oil

### Cooking instructions

1. Season steak and sear.
2. Make the chimichurri and serve.

Watch Gordon make this amazing dish [here](https://youtube.com/watch?v=x)!

## Thank you

Thank you for signing up for our e-newsletter.
"""


def test_recipe_from_markdown_reads_quantified_paragraphs_without_heading():
    recipe = recipe_from_markdown(JAMIE_STYLE_MARKDOWN, "https://example.com/katsu", "Chicken katsu curry")
    assert recipe is not None
    assert recipe["source"] == "markdown"
    assert "4 x 150g skinless boneless free-range chicken breasts" in recipe["recipeIngredient"]
    assert "250ml buttermilk" in recipe["recipeIngredient"]
    assert "olive oil" in recipe["recipeIngredient"]
    assert "1 onion" in recipe["recipeIngredient"]
    assert all("newsletter" not in item.lower() for item in recipe["recipeIngredient"])
    assert all("about the recipe" not in item.lower() for item in recipe["recipeIngredient"])


def test_recipe_from_markdown_reads_ingredient_and_instruction_lists():
    recipe = recipe_from_markdown(GORDON_STYLE_MARKDOWN, "https://example.com/steak", None)
    assert recipe is not None
    assert "180g-200g Sirloin Steak" in recipe["recipeIngredient"]
    assert "Salt" in recipe["recipeIngredient"]
    assert "1 Chili, sliced" in recipe["recipeIngredient"]
    assert recipe["recipeInstructions"][0].startswith("Season steak")
    assert recipe["name"] == "Steak with Chimichurri"


def test_extract_page_parses_jamie_style_paragraph_ingredients():
    html = """
    <html><head><title>Chicken katsu curry</title></head>
    <body>
      <h1>Chicken katsu curry</h1>
      <p>About the recipe</p>
      <p>nutrition per serving</p>
      <p>4 x 150g skinless boneless free-range chicken breasts</p>
      <p>250ml buttermilk</p>
      <p>2 heaped teaspoons medium curry powder</p>
      <p>2 cloves of garlic</p>
      <p>Buy now</p>
    </body></html>
    """
    page = extract_page(html, "https://example.com/katsu", "markdown", 50_000)
    assert page.recipe is not None
    assert page.recipe["source"] == "markdown"
    assert "250ml buttermilk" in page.recipe["recipeIngredient"]
    assert "4 x 150g skinless boneless free-range chicken breasts" in page.recipe["recipeIngredient"]
