from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_does_not_expose_provider_configuration_details():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "provider_configured", "max_upload_mb"}


def test_compare_endpoint_reuses_extracted_data_without_provider():
    response = client.post("/api/compare", json={
        "label": {
            "ingredients_status": "visible",
            "ingredients": [{"name": "milk", "source_text": "Milk powder", "status": "visible"}],
        },
        "profile": {"allergens": ["milk"]},
    })
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["status"] == "conflict_detected"
    assert finding["evidence"][0]["source_text"] == "Milk powder"


def test_compare_endpoint_rejects_malformed_label_data():
    response = client.post("/api/compare", json={"label": {"ingredients": "not a list"}, "profile": {}})
    assert response.status_code == 422


def test_compare_endpoint_keeps_unclear_image_quality_and_flags_missing_ingredient():
    response = client.post("/api/compare", json={
        "label": {
            "image_quality": "limited",
            "image_issues": ["blurry", "curved_surface"],
            "ingredients_status": "visible",
            "ingredients": [{"name": "salt", "source_text": "Salt", "status": "visible"}],
        },
        "profile": {"allergens": ["milk"]},
    })

    assert response.status_code == 200
    body = response.json()
    assert body["label"]["image_issues"] == ["blurry", "curved_surface"]
    finding = body["findings"][0]
    assert finding["status"] == "insufficient_information"
    assert finding["evidence"] == []
    assert "retake" in finding["uncertainty"].lower()


def test_compare_endpoint_downgrades_nutrition_value_not_supported_by_its_quote():
    response = client.post("/api/compare", json={
        "label": {
            "nutrition": [{
                "nutrient": "Sugar", "value": 40, "unit": "g", "basis": "per serving",
                "source_text": "Sugar 4 g per serving", "status": "visible",
            }],
        },
        "profile": {
            "nutrition_thresholds": [{
                "nutrient": "Sugar", "direction": "maximum", "value": 10,
                "unit": "g", "basis": "per serving",
            }],
        },
    })

    assert response.status_code == 200
    body = response.json()
    assert body["label"]["nutrition"][0]["status"] == "partially_readable"
    assert body["findings"][0]["status"] == "insufficient_information"
    assert body["findings"][0]["evidence"][0]["source_text"] == "Sugar 4 g per serving"
