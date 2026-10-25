"""Strict validation for parsed Gemini assessment responses."""

from typing import Any

from src.accessable_ai.response_schema import CONFIDENCE_LEVELS


MAX_BARRIERS = 30
MAX_FEATURES = 30
MAX_TEXT_ITEMS = 30
MAX_FIELD_CHARS = 2000
MAX_TOTAL_CHARS = 20000

TOP_LEVEL_FIELDS = {
    "potential_barriers",
    "visible_features",
    "limitations",
    "recommended_checks",
}


class ResponseValidationError(ValueError):
    """Raised when a model response violates the assessment contract."""


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResponseValidationError(f"{location} must be an object.")
    if any(not isinstance(key, str) for key in value):
        raise ResponseValidationError(f"{location} has invalid field names.")
    return value


def _require_exact_fields(
    value: dict[str, Any],
    required: set[str],
    location: str,
) -> None:
    actual = set(value)
    missing = required - actual
    unexpected = actual - required

    if missing:
        raise ResponseValidationError(
            f"{location} is missing required fields: {', '.join(sorted(missing))}."
        )
    if unexpected:
        raise ResponseValidationError(
            f"{location} contains unexpected fields: {', '.join(sorted(unexpected))}."
        )


def _require_text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResponseValidationError(f"{location} must be a non-empty string.")
    if len(value) > MAX_FIELD_CHARS:
        raise ResponseValidationError(f"{location} exceeds the text length limit.")
    return value.strip()


def _require_text_list(
    value: Any,
    location: str,
    maximum_items: int = MAX_TEXT_ITEMS,
) -> list[str]:
    if not isinstance(value, list):
        raise ResponseValidationError(f"{location} must be an array.")
    if len(value) > maximum_items:
        raise ResponseValidationError(f"{location} contains too many items.")

    return [
        _require_text(item, f"{location}[{index}]")
        for index, item in enumerate(value)
    ]


def validate_assessment_response(value: Any) -> dict[str, Any]:
    """Validate and return a clean assessment dictionary."""
    data = _require_object(value, "Assessment")
    _require_exact_fields(data, TOP_LEVEL_FIELDS, "Assessment")

    barriers = data["potential_barriers"]
    if not isinstance(barriers, list):
        raise ResponseValidationError("potential_barriers must be an array.")
    if len(barriers) > MAX_BARRIERS:
        raise ResponseValidationError("Too many potential barriers.")

    clean_barriers = []
    for index, item in enumerate(barriers):
        location = f"potential_barriers[{index}]"
        barrier = _require_object(item, location)
        _require_exact_fields(
            barrier,
            {"observation", "visible_evidence", "confidence"},
            location,
        )
        confidence = barrier["confidence"]
        if confidence not in CONFIDENCE_LEVELS:
            raise ResponseValidationError(
                f"{location}.confidence must be one of: "
                f"{', '.join(CONFIDENCE_LEVELS)}."
            )
        clean_barriers.append({
            "observation": _require_text(
                barrier["observation"], f"{location}.observation"
            ),
            "visible_evidence": _require_text(
                barrier["visible_evidence"], f"{location}.visible_evidence"
            ),
            "confidence": confidence,
        })

    features = data["visible_features"]
    if not isinstance(features, list):
        raise ResponseValidationError("visible_features must be an array.")
    if len(features) > MAX_FEATURES:
        raise ResponseValidationError("Too many visible features.")

    clean_features = []
    for index, item in enumerate(features):
        location = f"visible_features[{index}]"
        feature = _require_object(item, location)
        _require_exact_fields(
            feature,
            {"feature", "visible_evidence"},
            location,
        )
        clean_features.append({
            "feature": _require_text(feature["feature"], f"{location}.feature"),
            "visible_evidence": _require_text(
                feature["visible_evidence"], f"{location}.visible_evidence"
            ),
        })

    limitations = _require_text_list(data["limitations"], "limitations")
    recommended_checks = _require_text_list(
        data["recommended_checks"], "recommended_checks"
    )

    clean = {
        "potential_barriers": clean_barriers,
        "visible_features": clean_features,
        "limitations": limitations,
        "recommended_checks": recommended_checks,
    }

    total_chars = sum(
        len(text)
        for barrier in clean_barriers
        for text in (barrier["observation"], barrier["visible_evidence"])
    )
    total_chars += sum(
        len(text)
        for feature in clean_features
        for text in (feature["feature"], feature["visible_evidence"])
    )
    total_chars += sum(map(len, limitations))
    total_chars += sum(map(len, recommended_checks))

    if total_chars > MAX_TOTAL_CHARS:
        raise ResponseValidationError(
            "The assessment exceeds the total text length limit."
        )

    return clean
