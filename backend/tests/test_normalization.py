from app.schemas.label import DataStatus, Ingredient, LabelData, LabelField, NutritionFact
from app.services.normalization_service import normalize_label


def test_normalization_preserves_original_ingredient_and_nutrition_source():
    label = LabelData(
        ingredients=[Ingredient(name="Soya", source_text="Soya flour")],
        nutrition=[NutritionFact(nutrient="Sugars", value=4, unit="grams", basis="per serving", source_text="Sugars 4 grams per serving")],
    )
    result = normalize_label(label)
    assert result.ingredients[0].source_text == "Soya flour"
    assert result.ingredients[0].normalized_name == "soy"
    assert result.nutrition[0].nutrient == "sugar"
    assert result.nutrition[0].unit == "g"
    assert result.nutrition[0].source_text == "Sugars 4 grams per serving"


def test_missing_full_transcription_is_flagged_without_fabricating_text():
    result = normalize_label(LabelData())

    assert result.full_text == ""
    assert any("missing wording cannot be treated as absent" in warning for warning in result.extraction_warnings)


def test_ingredient_without_visible_source_text_is_flagged_for_confirmation():
    label = LabelData(ingredients=[Ingredient(name="milk", source_text="")])

    result = normalize_label(label)

    assert result.ingredients[0].source_text == ""
    assert any("no exact source wording" in warning for warning in result.extraction_warnings)


def test_ingredient_missing_from_full_transcription_is_marked_uncertain():
    label = LabelData(
        ingredients_status="visible",
        ingredients=[Ingredient(name="milk", source_text="Milk powder", status="visible")],
        full_text="Ingredients: Salt",
    )

    result = normalize_label(label)

    assert result.ingredients[0].status.value == "partially_readable"
    assert result.ingredients_status.value == "partially_readable"
    assert any("does not match the full transcription" in warning for warning in result.extraction_warnings)


def test_allergen_statement_without_source_text_is_not_left_confirmed():
    label = LabelData(allergen_statement=LabelField(status=DataStatus.VISIBLE))

    result = normalize_label(label)

    assert result.allergen_statement.status == DataStatus.UNKNOWN
    assert any("allergen statement is missing exact source wording" in warning for warning in result.extraction_warnings)


def test_nutrition_value_not_present_in_quote_is_marked_for_confirmation():
    label = LabelData(
        nutrition=[NutritionFact(
            nutrient="Sugar", value=40, unit="g", basis="per serving",
            source_text="Sugar 4 g per serving", status=DataStatus.VISIBLE,
        )],
    )

    result = normalize_label(label)

    assert result.nutrition[0].value == 40
    assert result.nutrition[0].source_text == "Sugar 4 g per serving"
    assert result.nutrition[0].status == DataStatus.PARTIALLY_READABLE
    assert any("could not be verified against exact source wording" in warning for warning in result.extraction_warnings)


def test_nutrition_field_and_basis_must_be_supported_by_label_text():
    label = LabelData(
        nutrition=[NutritionFact(
            nutrient="Sugar", value=4, unit="g", basis="per serving",
            source_text="Protein 4 g", status=DataStatus.VISIBLE,
        )],
    )

    result = normalize_label(label)

    assert result.nutrition[0].status == DataStatus.PARTIALLY_READABLE


def test_visible_product_and_claim_fields_need_exact_source_text():
    label = LabelData(
        product_name=LabelField(value="Oat Bites", status=DataStatus.VISIBLE),
        dietary_claims=[LabelField(value="Gluten free", status=DataStatus.VISIBLE)],
    )

    result = normalize_label(label)

    assert result.product_name.status == DataStatus.UNKNOWN
    assert result.dietary_claims[0].status == DataStatus.UNKNOWN
    assert any("lack matching exact source wording" in warning for warning in result.extraction_warnings)
