import pytest

from src.accessable_ai.response_validation import (
    ResponseValidationError,
    validate_assessment_response,
)


def valid_assessment():
    return {
        "potential_barriers": [
            {
                "observation": "A step is visible at the entrance.",
                "visible_evidence": "The doorway appears raised above the path.",
                "confidence": "medium",
            }
        ],
        "visible_features": [
            {
                "feature": "A handrail is visible.",
                "visible_evidence": "A rail can be seen beside the steps.",
            }
        ],
        "limitations": ["The image cannot establish exact dimensions."],
        "recommended_checks": ["Measure the step height on site."],
    }


def test_valid_assessment_is_accepted():
    result = validate_assessment_response(valid_assessment())
    assert result["potential_barriers"][0]["confidence"] == "medium"


def test_empty_sections_are_valid():
    data = {
        "potential_barriers": [],
        "visible_features": [],
        "limitations": [],
        "recommended_checks": [],
    }
    assert validate_assessment_response(data) == data


def test_missing_top_level_field_is_rejected():
    data = valid_assessment()
    del data["limitations"]

    with pytest.raises(ResponseValidationError, match="missing required fields"):
        validate_assessment_response(data)


def test_unexpected_top_level_field_is_rejected():
    data = valid_assessment()
    data["compliance_score"] = 100

    with pytest.raises(ResponseValidationError, match="unexpected fields"):
        validate_assessment_response(data)


def test_non_object_response_is_rejected():
    with pytest.raises(ResponseValidationError, match="must be an object"):
        validate_assessment_response(["not", "an", "object"])


def test_invalid_confidence_is_rejected():
    data = valid_assessment()
    data["potential_barriers"][0]["confidence"] = "certain"

    with pytest.raises(ResponseValidationError, match="confidence must be one of"):
        validate_assessment_response(data)


def test_blank_evidence_is_rejected():
    data = valid_assessment()
    data["potential_barriers"][0]["visible_evidence"] = "   "

    with pytest.raises(ResponseValidationError, match="non-empty string"):
        validate_assessment_response(data)


def test_unexpected_nested_field_is_rejected():
    data = valid_assessment()
    data["visible_features"][0]["extra"] = "unexpected"

    with pytest.raises(ResponseValidationError, match="unexpected fields"):
        validate_assessment_response(data)


def test_wrong_array_type_is_rejected():
    data = valid_assessment()
    data["limitations"] = "not an array"

    with pytest.raises(ResponseValidationError, match="must be an array"):
        validate_assessment_response(data)


def test_excessive_barrier_count_is_rejected():
    data = valid_assessment()
    data["potential_barriers"] = [
        {
            "observation": "Barrier",
            "visible_evidence": "Evidence",
            "confidence": "low",
        }
        for _ in range(31)
    ]

    with pytest.raises(ResponseValidationError, match="Too many potential barriers"):
        validate_assessment_response(data)


def test_non_string_confidence_is_rejected():
    data = valid_assessment()
    data["potential_barriers"][0]["confidence"] = None

    with pytest.raises(ResponseValidationError):
        validate_assessment_response(data)


def test_excessively_long_text_field_is_rejected():
    data = valid_assessment()
    data["limitations"] = ["x" * 2001]

    with pytest.raises(ResponseValidationError, match="text length limit"):
        validate_assessment_response(data)


def test_excessive_recommended_checks_are_rejected():
    data = valid_assessment()
    data["recommended_checks"] = ["Check on site"] * 31

    with pytest.raises(ResponseValidationError, match="too many items"):
        validate_assessment_response(data)


def test_non_object_nested_barrier_is_rejected():
    data = valid_assessment()
    data["potential_barriers"] = ["not an object"]

    with pytest.raises(ResponseValidationError, match="must be an object"):
        validate_assessment_response(data)
