from io import BytesIO

import pytest
from PIL import Image

from src.accessable_ai.gemini_client import GeminiResponseError
from src.accessable_ai.image_validation import ImageValidationError
from src.accessable_ai import assessment_service


def make_png_bytes():
    buffer = BytesIO()
    image = Image.new("RGB", (128, 128), color="blue")
    image.save(buffer, format="PNG")
    image.close()
    return buffer.getvalue()


def valid_assessment():
    return {
        "potential_barriers": [],
        "visible_features": [],
        "limitations": [
            "A photograph cannot establish overall accessibility."
        ],
        "recommended_checks": [
            "Check the entrance on site."
        ],
    }


def test_valid_image_is_normalized_and_analyzed(monkeypatch):
    original_image = make_png_bytes()
    fake_client = object()
    factory_calls = []
    analysis_calls = []

    def fake_client_factory(api_key):
        factory_calls.append(api_key)
        return fake_client

    def fake_analyze_image(client, image_bytes, mime_type):
        analysis_calls.append((client, image_bytes, mime_type))
        return valid_assessment()

    monkeypatch.setattr(
        assessment_service,
        "analyze_image",
        fake_analyze_image,
        raising=False,
    )

    result = assessment_service.assess_image(
        original_image,
        "test-api-key",
        client_factory=fake_client_factory,
    )

    assert result == valid_assessment()
    assert factory_calls == ["test-api-key"]
    assert len(analysis_calls) == 1

    client, normalized_bytes, mime_type = analysis_calls[0]
    assert client is fake_client
    assert normalized_bytes.startswith(b"\xff\xd8")
    assert mime_type == "image/jpeg"


def test_invalid_image_is_rejected_before_client_creation():
    factory_calls = []

    def fake_client_factory(api_key):
        factory_calls.append(api_key)
        return object()

    with pytest.raises(ImageValidationError):
        assessment_service.assess_image(
            b"not an image",
            "test-api-key",
            client_factory=fake_client_factory,
        )

    assert factory_calls == []


def test_sanitized_gemini_error_propagates(monkeypatch):
    fake_client = object()
    expected_error = GeminiResponseError(
        "The Gemini service could not complete the request."
    )

    def fake_analyze_image(client, image_bytes, mime_type):
        raise expected_error

    monkeypatch.setattr(
        assessment_service,
        "analyze_image",
        fake_analyze_image,
        raising=False,
    )

    with pytest.raises(GeminiResponseError) as caught:
        assessment_service.assess_image(
            make_png_bytes(),
            "test-api-key",
            client_factory=lambda api_key: fake_client,
        )

    assert caught.value is expected_error
    assert "private provider diagnostic" not in str(caught.value)

def test_missing_api_key_is_rejected_without_client_creation():
    factory_calls = []

    def fake_client_factory(api_key):
        factory_calls.append(api_key)
        return object()

    with pytest.raises(ValueError, match="A Gemini API key is required"):
        assessment_service.assess_image(
            make_png_bytes(),
            "   ",
            client_factory=fake_client_factory,
        )

    assert factory_calls == []


def test_client_is_created_only_after_image_validation(monkeypatch):
    events = []
    fake_client = object()

    def fake_client_factory(api_key):
        events.append("client")
        return fake_client

    def fake_analyze_image(client, image_bytes, mime_type):
        events.append("analysis")
        assert client is fake_client
        assert image_bytes
        assert mime_type in ("image/jpeg", "image/png")
        return valid_assessment()

    monkeypatch.setattr(
        assessment_service,
        "analyze_image",
        fake_analyze_image,
    )

    result = assessment_service.assess_image(
        make_png_bytes(),
        "test-api-key",
        client_factory=fake_client_factory,
    )

    assert events == ["client", "analysis"]
    assert result == valid_assessment()


def test_service_returns_analyzer_result_without_modification(monkeypatch):
    expected = {
        "potential_barriers": [
            {
                "observation": "A possible step at the entrance",
                "visible_evidence": "A raised edge is visible in the photograph.",
                "confidence": "medium",
            }
        ],
        "visible_features": [],
        "limitations": ["The photograph cannot establish full accessibility."],
        "recommended_checks": ["Verify the entrance on site."],
    }

    monkeypatch.setattr(
        assessment_service,
        "analyze_image",
        lambda client, image_bytes, mime_type: expected,
    )

    result = assessment_service.assess_image(
        make_png_bytes(),
        "test-api-key",
        client_factory=lambda api_key: object(),
    )

    assert result is expected
