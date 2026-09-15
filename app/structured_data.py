import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.models import Page

INGREDIENT_SELECTORS = (
    '[itemprop="recipeIngredient"]',
    ".wprm-recipe-ingredient",
    ".tasty-recipes-ingredients li",
    ".mv-create-ingredients li",
    ".recipe-ingredients li",
    ".ingredients li",
)
INSTRUCTION_SELECTORS = (
    '[itemprop="recipeInstructions"] li',
    '[itemprop="recipeInstructions"]',
    ".wprm-recipe-instruction-text",
    ".tasty-recipes-instructions li",
    ".mv-create-instructions li",
    ".recipe-instructions li",
    ".instructions li",
)
INGREDIENT_HEADING = re.compile(
    r"sk[lł]adnik|ingredients?|what you.?ll need|b[eę]dziesz potrzeb",
    re.I,
)
INSTRUCTION_HEADING = re.compile(
    r"instrukc|instructions?|przygotow|directions?|method|steps?\b|wykonanie|krok",
    re.I,
)
_NUMBER = r"(?:\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+[.,]?\d*)"
_UNIT = (
    r"(?:kg|g|ml|cl|l|oz|lb|tsp|tbsp|teaspoons?|tablespoons?|cups?|cloves?|"
    r"litres?|liters?|cm|mm|łyżeczki|łyżeczka|łyżki|łyżka|łyż|szklanki|szklanka|szkl|szt)"
)
QUANTITY = re.compile(
    rf"^\s*(?:[-*+]|\d+[.)])?\s*(?:\d+\s*[x×]\s*)?{_NUMBER}\s*(?:-\s*{_NUMBER})?\s*{_UNIT}?\b",
    re.I,
)
NOISE = re.compile(
    r"\b(?:mins?|minutes?|hours?|hrs?|proving|tricky|serves|makes|nutrition|"
    r"about the recipe|recipe from|czytaj wi[eę]cej|buy now|shop now|subscribe|"
    r"newsletter|upgrade your browser|back to top|watch .+ here)\b",
    re.I,
)
BARE_INGREDIENT = re.compile(
    r"^(?:a\s+|an\s+|handful of\s+|pinch of\s+|dash of\s+)?"
    r"(?:salt|pepper|olive oil|butter|oil|honey|lemon zest|to taste)\b",
    re.I,
)
HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$")
MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
RECIPE_SCHEMA_KEYS = {
    "recipeingredient",
    "recipeinstructions",
    "ingredients",
    "instructions",
    "recipename",
    "recipeyield",
    "preptime",
    "cooktime",
}


def parse_json_ld(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        script_type = (script.get("type") or "").lower()
        if "ld+json" not in script_type:
            continue
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items.extend(_flatten_json_ld(parsed))
    return items


def is_ingredient_line(line: str) -> bool:
    text = _clean_md_line(line)
    if not text or NOISE.search(text) or HEADING_LINE.match(line.strip()):
        return False
    return bool(QUANTITY.search(text) or BARE_INGREDIENT.search(text))


def content_recipe_score(text: str) -> tuple:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    qty = sum(1 for line in lines if is_ingredient_line(line))
    if qty >= 3 or INGREDIENT_HEADING.search(text):
        return (1, qty / max(len(text), 1), -len(text))
    return (0, float(len(text)), 0.0)


def recipe_from_markdown(markdown: str, url: str, title: str | None) -> dict[str, Any] | None:
    if not markdown or not markdown.strip():
        return None
    sections = _markdown_sections(markdown)
    ingredients: list[str] = []
    for heading, body in sections:
        if heading and INGREDIENT_HEADING.search(heading):
            ingredients.extend(_section_items(body, require_ingredient=False))
    from_heading = len(ingredients) >= 2
    if not from_heading:
        ingredients = _best_ingredient_run(markdown)
    if from_heading:
        if len(ingredients) < 2:
            return None
    elif not _enough_ingredients(ingredients, required_quantity=True):
        return None
    instructions: list[str] = []
    for heading, body in sections:
        if heading and INSTRUCTION_HEADING.search(heading):
            instructions = _section_items(body, require_ingredient=False)
            break
    name = title
    for heading, _body in sections:
        if (
            heading
            and not INGREDIENT_HEADING.search(heading)
            and not INSTRUCTION_HEADING.search(heading)
            and not NOISE.search(heading)
            and len(heading) > 3
        ):
            name = name or heading
            break
    return _recipe_record(
        name=name,
        description=None,
        ingredients=ingredients,
        instructions=instructions,
        prep_time=None,
        cook_time=None,
        total_time=None,
        recipe_yield=None,
        author=None,
        url=url,
        source="markdown",
    )


def recipe_from_page(
    html: str,
    url: str,
    title: str | None,
    items: list[dict[str, Any]] | None = None,
    markdown: str | None = None,
) -> dict[str, Any] | None:
    items = parse_json_ld(html) if items is None else items
    from_ld = _recipe_from_jsonld(items, url, title)
    if from_ld:
        return from_ld
    from_html = _recipe_from_html(html, url, title)
    from_md = recipe_from_markdown(markdown or "", url, title)
    if from_html and from_md:
        html_n = len(from_html.get("recipeIngredient") or [])
        md_n = len(from_md.get("recipeIngredient") or [])
        return from_md if md_n > html_n else from_html
    return from_html or from_md


def fill_extract(page: Page, schema: dict | None, prompt: str | None) -> dict[str, Any] | None:
    recipe = page.recipe
    if recipe is None and _wants_recipe(schema, prompt) and page.markdown:
        recipe = recipe_from_markdown(page.markdown, page.url, page.title)
    if recipe and _wants_recipe(schema, prompt):
        return _map_to_schema(recipe, schema)
    if page.structured_data and _wants_recipe(schema, prompt):
        from_ld = _recipe_from_jsonld(page.structured_data, page.url, page.title)
        if from_ld:
            return _map_to_schema(from_ld, schema)
    match = _best_jsonld_match(page.structured_data or [], schema, prompt)
    if match:
        return _map_to_schema(match, schema)
    return None


def _flatten_json_ld(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, list):
        items: list[dict[str, Any]] = []
        for item in node:
            items.extend(_flatten_json_ld(item))
        return items
    if not isinstance(node, dict):
        return []
    graph = node.get("@graph")
    if isinstance(graph, list):
        return _flatten_json_ld(graph)
    return [node]


def _types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type") or node.get("type")
    values = raw if isinstance(raw, list) else [raw]
    return {str(value).rsplit("/", 1)[-1] for value in values if value}


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        return _as_text(value.get("name") or value.get("text") or value.get("@value"))
    if isinstance(value, list):
        parts = [_as_text(item) for item in value]
        joined = ", ".join(part for part in parts if part)
        return joined or None
    return str(value)


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_as_text_list(item))
        return items
    if isinstance(value, dict):
        nested = value.get("itemListElement") or value.get("text") or value.get("name")
        if nested is not None and nested is not value:
            return _as_text_list(nested)
        text = _as_text(value)
        return [text] if text else []
    text = _as_text(value)
    return [text] if text else []


def _recipe_from_jsonld(items: list[dict[str, Any]], url: str, title: str | None) -> dict[str, Any] | None:
    recipe = next((item for item in items if "Recipe" in _types(item)), None)
    if not recipe:
        return None
    ingredients = _as_text_list(recipe.get("recipeIngredient") or recipe.get("ingredients"))
    instructions = _as_text_list(recipe.get("recipeInstructions") or recipe.get("instructions"))
    if not ingredients:
        return None
    return _recipe_record(
        name=_as_text(recipe.get("name")) or title,
        description=_as_text(recipe.get("description")),
        ingredients=ingredients,
        instructions=instructions,
        prep_time=_as_text(recipe.get("prepTime")),
        cook_time=_as_text(recipe.get("cookTime")),
        total_time=_as_text(recipe.get("totalTime")),
        recipe_yield=_as_text(recipe.get("recipeYield")),
        author=_as_text(recipe.get("author")),
        url=_as_text(recipe.get("url")) or url,
        source="jsonld",
    )


def _recipe_from_html(html: str, url: str, title: str | None) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    ingredients = _texts_from_selectors(soup, INGREDIENT_SELECTORS)
    if not ingredients:
        ingredients = _list_after_heading(soup, INGREDIENT_HEADING)
    if not _enough_ingredients(ingredients, required_quantity=not _has_recipe_markup(soup)):
        return None
    instructions = _texts_from_selectors(soup, INSTRUCTION_SELECTORS)
    if not instructions:
        instructions = _list_after_heading(soup, INSTRUCTION_HEADING)
    heading = soup.find(["h1", "h2"])
    return _recipe_record(
        name=title or (heading.get_text(" ", strip=True) if heading else None),
        description=None,
        ingredients=ingredients,
        instructions=instructions,
        prep_time=None,
        cook_time=None,
        total_time=None,
        recipe_yield=None,
        author=None,
        url=url,
        source="html",
    )


def _has_recipe_markup(soup: BeautifulSoup) -> bool:
    return bool(soup.select_one('[itemprop="recipeIngredient"], .wprm-recipe-ingredient, .tasty-recipes-ingredients'))


def _clean_md_line(line: str) -> str:
    text = MD_LINK.sub(r"\1", line.strip())
    text = LIST_LINE.sub(r"\1", text)
    return text.strip().strip("*_").strip()


def _markdown_sections(markdown: str) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = []
    heading: str | None = None
    body: list[str] = []
    for raw in markdown.splitlines():
        match = HEADING_LINE.match(raw.strip())
        if match:
            if heading is not None or body:
                sections.append((heading, body))
            heading = match.group(2).strip()
            body = []
            continue
        body.append(raw)
    if heading is not None or body:
        sections.append((heading, body))
    return sections


def _section_items(lines: list[str], *, require_ingredient: bool) -> list[str]:
    items: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped in {"---", "***"} or HEADING_LINE.match(stripped):
            if items:
                break
            continue
        listed = LIST_LINE.match(stripped)
        text = _clean_md_line(stripped)
        if not text or NOISE.search(text):
            continue
        if listed or is_ingredient_line(text):
            items.append(text)
            continue
        if items and require_ingredient:
            break
    return items


def _best_ingredient_run(markdown: str) -> list[str]:
    best: list[str] = []
    current: list[str] = []
    misses = 0
    for raw in markdown.splitlines():
        stripped = raw.strip()
        if HEADING_LINE.match(stripped):
            if len(current) > len(best):
                best = current
            current = []
            misses = 0
            continue
        if not stripped:
            continue
        text = _clean_md_line(stripped)
        if not text or NOISE.search(text):
            misses += 1
            if misses >= 2:
                if len(current) > len(best):
                    best = current
                current = []
                misses = 0
            continue
        if is_ingredient_line(text) or (current and text.isupper() and len(text) < 40):
            if text.isupper() and not QUANTITY.search(text):
                misses = 0
                continue
            current.append(text)
            misses = 0
            continue
        misses += 1
        if misses >= 2:
            if len(current) > len(best):
                best = current
            current = []
            misses = 0
    if len(current) > len(best):
        best = current
    return best


def _enough_ingredients(ingredients: list[str], *, required_quantity: bool) -> bool:
    if len(ingredients) < 2:
        return False
    if not required_quantity:
        return True
    quantified = sum(1 for line in ingredients if QUANTITY.search(line))
    return quantified >= max(2, (len(ingredients) + 1) // 2)


def _texts_from_selectors(soup: BeautifulSoup, selectors: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    texts: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if text and text not in seen:
                seen.add(text)
                texts.append(text)
        if texts:
            return texts
    return texts


def _list_after_heading(soup: BeautifulSoup, heading_re: re.Pattern[str]) -> list[str]:
    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        if not heading_re.search(heading.get_text(" ", strip=True)):
            continue
        sibling = heading.find_next_sibling()
        while sibling and isinstance(sibling, Tag) and sibling.name in {"p", "div"} and not sibling.find(["ul", "ol"]):
            sibling = sibling.find_next_sibling()
        if isinstance(sibling, Tag) and sibling.name in {"ul", "ol"}:
            items = [item.get_text(" ", strip=True) for item in sibling.find_all("li")]
            return [item for item in items if item]
        parent_list = heading.find_next(["ul", "ol"])
        if parent_list:
            items = [item.get_text(" ", strip=True) for item in parent_list.find_all("li")]
            return [item for item in items if item]
    return []


def _recipe_record(
    *,
    name: str | None,
    description: str | None,
    ingredients: list[str],
    instructions: list[str],
    prep_time: str | None,
    cook_time: str | None,
    total_time: str | None,
    recipe_yield: str | None,
    author: str | None,
    url: str,
    source: str,
) -> dict[str, Any]:
    record = {
        "name": name,
        "description": description,
        "recipeIngredient": ingredients,
        "recipeInstructions": instructions or None,
        "prepTime": prep_time,
        "cookTime": cook_time,
        "totalTime": total_time,
        "recipeYield": recipe_yield,
        "author": author,
        "url": url,
        "source": source,
    }
    return {key: value for key, value in record.items() if value is not None}


def _wants_recipe(schema: dict | None, prompt: str | None) -> bool:
    blob = f"{json.dumps(schema or {})} {prompt or ''}".lower()
    if "recipe" in blob:
        return True
    properties = (schema or {}).get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return False
    return any(key.lower() in RECIPE_SCHEMA_KEYS for key in properties)


def _best_jsonld_match(items: list[dict[str, Any]], schema: dict | None, prompt: str | None) -> dict[str, Any] | None:
    if not items:
        return None
    blob = f"{json.dumps(schema or {})} {prompt or ''}".lower()
    for item in items:
        types = {name.lower() for name in _types(item)}
        if types and any(name in blob for name in types):
            return item
    return None


def _map_to_schema(data: dict[str, Any], schema: dict | None) -> dict[str, Any]:
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return data
    aliases = {
        "ingredients": "recipeIngredient",
        "instructions": "recipeInstructions",
        "title": "name",
        "yield": "recipeYield",
    }
    mapped: dict[str, Any] = {}
    for key in properties:
        if key in data:
            mapped[key] = data[key]
        elif aliases.get(key) in data:
            mapped[key] = data[aliases[key]]
    return mapped or data
