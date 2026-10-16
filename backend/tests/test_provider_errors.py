import pytest
from app.services.vision_provider import ProviderAnalysisError, VisionProvider


class FakeResponse:
    def __init__(self, output_text):
        self.output_text = output_text


class FakeClient:
    output_text = "{}"
    last_request = None

    def __init__(self, **_kwargs):
        del _kwargs
        self.responses = self

    def create(self, **kwargs):
        type(self).last_request = kwargs
        if isinstance(self.output_text, Exception):
            raise self.output_text
        return FakeResponse(self.output_text)


def configure_provider(monkeypatch, output_text):
    monkeypatch.setattr("app.services.vision_provider.OpenAI", FakeClient)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_VISION_MODEL", "test-vision-model")
    FakeClient.output_text = output_text
    FakeClient.last_request = None


def test_provider_failure_does_not_return_empty_clean_label(monkeypatch):
    configure_provider(monkeypatch, TimeoutError("private provider detail"))
    with pytest.raises(ProviderAnalysisError, match="could not analyze"):
        VisionProvider().extract(b"image", "image/jpeg")


def test_malformed_provider_json_is_an_error(monkeypatch):
    configure_provider(monkeypatch, "not json")
    with pytest.raises(ProviderAnalysisError):
        VisionProvider().extract(b"image", "image/jpeg")


def test_empty_provider_output_is_an_error(monkeypatch):
    configure_provider(monkeypatch, "")
    with pytest.raises(ProviderAnalysisError):
        VisionProvider().extract(b"image", "image/jpeg")


def test_provider_assesses_image_quality_and_preserves_uncertain_visible_text(monkeypatch):
    configure_provider(monkeypatch, (
        '{"image_quality":"limited","image_issues":["curved_surface","blurry"],'
        '"ingredients_status":"partially_readable",'
        '"ingredients":[{"name":"milk","source_text":"Milk powd…","status":"partially_readable","confidence":0.54}],'
        '"allergen_statement":{"source_text":"Contains mil…","status":"partially_readable","confidence":0.5},'
        '"full_text":"Milk powd…"}'
    ))

    label = VisionProvider().extract(b"image", "image/jpeg")
    prompt = FakeClient.last_request["input"][0]["content"][0]["text"]

    assert label.image_quality.value == "limited"
    assert [issue.value for issue in label.image_issues] == ["curved_surface", "blurry"]
    assert label.ingredients[0].source_text == "Milk powd…"
    assert label.ingredients[0].status.value == "partially_readable"
    assert "do not infer that an ingredient or allergen is absent" in prompt.lower()
    assert "without completing or inferring the missing text" in prompt.lower()
    assert "every populated value must be directly supported" in prompt.lower()
    assert "distinguish unreadable from not_found_in_image" in prompt.lower()
