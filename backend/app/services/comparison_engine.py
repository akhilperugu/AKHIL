import re
from app.schemas.comparison import (
    DietaryProfile, Finding, FindingStatus, NutrientThreshold,
    ReasoningType, Severity,
)
from app.schemas.label import DataStatus, ImageQuality, LabelData
from app.services.evidence_service import evidence_for


SYNONYMS = {
    "milk": {"whey", "casein", "caseinate", "milk solids", "lactose", "butter"},
    "peanuts": {"groundnut", "groundnuts", "peanut oil", "arachis"},
    "soy": {"soya", "soybean", "soybeans", "soy lecithin"},
    "wheat": {"wheat flour", "durum", "semolina", "spelt"},
    "eggs": {"albumen", "albumin", "egg white", "egg yolk"},
    "tree nuts": {"almond", "almonds", "cashew", "cashews", "walnut", "hazelnut", "pistachio"},
    "fish": {"anchovy", "anchovies", "fish oil", "cod"},
    "crustaceans": {"shrimp", "prawn", "prawns", "crab", "lobster", "crayfish"},
    "sesame": {"tahini", "sesame oil", "sesame seed"},
    "gluten": {"wheat", "barley", "rye", "malt"},
    "artificial sweeteners": {"sucralose", "aspartame", "saccharin", "acesulfame potassium", "cyclamate", "neotame", "advantame"},
}


def _contains_term(text: str, term: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(term.lower()) + r"(?![a-z])", text.lower()) is not None


def _transcription_contains(source_text: str, full_text: str) -> bool:
    normalize = lambda text: re.sub(r"\s+", " ", text).strip().casefold()
    return normalize(source_text) in normalize(full_text)


def _ingredient_finding(label: LabelData, preference: str) -> Finding:
    terms = [preference.lower(), *sorted(SYNONYMS.get(preference.lower(), set()))]
    for ingredient in label.ingredients:
        text = ingredient.source_text.strip()
        if not text:
            continue
        if ingredient.status in {DataStatus.UNREADABLE, DataStatus.UNKNOWN}:
            continue
        for term in terms:
            if _contains_term(text, term):
                direct = term == preference.lower()
                transcription_supports_text = not label.full_text.strip() or _transcription_contains(text, label.full_text)
                confirmed = (
                    direct
                    and ingredient.status == DataStatus.VISIBLE
                    and (ingredient.confidence is None or ingredient.confidence >= 0.8)
                    and label.image_quality != ImageQuality.UNREADABLE
                    and transcription_supports_text
                )
                return Finding(
                    preference=preference,
                    status=FindingStatus.CONFLICT_DETECTED if confirmed else FindingStatus.POTENTIAL_CONFLICT,
                    severity=Severity.HIGH if confirmed else Severity.MEDIUM,
                    summary=(f"{preference} appears in the visible ingredient list." if direct else f"A possible {preference} synonym appears in the visible ingredient list."),
                    evidence=evidence_for(text, "ingredients", "Direct ingredient match." if direct else f"Matched curated synonym '{term}' for {preference}."),
                    reasoning_type=ReasoningType.DIRECT_MATCH if direct else ReasoningType.SYNONYM_MATCH,
                    uncertainty=None if confirmed else "This match is based on a curated synonym or partially readable ingredient text and should be confirmed against the package.",
                )

    declaration = label.allergen_statement.source_text or ""
    direct_declaration = declaration
    if _contains_term(declaration, "may contain"):
        direct_declaration = next((clause.strip() for clause in re.split(r"[;.!]\s*", declaration)
                                   if _contains_term(clause, "contains") and not _contains_term(clause, "may contain")), "")
    if direct_declaration:
        for term in terms:
            if _contains_term(direct_declaration, term):
                confirmed = (
                    term == preference.lower()
                    and label.allergen_statement.status == DataStatus.VISIBLE
                    and (label.allergen_statement.confidence is None or label.allergen_statement.confidence >= 0.8)
                    and label.image_quality != ImageQuality.UNREADABLE
                    and (
                        not label.full_text.strip()
                        or _transcription_contains(direct_declaration, label.full_text)
                    )
                )
                return Finding(
                    preference=preference,
                    status=FindingStatus.CONFLICT_DETECTED if confirmed else FindingStatus.POTENTIAL_CONFLICT,
                    severity=Severity.HIGH if confirmed else Severity.MEDIUM,
                    summary=f"The allergen statement declares {preference}.",
                    evidence=evidence_for(direct_declaration, "allergen_statement", "The label's allergen declaration names this preference."),
                    reasoning_type=ReasoningType.DIRECT_MATCH if term == preference.lower() else ReasoningType.SYNONYM_MATCH,
                    uncertainty=None if confirmed else "The allergen statement is not fully readable or relies on a curated synonym.",
                )

    precautionary_statements = [
        label.allergen_statement.source_text or "",
        *label.other_visible_text,
        *(line.strip() for line in label.full_text.splitlines()),
    ]
    statement = next((text for text in precautionary_statements
                      if _contains_term(text, "may contain") and any(_contains_term(text, term) for term in terms)), "")
    if statement:
        return Finding(
            preference=preference,
            status=FindingStatus.POTENTIAL_CONFLICT,
            severity=Severity.HIGH,
            summary=f"The label indicates possible cross-contact with {preference}.",
            evidence=evidence_for(statement, "allergen_statement", "Precautionary cross-contact wording, not an ingredient declaration."),
            reasoning_type=ReasoningType.CONTEXTUAL_INTERPRETATION,
            uncertainty="Precautionary statements describe possible exposure and do not confirm an ingredient in the recipe.",
        )

    quality_unclear = label.image_quality in {ImageQuality.LIMITED, ImageQuality.UNREADABLE} or bool(label.image_issues)
    allergen_statement_readable = (
        label.allergen_statement.status == DataStatus.NOT_FOUND_IN_IMAGE
        or (
            label.allergen_statement.status == DataStatus.VISIBLE
            and bool((label.allergen_statement.source_text or "").strip())
            and (
                not label.full_text.strip()
                or _transcription_contains(label.allergen_statement.source_text or "", label.full_text)
            )
        )
    )
    if not quality_unclear and allergen_statement_readable and label.full_text.strip() and label.ingredients_status in {DataStatus.VISIBLE, DataStatus.NOT_FOUND_IN_IMAGE} and label.ingredients and all(
        item.status == DataStatus.VISIBLE
        and item.source_text.strip()
        and _transcription_contains(item.source_text, label.full_text)
        for item in label.ingredients
    ):
        return Finding(
            preference=preference,
            status=FindingStatus.NO_CONFLICT_FOUND,
            severity=Severity.INFORMATIONAL,
            summary=f"No {preference} match was detected in the visible ingredient text.",
            reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE,
            uncertainty="This does not establish that the product is free from this allergen; extraction and cross-contact limits apply.",
        )
    return _unknown_finding(preference, label)


def _unknown_finding(preference: str, label: LabelData) -> Finding:
    image_unclear = label.image_quality in {ImageQuality.LIMITED, ImageQuality.UNREADABLE} or bool(label.image_issues)
    allergen_statement_unclear = (
        label.allergen_statement.status in {DataStatus.PARTIALLY_READABLE, DataStatus.UNREADABLE, DataStatus.UNKNOWN}
        or (label.allergen_statement.status == DataStatus.VISIBLE and not (label.allergen_statement.source_text or "").strip())
    )
    transcription_incomplete = (
        (label.ingredients_status == DataStatus.VISIBLE and bool(label.ingredients) and not label.full_text.strip())
        or any(not item.source_text.strip() for item in label.ingredients)
        or any(
            item.status == DataStatus.VISIBLE and item.source_text.strip()
            and label.full_text.strip() and not _transcription_contains(item.source_text, label.full_text)
            for item in label.ingredients
        )
        or (
            label.allergen_statement.status == DataStatus.VISIBLE
            and bool((label.allergen_statement.source_text or "").strip())
            and label.full_text.strip()
            and not _transcription_contains(label.allergen_statement.source_text or "", label.full_text)
        )
    )
    status = FindingStatus.INSUFFICIENT_INFORMATION if (
        label.ingredients_status in {DataStatus.PARTIALLY_READABLE, DataStatus.UNREADABLE}
        or image_unclear or transcription_incomplete or allergen_statement_unclear
    ) else FindingStatus.UNKNOWN
    if image_unclear:
        issues = ", ".join(issue.value.replace("_", " ") for issue in label.image_issues)
        reason = f"The image may be difficult to read{f' ({issues})' if issues else ''}."
        summary = "Image quality prevents confirming that the full ingredient list was read."
        uncertainty = f"{reason} Retake the photo or manually confirm the complete ingredient list against the package."
    elif label.ingredients_status in {DataStatus.PARTIALLY_READABLE, DataStatus.UNREADABLE}:
        summary = "Ingredients could not be fully assessed from the supplied image."
        uncertainty = "The ingredient list is missing, unreadable, or not confirmed as complete."
    elif transcription_incomplete:
        summary = "No full label transcription is available to verify that the ingredient list is complete."
        uncertainty = "Missing OCR text is not evidence that an ingredient is absent. Request a clearer photo or manually confirm the full list."
    elif allergen_statement_unclear:
        summary = "The allergen statement could not be fully assessed from the supplied image."
        uncertainty = "A missing or unreadable allergen statement cannot rule out precautionary wording. Retake the photo or confirm it on the package."
    else:
        summary = "Ingredients could not be fully assessed from the supplied image."
        uncertainty = "The ingredient list is missing, unreadable, or not confirmed as complete."
    return Finding(
        preference=preference,
        status=status,
        severity=Severity.MEDIUM,
        summary=summary,
        reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE,
        uncertainty=uncertainty,
    )


def _threshold_finding(label: LabelData, threshold: NutrientThreshold) -> Finding:
    fact = next((f for f in label.nutrition if f.nutrient.lower() == threshold.nutrient.lower()), None)
    preference = f"{threshold.direction} {threshold.value:g} {threshold.unit} {threshold.nutrient} {threshold.basis}"
    if fact is None:
        return Finding(preference=preference, status=FindingStatus.UNKNOWN, severity=Severity.LOW,
            summary=f"{threshold.nutrient} could not be assessed from the visible nutrition data.",
            reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE, uncertainty="The nutrient value is missing.")
    if fact.value is None or fact.status != DataStatus.VISIBLE:
        status = FindingStatus.INSUFFICIENT_INFORMATION if fact.status in {DataStatus.PARTIALLY_READABLE, DataStatus.UNREADABLE} else FindingStatus.UNKNOWN
        return Finding(preference=preference, status=status, severity=Severity.LOW,
            summary=f"{threshold.nutrient} could not be assessed reliably from the visible nutrition data.",
            evidence=evidence_for(fact.source_text, "nutrition", "The value is not marked as fully readable."),
            reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE, uncertainty="The nutrient value or unit may be incomplete or unreadable.")
    if not fact.source_text or not fact.source_text.strip():
        return Finding(preference=preference, status=FindingStatus.INSUFFICIENT_INFORMATION, severity=Severity.LOW,
            summary=f"{threshold.nutrient} has no exact label wording to verify.",
            reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE,
            uncertainty="Confirm the value and its serving basis against the original package.")
    if (fact.unit or "").lower() != threshold.unit.lower() or (fact.basis or "").lower() != threshold.basis.lower():
        return Finding(preference=preference, status=FindingStatus.INSUFFICIENT_INFORMATION, severity=Severity.LOW,
            summary=f"{threshold.nutrient} is shown on an incompatible serving basis or unit.",
            evidence=evidence_for(fact.source_text or f"{fact.nutrient} {fact.value:g} {fact.unit or ''}", "nutrition", "Values are compared only when units and serving bases match."),
            reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE,
            uncertainty=f"Label basis is '{fact.basis or 'unknown'}' ({fact.unit or 'unknown'}); preference basis is '{threshold.basis}' ({threshold.unit}).")
    exceeded = fact.value > threshold.value if threshold.direction.value == "maximum" else fact.value < threshold.value
    return Finding(preference=preference,
        status=FindingStatus.POTENTIAL_CONFLICT if exceeded else FindingStatus.NO_CONFLICT_FOUND,
        severity=Severity.MEDIUM if exceeded else Severity.INFORMATIONAL,
        summary=f"{threshold.nutrient} is {fact.value:g} {fact.unit} {fact.basis}.",
        evidence=evidence_for(fact.source_text or f"{fact.nutrient} {fact.value:g} {fact.unit}", "nutrition", "Compared with the user-defined threshold using matching units and serving basis."),
        reasoning_type=ReasoningType.NUTRITION_THRESHOLD,
        uncertainty=None)


def compare_label(label: LabelData, profile: DietaryProfile) -> list[Finding]:
    findings: list[Finding] = []
    restrictions = list(dict.fromkeys([*profile.allergens, *profile.avoid_ingredients]))
    for preference in restrictions:
        findings.append(_ingredient_finding(label, preference))

    for pattern in profile.dietary_patterns:
        gelatin = next((i for i in label.ingredients if _contains_term(i.source_text, "gelatin")), None)
        if gelatin and pattern.lower() in {"vegan", "vegetarian", "jain"}:
            findings.append(Finding(preference=pattern, status=FindingStatus.POTENTIAL_CONFLICT,
                severity=Severity.MEDIUM, summary=f"Gelatin is listed, but its source is not established for {pattern} classification.",
                evidence=evidence_for(gelatin.source_text, "ingredients", "The label wording does not identify the gelatin source."),
                reasoning_type=ReasoningType.CONTEXTUAL_INTERPRETATION,
                uncertainty="Ingredient source and individual dietary rules may vary."))
            continue

        pattern_terms = {
            "vegan": {"milk", "whey", "casein", "egg", "eggs", "honey", "beef", "pork", "chicken", "fish"},
            "vegetarian": {"beef", "pork", "chicken", "meat", "fish", "anchovy"},
        }.get(pattern.lower(), set())
        explicit = next((item for item in label.ingredients if item.status == DataStatus.VISIBLE
                         and any(_contains_term(item.source_text, term) for term in pattern_terms)), None)
        if explicit:
            findings.append(Finding(preference=pattern, status=FindingStatus.POTENTIAL_CONFLICT,
                severity=Severity.MEDIUM, summary=f"An ingredient commonly excluded by {pattern} diets is listed.",
                evidence=evidence_for(explicit.source_text, "ingredients", "This ingredient is commonly incompatible with the selected dietary pattern; individual rules can vary."),
                reasoning_type=ReasoningType.CONTEXTUAL_INTERPRETATION,
                uncertainty="Dietary pattern definitions and individual practice vary."))
            continue

        label_claim = next((claim for claim in [*label.certifications, *label.dietary_claims]
                            if claim.status == DataStatus.VISIBLE and claim.source_text and _contains_term(claim.source_text, pattern)), None)
        if label.ingredients_status == DataStatus.VISIBLE and label_claim:
            findings.append(Finding(preference=pattern, status=FindingStatus.INSUFFICIENT_INFORMATION,
                severity=Severity.LOW, summary=f"The label includes a {pattern} claim, but this image cannot verify its scope or validity.",
                evidence=evidence_for(label_claim.source_text, "certifications" if label_claim in label.certifications else "dietary_claims",
                                      "A visible claim is evidence of label wording, not independent certification verification."),
                reasoning_type=ReasoningType.CERTIFICATION_EVIDENCE,
                uncertainty="Dietary requirements vary by individual practice, ingredient sourcing, and certification standards."))
        else:
            findings.append(Finding(preference=pattern,
                status=FindingStatus.INSUFFICIENT_INFORMATION if (
                    label.ingredients_status in {DataStatus.PARTIALLY_READABLE, DataStatus.UNREADABLE}
                    or label.image_quality in {ImageQuality.LIMITED, ImageQuality.UNREADABLE}
                    or bool(label.image_issues)
                ) else FindingStatus.UNKNOWN,
                severity=Severity.MEDIUM,
                summary=f"The label image cannot establish {pattern} compatibility.",
                reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE,
                uncertainty="Ingredient names alone may not reveal sourcing, processing, or individual dietary rules."))

    for requirement in profile.custom_requirements:
        findings.append(Finding(preference=requirement, status=FindingStatus.UNKNOWN, severity=Severity.LOW,
            summary="Custom dietary requirements are recorded, but this version cannot reliably interpret them automatically.",
            reasoning_type=ReasoningType.INSUFFICIENT_EVIDENCE,
            uncertainty="Review the extracted label text yourself; custom requirements are not treated as a rule-based pass."))

    for threshold in profile.nutrition_thresholds:
        findings.append(_threshold_finding(label, threshold))
    if profile.avoid_palm_oil:
        findings.append(_ingredient_finding(label, "palm oil"))
    if profile.avoid_artificial_sweeteners:
        findings.append(_ingredient_finding(label, "artificial sweeteners"))
    return findings
