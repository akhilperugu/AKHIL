import re
from app.schemas.label import DataStatus, LabelData, LabelField

INGREDIENT_ALIASES = {
    "soya": "soy", "soybean": "soy", "groundnut": "peanuts", "groundnuts": "peanuts",
    "arachis": "peanuts", "albumen": "egg", "egg albumin": "egg", "caseinate": "milk protein",
}
NUTRIENT_ALIASES = {"sugars": "sugar", "salt": "sodium", "saturated fats": "saturated fat"}
NUTRIENT_SOURCE_TERMS = {
    "sugar": ("sugar", "sugars", "total sugar", "total sugars"),
    "sodium": ("sodium", "salt"),
    "saturated fat": ("saturated fat", "saturated fats"),
}
UNIT_ALIASES = {
    "gram": "g", "grams": "g", "milligram": "mg", "milligrams": "mg",
    "kilocalorie": "kcal", "kilocalories": "kcal", "microgram": "mcg", "micrograms": "mcg",
}


def _quoted_unit(unit: str, source_text: str) -> bool:
    spellings = {
        "g": ("g", "gram", "grams"),
        "mg": ("mg", "milligram", "milligrams"),
        "kcal": ("kcal", "kilocalorie", "kilocalories"),
        "mcg": ("mcg", "microgram", "micrograms", "μg", "µg"),
    }.get(unit.lower(), (unit,))
    return any(
        re.search(r"(?<![a-z])" + re.escape(spelling) + r"(?![a-z])", source_text, re.IGNORECASE)
        for spelling in spellings
    )


def _quoted_value(value: float, source_text: str) -> bool:
    for token in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w.])", source_text):
        try:
            parsed = float(token.replace(",", "."))
            if "," in token and re.fullmatch(r"\d{1,3}(?:,\d{3})+", token):
                parsed = float(token.replace(",", ""))
            if abs(parsed - value) < 1e-9:
                return True
        except ValueError:
            continue
    return False


def _quoted_term(term: str, source_text: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", source_text, re.IGNORECASE) is not None


def normalize_label(label: LabelData) -> LabelData:
    ingredients = []
    full_text = re.sub(r"\s+", " ", label.full_text).strip().casefold()
    for item in label.ingredients:
        key = (item.normalized_name or item.name).strip().lower()
        normalized = INGREDIENT_ALIASES.get(key, item.normalized_name or item.name.strip())
        status = item.status
        source_text = re.sub(r"\s+", " ", item.source_text).strip().casefold()
        if source_text and full_text and source_text not in full_text and status == DataStatus.VISIBLE:
            status = DataStatus.PARTIALLY_READABLE
        elif not source_text and status == DataStatus.VISIBLE:
            status = DataStatus.UNKNOWN
        ingredients.append(item.model_copy(update={"normalized_name": normalized, "status": status}))

    def normalize_field(field: LabelField) -> LabelField:
        source_text = re.sub(r"\s+", " ", field.source_text or "").strip().casefold()
        status = field.status
        if status == DataStatus.VISIBLE and not source_text:
            status = DataStatus.UNKNOWN
        elif status == DataStatus.VISIBLE and full_text and source_text not in full_text:
            status = DataStatus.PARTIALLY_READABLE
        return field.model_copy(update={"status": status})

    product_name = normalize_field(label.product_name)
    serving_size = normalize_field(label.serving_size)
    dietary_claims = [normalize_field(item) for item in label.dietary_claims]
    certifications = [normalize_field(item) for item in label.certifications]

    nutrition = []
    unsupported_nutrition = False
    for item in label.nutrition:
        nutrient_key = item.nutrient.strip().lower()
        unit_key = (item.unit or "").strip().lower()
        normalized_unit = UNIT_ALIASES.get(unit_key, item.unit)
        source_text = re.sub(r"\s+", " ", item.source_text or "").strip().casefold()
        status = item.status
        if status == DataStatus.VISIBLE and not source_text:
            status = DataStatus.UNKNOWN
            unsupported_nutrition = True
        elif status == DataStatus.VISIBLE and (
            item.value is None or not normalized_unit
            or not any(_quoted_term(term, source_text) for term in NUTRIENT_SOURCE_TERMS.get(
                NUTRIENT_ALIASES.get(nutrient_key, nutrient_key), (NUTRIENT_ALIASES.get(nutrient_key, nutrient_key),)
            ))
            or not _quoted_value(item.value, source_text)
            or not _quoted_unit(normalized_unit, source_text)
            or (item.basis and not (
                _quoted_term(item.basis.strip().lower(), source_text)
                or _quoted_term(item.basis.strip().lower(), full_text)
            ))
            or (full_text and source_text not in full_text)
        ):
            status = DataStatus.PARTIALLY_READABLE
            unsupported_nutrition = True
        nutrition.append(item.model_copy(update={
            "nutrient": NUTRIENT_ALIASES.get(nutrient_key, item.nutrient),
            "unit": normalized_unit,
            "status": status,
        }))
    warnings = list(label.extraction_warnings)
    if not label.full_text.strip():
        warning = "No full-label transcription was returned; missing wording cannot be treated as absent."
        if warning not in warnings:
            warnings.append(warning)
    if any(not item.source_text.strip() for item in label.ingredients):
        warning = "An extracted ingredient has no exact source wording and needs manual confirmation."
        if warning not in warnings:
            warnings.append(warning)
    if any(item.status == DataStatus.PARTIALLY_READABLE and original.status == DataStatus.VISIBLE
           for item, original in zip(ingredients, label.ingredients)):
        warning = "An ingredient reading does not match the full transcription and needs manual confirmation."
        if warning not in warnings:
            warnings.append(warning)
    if unsupported_nutrition:
        warning = "One or more nutrition values could not be verified against exact source wording and need manual confirmation."
        if warning not in warnings:
            warnings.append(warning)
    if any(
        normalized.status != original.status and original.status == DataStatus.VISIBLE
        for normalized, original in [
            (product_name, label.product_name),
            (serving_size, label.serving_size),
            *zip(dietary_claims, label.dietary_claims),
            *zip(certifications, label.certifications),
        ]
    ):
        warning = "One or more label fields lack matching exact source wording and need manual confirmation."
        if warning not in warnings:
            warnings.append(warning)
    allergen_statement = label.allergen_statement
    allergen_text = re.sub(r"\s+", " ", allergen_statement.source_text or "").strip().casefold()
    if allergen_statement.status == DataStatus.VISIBLE and not allergen_text:
        allergen_statement = allergen_statement.model_copy(update={"status": DataStatus.UNKNOWN})
    elif allergen_statement.status == DataStatus.VISIBLE and allergen_text and full_text and allergen_text not in full_text:
        allergen_statement = allergen_statement.model_copy(update={"status": DataStatus.PARTIALLY_READABLE})
    if allergen_statement.status != label.allergen_statement.status:
        warning = "The allergen statement is missing exact source wording or does not match the full transcription; confirm it manually."
        if warning not in warnings:
            warnings.append(warning)
    ingredients_status = label.ingredients_status
    if ingredients_status == DataStatus.VISIBLE and any(item.status != DataStatus.VISIBLE for item in ingredients):
        ingredients_status = DataStatus.PARTIALLY_READABLE
    return label.model_copy(update={
        "product_name": product_name,
        "ingredients": ingredients,
        "ingredients_status": ingredients_status,
        "allergen_statement": allergen_statement,
        "nutrition": nutrition,
        "serving_size": serving_size,
        "dietary_claims": dietary_claims,
        "certifications": certifications,
        "extraction_warnings": warnings,
    })
