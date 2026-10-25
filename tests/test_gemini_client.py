import json
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors, types

from src.accessable_ai.config import MODEL_NAME
from src.accessable_ai.gemini_client import (
    GeminiResponseError,
    analyze_image,
)
from src.accessable_ai.response_schema import ASSESSMENT_SCHEMA


def valid_payload():
    return {
        "potential_barriers": [
            {
                "observation": "A step is visible.",
                "visible_evidence": "The entrance appears raised above the path.",
                "confidence": "medium",
            }
        ],
        "visible_features": [],
        "limitations": ["Exact dimensions cannot be determined from the image."],
        "recommended_checks": ["Measure the entrance height on site."],
    }


class FakeModels:
    def __init__(self, response_text, candidates=None, exception=None):
        self.response_text = response_text
        self.candidates = (
            [SimpleNamespace(finish_reason=types.FinishReason.STOP)]
            if candidates is None
            else candidates
        )
        self.exception = exception
        self.call_args = None

    def generate_content(self, **kwargs):
        self.call_args = kwargs
        if self.exception is not None:
            raise self.exception
        return SimpleNamespace(
            text=self.response_text,
            candidates=self.candidates,
        )


class FakeClient:
    def __init__(self, response_text, candidates=None, exception=None):
        self.models = FakeModels(response_text, candidates, exception)


def test_valid_gemini_response_is_parsed_and_validated():
    client = FakeClient(json.dumps(valid_payload()))

    result = analyze_image(client, b"normalized-image", "image/jpeg")

    assert result["potential_barriers"][0]["confidence"] == "medium"
    assert client.models.call_args["model"] == MODEL_NAME


def test_gemini_request_uses_structured_schema():
    client = FakeClient(json.dumps(valid_payload()))

    analyze_image(client, b"normalized-image", "image/jpeg")

    config = client.models.call_args["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == ASSESSMENT_SCHEMA
    assert config.system_instruction
    assert config.temperature is None


def test_empty_model_response_is_rejected():
    with pytest.raises(GeminiResponseError, match="did not return an assessment"):
        analyze_image(FakeClient(""), b"image", "image/jpeg")


def test_invalid_json_is_rejected():
    with pytest.raises(GeminiResponseError, match="unreadable"):
        analyze_image(FakeClient("{not json"), b"image", "image/jpeg")


def test_invalid_assessment_structure_is_rejected():
    with pytest.raises(GeminiResponseError, match="failed validation"):
        analyze_image(FakeClient('{"unexpected": true}'), b"image", "image/jpeg")


def test_empty_image_is_rejected_before_api_call():
    client = FakeClient(json.dumps(valid_payload()))

    with pytest.raises(ValueError, match="non-empty normalized image"):
        analyze_image(client, b"", "image/jpeg")

    assert client.models.call_args is None


def test_unsupported_mime_type_is_rejected_before_api_call():
    client = FakeClient(json.dumps(valid_payload()))

    with pytest.raises(ValueError, match="MIME type"):
        analyze_image(client, b"image", "image/gif")

    assert client.models.call_args is None


def test_safety_block_is_not_treated_as_an_assessment():
    candidates = [
        SimpleNamespace(finish_reason=types.FinishReason.SAFETY)
    ]
    with pytest.raises(GeminiResponseError, match="different image"):
        analyze_image(
            FakeClient(json.dumps(valid_payload()), candidates),
            b"image",
            "image/jpeg",
        )


def test_token_limited_response_is_rejected_as_incomplete():
    candidates = [
        SimpleNamespace(finish_reason=types.FinishReason.MAX_TOKENS)
    ]
    with pytest.raises(GeminiResponseError, match="incomplete"):
        analyze_image(
            FakeClient(json.dumps(valid_payload()), candidates),
            b"image",
            "image/jpeg",
        )


def test_missing_candidates_are_rejected():
    with pytest.raises(GeminiResponseError, match="candidate"):
        analyze_image(
            FakeClient(json.dumps(valid_payload()), candidates=[]),
            b"image",
            "image/jpeg",
        )


def test_rate_limit_error_is_sanitized():
    provider_error = errors.ClientError(
        429,
        {
            "error": {
                "message": "private provider diagnostic",
                "status": "RESOURCE_EXHAUSTED",
            }
        },
    )
    client = FakeClient("unused", exception=provider_error)

    with pytest.raises(GeminiResponseError, match="request limit") as caught:
        analyze_image(client, b"image", "image/jpeg")

    assert "private provider diagnostic" not in str(caught.value)


def test_timeout_error_is_sanitized():
    client = FakeClient(
        "unused",
        exception=httpx.TimeoutException("internal timeout details"),
    )

    with pytest.raises(GeminiResponseError, match="timed out") as caught:
        analyze_image(client, b"image", "image/jpeg")

    assert "internal timeout details" not in str(caught.value)


def test_network_error_is_sanitized():
    client = FakeClient(
        "unused",
        exception=httpx.ConnectError("internal connection details"),
    )

    with pytest.raises(GeminiResponseError, match="network error") as caught:
        analyze_image(client, b"image", "image/jpeg")

    assert "internal connection details" not in str(caught.value)


def test_api_error_exposes_safe_diagnostic_fields():
    provider_error = errors.APIError(
        400,
        {
            "error": {
                "message": "private provider diagnostic",
                "status": "INVALID_ARGUMENT",
            }
        },
    )
    client = FakeClient("unused", exception=provider_error)

    with pytest.raises(GeminiResponseError) as caught:
        analyze_image(client, b"image", "image/jpeg")

    assert caught.value.diagnostic_code == 400
    assert caught.value.diagnostic_status == "INVALID_ARGUMENT"
    assert "private provider diagnostic" not in str(caught.value)
    assert caught.value.__suppress_context__ is True


def test_unknown_provider_status_is_not_exposed_verbatim():
    provider_error = errors.APIError(
        500,
        {
            "error": {
                "message": "sensitive provider details",
                "status": "CUSTOM_PRIVATE_STATUS",
            }
        },
    )
    client = FakeClient("unused", exception=provider_error)

    with pytest.raises(GeminiResponseError) as caught:
        analyze_image(client, b"image", "image/jpeg")

    assert caught.value.diagnostic_code == 500
    assert caught.value.diagnostic_status == "UNKNOWN"
    assert "sensitive provider details" not in str(caught.value)
    assert "CUSTOM_PRIVATE_STATUS" not in str(caught.value)
