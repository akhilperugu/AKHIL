from app.schemas.comparison import DietaryProfile, FindingStatus, NutrientThreshold
from app.schemas.label import DataStatus, ImageIssue, ImageQuality, Ingredient, LabelData, LabelField, NutritionFact
from app.services.comparison_engine import compare_label


def test_exact_restricted_ingredient_has_quoted_evidence():
    label = LabelData(ingredients_status=DataStatus.VISIBLE, ingredients=[Ingredient(name="milk", source_text="Whole milk powder")])
    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]
    assert finding.status == FindingStatus.CONFLICT_DETECTED
    assert finding.evidence[0].source_text == "Whole milk powder"


def test_allergen_synonym_is_transparent():
    label = LabelData(ingredients_status=DataStatus.VISIBLE, ingredients=[Ingredient(name="whey", source_text="Whey protein")])
    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]
    assert finding.status == FindingStatus.POTENTIAL_CONFLICT
    assert "synonym" in finding.evidence[0].explanation


def test_may_contain_is_potential_cross_contact():
    label = LabelData(allergen_statement=LabelField(value="May contain peanuts", source_text="May contain peanuts", status=DataStatus.VISIBLE))
    finding = compare_label(label, DietaryProfile(allergens=["peanuts"]))[0]
    assert finding.status == FindingStatus.POTENTIAL_CONFLICT
    assert "May contain peanuts" in finding.evidence[0].source_text


def test_cross_contact_match_requires_target_in_same_precautionary_statement():
    label = LabelData(
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="sesame", source_text="Sesame seeds")],
        allergen_statement=LabelField(value="May contain peanuts", source_text="May contain peanuts", status=DataStatus.VISIBLE),
        full_text="Ingredients: Sesame seeds. May contain peanuts.",
    )
    finding = compare_label(label, DietaryProfile(allergens=["tree nuts"]))[0]
    assert finding.status == FindingStatus.NO_CONFLICT_FOUND


def test_allergen_declaration_is_evidence_even_if_not_in_ingredients():
    label = LabelData(allergen_statement=LabelField(value="Contains milk", source_text="Contains milk", status=DataStatus.VISIBLE))
    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]
    assert finding.status == FindingStatus.CONFLICT_DETECTED
    assert finding.evidence[0].field == "allergen_statement"


def test_missing_ingredient_list_is_not_clean_bill_of_health():
    finding = compare_label(LabelData(), DietaryProfile(allergens=["milk"]))[0]
    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION
    assert not finding.evidence


def test_complete_visible_list_can_only_report_no_match_not_safety():
    label = LabelData(
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="salt", source_text="Salt")],
        allergen_statement=LabelField(status=DataStatus.NOT_FOUND_IN_IMAGE),
        full_text="Ingredients: Salt",
    )
    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]
    assert finding.status == FindingStatus.NO_CONFLICT_FOUND
    assert "does not establish" in finding.uncertainty


def test_missing_full_transcription_never_counts_as_absence_from_visible_rows():
    label = LabelData(
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="salt", source_text="Salt")],
    )

    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]

    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION
    assert finding.evidence == []
    assert "Missing OCR text is not evidence" in finding.uncertainty


def test_unreadable_allergen_statement_is_not_treated_as_a_clear_review():
    label = LabelData(
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="salt", source_text="Salt")],
        allergen_statement=LabelField(source_text="May contain milk", status=DataStatus.PARTIALLY_READABLE),
        full_text="Ingredients: Salt. May contain milk",
    )

    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]

    assert finding.status == FindingStatus.POTENTIAL_CONFLICT
    assert finding.evidence[0].source_text == "May contain milk"


def test_ingredient_conflicts_are_downgraded_when_source_and_transcription_disagree():
    label = LabelData(
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="milk", source_text="Milk powder")],
        full_text="Ingredients: Salt",
    )

    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]

    assert finding.status == FindingStatus.POTENTIAL_CONFLICT
    assert finding.evidence[0].source_text == "Milk powder"
    assert finding.uncertainty


def test_partial_ingredient_list_is_insufficient():
    label = LabelData(ingredients_status=DataStatus.PARTIALLY_READABLE)
    assert compare_label(label, DietaryProfile(allergens=["milk"]))[0].status == FindingStatus.INSUFFICIENT_INFORMATION


def test_ingredient_not_detected_is_not_reported_as_explicitly_absent_when_unreadable():
    label = LabelData(ingredients_status=DataStatus.UNREADABLE)
    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]
    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION
    assert "could not be fully assessed" in finding.summary


def test_blurry_curved_or_obscured_image_cannot_produce_a_no_match_result():
    label = LabelData(
        image_quality=ImageQuality.LIMITED,
        image_issues=[ImageIssue.BLURRY, ImageIssue.CURVED_SURFACE, ImageIssue.PARTIALLY_OBSCURED],
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="salt", source_text="Salt")],
    )

    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]

    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION
    assert "No milk match" not in finding.summary
    assert "blurry, curved surface, partially obscured" in finding.uncertainty
    assert "Retake the photo" in finding.uncertainty


def test_unreadable_image_uses_insufficient_information_even_if_list_is_empty():
    label = LabelData(image_quality=ImageQuality.UNREADABLE, ingredients_status=DataStatus.VISIBLE)

    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]

    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION
    assert finding.evidence == []
    assert "manually confirm" in finding.uncertainty


def test_low_confidence_ingredient_match_is_not_presented_as_confirmed():
    label = LabelData(
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="milk", source_text="Milk powder", confidence=0.42)],
    )

    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]

    assert finding.status == FindingStatus.POTENTIAL_CONFLICT
    assert finding.evidence[0].source_text == "Milk powder"
    assert finding.uncertainty


def test_missing_ingredient_source_text_is_neither_evidence_nor_proof_of_absence():
    label = LabelData(
        ingredients_status=DataStatus.VISIBLE,
        ingredients=[Ingredient(name="milk", source_text="", status=DataStatus.VISIBLE)],
    )

    finding = compare_label(label, DietaryProfile(allergens=["milk"]))[0]

    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION
    assert finding.evidence == []


def test_nutrition_without_exact_source_text_cannot_be_confirmed():
    label = LabelData(nutrition=[
        NutritionFact(nutrient="Sugar", value=4, unit="g", basis="per serving", status=DataStatus.VISIBLE),
    ])
    threshold = NutrientThreshold(nutrient="Sugar", direction="maximum", value=10, unit="g")

    finding = compare_label(label, DietaryProfile(nutrition_thresholds=[threshold]))[0]

    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION
    assert finding.evidence == []
    assert "exact label wording" in finding.summary


def test_corrected_extraction_is_used_for_new_comparison():
    corrected = LabelData(ingredients_status=DataStatus.VISIBLE, ingredients=[Ingredient(name="milk", source_text="Milk powder")])
    finding = compare_label(corrected, DietaryProfile(allergens=["milk"]))[0]
    assert finding.status == FindingStatus.CONFLICT_DETECTED
    assert finding.evidence[0].source_text == "Milk powder"


def test_gelatin_source_is_not_inferred():
    label = LabelData(ingredients_status=DataStatus.VISIBLE, ingredients=[Ingredient(name="gelatin", source_text="Gelatin")])
    finding = compare_label(label, DietaryProfile(dietary_patterns=["vegan"]))[0]
    assert finding.status == FindingStatus.POTENTIAL_CONFLICT
    assert "source" in finding.uncertainty


def test_vegan_profile_flags_visible_milk_without_claiming_certainty():
    label = LabelData(ingredients_status=DataStatus.VISIBLE, ingredients=[Ingredient(name="milk", source_text="Milk powder")])
    finding = compare_label(label, DietaryProfile(dietary_patterns=["vegan"]))[0]
    assert finding.status == FindingStatus.POTENTIAL_CONFLICT
    assert finding.evidence[0].source_text == "Milk powder"


def test_threshold_compares_compatible_basis():
    label = LabelData(nutrition=[NutritionFact(nutrient="Sugar", value=12, unit="g", basis="per serving", source_text="Sugar 12 g per serving", status=DataStatus.VISIBLE)])
    threshold = NutrientThreshold(nutrient="Sugar", direction="maximum", value=10, unit="g", basis="per serving")
    assert compare_label(label, DietaryProfile(nutrition_thresholds=[threshold]))[0].status == FindingStatus.POTENTIAL_CONFLICT


def test_threshold_rejects_incompatible_basis():
    label = LabelData(nutrition=[NutritionFact(nutrient="Sugar", value=12, unit="g", basis="per 100 g", source_text="Sugar 12 g per 100 g", status=DataStatus.VISIBLE)])
    threshold = NutrientThreshold(nutrient="Sugar", direction="maximum", value=10, unit="g", basis="per serving")
    finding = compare_label(label, DietaryProfile(nutrition_thresholds=[threshold]))[0]
    assert finding.status == FindingStatus.INSUFFICIENT_INFORMATION


def test_missing_nutrition_value_is_unknown():
    threshold = NutrientThreshold(nutrient="Protein", direction="minimum", value=5, unit="g")
    assert compare_label(LabelData(), DietaryProfile(nutrition_thresholds=[threshold]))[0].status == FindingStatus.UNKNOWN
