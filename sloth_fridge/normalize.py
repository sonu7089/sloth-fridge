from __future__ import annotations

import re
import unicodedata

from .config import CATEGORIES, CATEGORY_ORDER

UNIT_SYNONYMS = {
    "pcs": "piece",
    "pc": "piece",
    "pieces": "piece",
    "item": "piece",
    "items": "piece",
    "units": "piece",
    "each": "piece",
    "x": "piece",
    "cartons": "container",
    "carton": "container",
    "bottles": "container",
    "bottle": "container",
    "jug": "container",
    "tubs": "container",
    "tub": "container",
    "cans": "container",
    "can": "container",
    "pouch": "container",
    "boxes": "pack",
    "box": "pack",
    "pack": "pack",
    "packs": "pack",
    "bags": "pack",
    "bag": "pack",
    "jars": "container",
    "jar": "container",
    "bunches": "bunch",
    "bunch": "bunch",
    "loaves": "loaf",
    "loaf": "loaf",
    "slices": "slice",
    "slice": "slice",
    "head": "piece",
    "heads": "piece",
    "bulb": "piece",
    "bulbs": "piece",
    "sprig": "bunch",
    "sprigs": "bunch",
    "stick": "piece",
    "sticks": "piece",
    "btl": "container",
    "btls": "container",
    "pkg": "pack",
    "pkgs": "pack",
    "pk": "piece",
}

UNIT_FAMILIES = {
    "container": {"container", "pack"},
    "pack": {"container", "pack"},
    "piece": {"piece", "loaf", "bunch", "slice"},
    "loaf": {"piece", "loaf"},
    "bunch": {"piece", "bunch"},
    "slice": {"piece", "slice"},
}

SYNONYMS = {
    "whole milk": "milk",
    "full fat milk": "milk",
    "skim milk": "milk",
    "2% milk": "milk",
    "semi skimmed milk": "milk",
    "yoghurt": "yogurt",
    "greek yoghurt": "yogurt",
    "plain yoghurt": "yogurt",
    "natural yoghurt": "yogurt",
    "feta cheese": "feta",
    "shredded cheese": "cheese",
    "grated cheese": "cheese",
    "cheddar": "cheese",
    "mozzarella": "mozzarella",
    "egg": "eggs",
    "large eggs": "eggs",
    "free range eggs": "eggs",
    "chicken breast": "chicken",
    "chicken breasts": "chicken",
    "chicken thigh": "chicken",
    "ground beef": "beef",
    "minced beef": "beef",
    "steak": "beef",
    "whole chicken": "chicken",
    "bananas": "banana",
    "apples": "apple",
    "oranges": "orange",
    "tomatoes": "tomato",
    "tomatoes ": "tomato",
    "cherry tomatoes": "cherry tomato",
    "baby spinach": "spinach",
    "spinach leaves": "spinach",
    "iceberg lettuce": "lettuce",
    "romaine lettuce": "lettuce",
    "mixed salad": "salad",
    "salad mix": "salad",
    "spring water": "water",
    "still water": "water",
    "mineral water": "water",
    "orange juice": "orange juice",
    "cola": "soda",
    "ketchup": "tomato ketchup",
    "mayonnaise": "mayo",
    "coconut milk": "coconut milk",
    "olive oil extra virgin": "olive oil",
    "extra virgin olive oil": "olive oil",
    "vegetable oil": "oil",
    "sunflower oil": "oil",
    "sunflower seeds": "sunflower seeds",
    "frozen peas": "peas",
    "sweet corn": "corn",
    "tinned tomatoes": "canned tomatoes",
    "canned tomatoes": "canned tomatoes",
    "chopped tomatoes": "canned tomatoes",
    "passata": "canned tomatoes",
    "white wine": "wine",
    "red wine": "wine",
    "orange juice concentrate": "orange juice",
}

CATEGORY_KEYWORDS = [
    ("seafood", ["salmon", "tuna", "cod", "prawn", "shrimp", "mackerel", "sardine", "crab", "mussel", "oyster", "scallop", "anchovy", "fish"]),
    ("meat", ["chicken", "beef", "pork", "lamb", "turkey", "bacon", "sausage", "ham", "prosciutto", "steak", "meatball", "mince", "brisket"]),
    ("eggs", ["egg"]),
    ("dairy", ["milk", "yogurt", "cheese", "butter", "cream", "mozzarella", "feta", "parmesan", "mascarpone", "kefir", "custard"]),
    ("bread", ["bread", "baguette", "bun", "roll", "bagel", "pita", "tortilla", "croissant", "muffin", "loaf", "rye", "sourdough"]),
    ("frozen", ["frozen", "ice cream", "popsicle"]),
    ("produce", ["apple", "banana", "orange", "lemon", "lime", "tomato", "lettuce", "spinach", "kale", "carrot", "potato", "onion", "garlic", "pepper", "cucumber", "grape", "berry", "berries", "peach", "pear", "mango", "avocado", "broccoli", "cauliflower", "celery", "herb", "parsley", "basil", "cilantro", "ginger", "mushroom", "zucchini", "corn", "peas", "melon", "plum", "cherry", "strawberr", "raspberr", "blueberr", "grapefruit", "pineapple", "radish", "beet", "leek", "corn", "asparagus", "cabbage", "pumpkin", "eggplant", "aubergine", "squash"]),
    ("beverage", ["water", "juice", "soda", "cola", "beer", "wine", "coffee", "tea", "kombucha", "lemonade", "seltzer", "sparkling"]),
    ("condiment", ["ketchup", "mustard", "mayo", "mayonnaise", "sauce", "dressing", "oil", "vinegar", "salsa", "jam", "honey", "syrup", "relish", "pickle"]),
    ("snack", ["chip", "crisp", "cracker", "cookie", "biscuit", "chocolate", "candy", "popcorn", "nuts", "granola bar", "snack"]),
    ("pantry_staple", ["rice", "pasta", "noodle", "flour", "sugar", "salt", "bean", "lentil", "chickpea", "cereal", "oat", "quinoa", "couscous", "canned", "tinned", "broth", "stock", "sauce", "peanut butter", "honey", "syrup", "yeast", "cocoa"]),
]

PLURAL_EXCEPTIONS = {
    "grapes": "grape",
    "greens": "greens",
    "oats": "oats",
    "beans": "beans",
    "lentils": "lentils",
    "noodles": "noodles",
}

BRAND_TOKENS = {
    "kikkoman", "heinz", "french's", "french'", "french", "newman's", "newmans", "knorr",
    "maggi", "bertolli", "gordon's", "gordons", "lea", "perrin", "mccormick", "del monte",
    "delmonte", "hunt's", "hunts", "carnation", "nestle", "nestlé", "dole", "yoplait",
    "danone", "mars", "cadbury", "oreo", "kellogg's", "kelloggs", "quaker", "post",
    "mondelez", "unilever", "kraft", "philadelphia", "hormel", "kirkland", "signature",
    "smucker'", "smucker's", "smucker", "taste you love", "a1", "a.1.", "spaceplus",
    "spaceplu", "lay", "lays",
}

DESCRIPTOR_WORDS = {
    "lid", "cap", "caps", "lids", "label", "labels", "top", "bottom", "shelf", "shelves",
    "contents", "color", "colour", "colored", "coloured", "shape", "text", "writing",
    "sticker", "package", "packaging", "front", "back", "left", "right", "row", "layer",
    "surface", "edge", "corner", "view", "image", "photo", "picture", "background",
    "plastic", "metal", "glass", "substance", "material", "tub", "packet", "box", "bag",
    "wrapper", "foil", "plastic wrap", "cellophane", "opaque", "transparent", "clear",
    "content", "packaged", "good", "goods", "product", "products",
    "yellowish", "greenish", "reddish", "brownish", "dark", "light",
    "tray", "holder", "rack", "kernel", "vegetable", "vegetables",
    "cylindrical", "rectangular", "round", "square", "object", "objects", "shaped",
}

COLOR_ONLY = {
    "purple", "yellow", "green", "white", "black", "brown", "pink", "grey", "gray",
    "beige", "tan", "blue", "gold", "golden", "silver",
}

EXTRA_SYNONYMS = {
    "tea bag": "tea",
    "juice box": "juice",
    "coffee pod": "coffee",
    "coffee pods": "coffee",
    "coffee bean": "coffee",
    "coffee beans": "coffee",
    "ground coffee": "coffee",
    "kitchen roll": "kitchen roll",
    "aluminium foil": "foil",
    "greek yogurt": "yogurt",
    "cheddar cheese": "cheese",
    "cheddar cheese block": "cheese",
    "cheese block": "cheese",
    "sourdough loaf": "bread",
    "sourdough": "bread",
    "white loaf": "bread",
    "olive oil": "olive oil",
    "yellow mustard": "mustard",
    "mustard sauce": "mustard",
    "hot sauce": "hot sauce",
    "sauce bottle": "hot sauce",
    "bottled sauce": "hot sauce",
    "olive oil bottle": "olive oil",
    "soy sauce": "soy sauce",
    "apple sauce": "applesauce",
    "canned corn": "corn",
    "frozen corn": "corn",
    "canned beans": "beans",
    "ice cream": "ice cream",
    "frozen dessert": "ice cream",
    "sour cream": "sour cream",
    "cream cheese": "cream cheese",
    "cottage cheese": "cottage cheese",
    "salad dressing": "salad dressing",
    "dressing": "salad dressing",
    "egg carton": "eggs",
    "carton of eggs": "eggs",
    "baby carrots": "carrot",
    "baby spinach": "spinach",
    "mixed greens": "greens",
    "spring mix": "greens",
    "orange juice": "orange juice",
    "lemon juice": "lemon juice",
    "white vinegar": "vinegar",
    "apple vinegar": "vinegar",
    "balsamic vinegar": "vinegar",
}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def singularize(word: str) -> str:
    if word in PLURAL_EXCEPTIONS:
        return PLURAL_EXCEPTIONS[word]
    irregular = {
        "leaves": "leaf",
        "loaves": "loaf",
        "halves": "half",
        "knives": "knife",
        "potatoes": "potato",
        "tomatoes": "tomato",
        "berries": "berry",
        "cherries": "cherry",
        "peaches": "peach",
    }
    if word in irregular:
        return irregular[word]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ses") or word.endswith("xes") or word.endswith("ches") or word.endswith("shes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


SIZE_TOKEN = re.compile(r"^\d+(?:\.\d+)?\s*[a-z]{0,4}$")

QUALIFIER_TOKENS = {
    "whole", "free", "range", "free-range", "organic", "british", "greek", "plain",
    "natural", "low", "reduced", "full", "semi", "skimmed", "skim", "large", "small",
    "medium", "boneless", "skinless", "ripe", "fresh", "frozen", "canned", "tinned",
    "dried", "sweetened", "unsweetened", "raw", "cooked", "roasted", "grilled",
    "smoked", "salted", "unsalted", "premium", "finest", "classic", "virgin", "extra",
}


def canonicalize_name(raw: str) -> str:
    text = strip_accents((raw or "").strip().lower())
    text = re.sub(r"[^a-z0-9\s\-&/']", " ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    tokens = [token for token in text.split() if not SIZE_TOKEN.match(token)]
    while tokens and tokens[0] in QUALIFIER_TOKENS:
        tokens.pop(0)
    text = " ".join(tokens)
    for _ in range(3):
        stripped = LEADING_NOISE.sub("", text)
        stripped = CONTAINER_PHRASE.sub("", stripped)
        if stripped == text:
            break
        text = stripped.strip()
    text = CONTAINER_SUFFIX.sub("", text)
    tokens = [token for token in text.split() if token not in BRAND_TOKENS]
    tokens = [token for token in tokens if token not in {"pack", "packs", "pkg", "pkgs"}]
    if tokens:
        text = " ".join(tokens)
    tokens = text.split()
    if len(tokens) > 1 and tokens[0].isdigit():
        text = " ".join(tokens[1:])
    if text in SYNONYMS:
        return SYNONYMS[text]
    if text in EXTRA_SYNONYMS:
        return EXTRA_SYNONYMS[text]
    words = text.split()
    if len(words) > 1 and " ".join(words) in SYNONYMS:
        return SYNONYMS[" ".join(words)]
    if len(words) > 1 and " ".join(words) in EXTRA_SYNONYMS:
        return EXTRA_SYNONYMS[" ".join(words)]
    head = singularize(words[0])
    rest = words[1:]
    for index, word in enumerate(rest):
        rest[index] = singularize(word)
    candidate = " ".join([head] + rest)
    if candidate in SYNONYMS:
        return SYNONYMS[candidate]
    if candidate in EXTRA_SYNONYMS:
        return EXTRA_SYNONYMS[candidate]
    if head in PLURAL_EXCEPTIONS and len(words) == 1:
        return PLURAL_EXCEPTIONS[head]
    return candidate


LEADING_NOISE = re.compile(
    r"^(?:(?:unopened|opened|sealed|unsealed|empty|full|glass|plastic|metal|cold|fresh|leftover|homemade|store|bought)\s+)+"
)
CONTAINER_PHRASE = re.compile(
    r"^(?:jar|bottle|can|tub|container|pack|bag|pouch|carton|box|cup|bowl|loaf|slice|piece|half)\s+(?:of|with|holding|containing)\s+"
)
CONTAINER_SUFFIX = re.compile(r"\s+(?:jar|bottle|can|tub|container|pack|bag|pouch|carton|box)$")
PAREN = re.compile(r"\([^)]*\)")
BRACKET = re.compile(r"\[[^\]]*\]")

REJECT_WORDS = {
    "unspecified", "unrecognizable", "unrecognisable", "unanswerable", "unknown", "unidentified",
    "nonsense", "inference", "possibly", "maybe", "none", "nothing", "various", "several",
    "item", "items", "food", "foods", "stuff", "things", "thing", "object", "objects",
    "beverage", "beverages", "drink", "drinks", "liquid", "product", "products", "meal",
    "leftovers", "leftover", "dish", "dishes", "container", "bottle", "jar", "can", "box",
    "bag", "tube", "packet", "sauce", "condiment", "canned", "frozen", "dried", "fresh",
    "cooked", "raw", "mixed", "assorted", "no", "not", "taste", "love", "spice",
    "spices", "seasoning", "canister", "pack", "bundle", "portion", "serve", "serving",
}

REJECT_PHRASES = {"...", "", "-", "n a"}


def clean_name(raw: str) -> str:
    text = (raw or "").strip().lower()
    text = PAREN.sub(" ", text)
    text = BRACKET.sub(" ", text)
    text = text.split(",")[0]
    text = re.sub(r"[^a-z0-9\s\-&/']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    for _ in range(3):
        stripped = LEADING_NOISE.sub("", text)
        stripped = CONTAINER_PHRASE.sub("", stripped)
        if stripped == text:
            break
        text = stripped.strip()
    text = CONTAINER_SUFFIX.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text in REJECT_PHRASES:
        return ""
    tokens = [token for token in text.split() if token not in BRAND_TOKENS]
    if tokens:
        text = " ".join(tokens)
    return text.strip()


STOPWORDS = {
    "or", "and", "with", "of", "in", "on", "at", "from", "a", "an", "the", "is", "are",
    "some", "that", "this", "it", "its", "there", "they", "you", "we", "my", "our",
    "sort", "kind", "type", "thing",
}

PHRASE_CATEGORIES = {
    "ice cream": "snack",
    "frozen yogurt": "snack",
    "ice lolly": "snack",
    "orange juice": "beverage",
    "apple juice": "beverage",
    "olive oil": "pantry_staple",
    "coconut milk": "pantry_staple",
    "soy sauce": "condiment",
    "tomato ketchup": "condiment",
    "salad dressing": "condiment",
    "sour cream": "dairy",
    "cream cheese": "dairy",
    "cottage cheese": "dairy",
    "peanut butter": "pantry_staple",
    "almond milk": "beverage",
    "oat milk": "beverage",
}


def is_specific_name(name: str) -> bool:
    cleaned = (name or "").strip()
    if not cleaned:
        return False
    words = cleaned.split()
    if len(words) == 1 and words[0] in COLOR_ONLY:
        return False
    if "/" in cleaned:
        return False
    if any(word in DESCRIPTOR_WORDS for word in words):
        return False
    if any(word.endswith("-based") or word.endswith("-like") for word in words):
        return False
    meaningful = [word for word in words if word not in REJECT_WORDS and word not in STOPWORDS]
    if not meaningful:
        return False
    if len(meaningful) == 1 and meaningful[0] in {"dairy", "produce", "protein", "snack", "drink", "beverage", "citrus"}:
        return False
    return True


def canonicalize_unit(raw: str) -> str:
    text = strip_accents((raw or "").strip().lower())
    text = re.sub(r"[^a-z]", "", text)
    if not text:
        return "piece"
    if text in UNIT_SYNONYMS:
        return UNIT_SYNONYMS[text]
    if text in UNIT_FAMILIES:
        return text
    if text.endswith("s") and text[:-1] in UNIT_FAMILIES:
        return text[:-1]
    return "piece"


def unit_family(unit: str) -> str:
    return UNIT_FAMILIES.get(unit, {unit})


def units_compatible(a: str, b: str) -> bool:
    left, right = canonicalize_unit(a), canonicalize_unit(b)
    return right in unit_family(left) or left in unit_family(right)


def infer_category(name: str, stated: str | None = None) -> str:
    stated = (stated or "").strip().lower()
    if stated in CATEGORIES:
        return stated
    haystack = name.lower()
    for phrase, category in PHRASE_CATEGORIES.items():
        if phrase in haystack:
            return category
    for category, keywords in CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in haystack:
                return category
    return "other"


def category_rank(category: str) -> int:
    try:
        return CATEGORY_ORDER.index(category)
    except ValueError:
        return len(CATEGORY_ORDER)


def normalize_item(raw: dict) -> dict | None:
    name = (raw.get("name") or raw.get("item") or raw.get("label") or "").strip()
    canonical = canonicalize_name(name)
    if not canonical:
        return None
    qty = raw.get("qty", raw.get("quantity", 1))
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        qty = 1.0
    if qty <= 0:
        qty = 1.0
    unit = canonicalize_unit(str(raw.get("unit") or "piece"))
    category = infer_category(canonical, raw.get("category"))
    confidence = raw.get("confidence", raw.get("score", 0.6))
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.6
    confidence = max(0.0, min(1.0, confidence))
    return {
        "name": name.lower() or canonical,
        "canonical": canonical,
        "qty": qty,
        "unit": unit,
        "category": category,
        "confidence": confidence,
    }
