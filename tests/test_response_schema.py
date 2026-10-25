from src.accessable_ai.response_schema import (
    ASSESSMENT_SCHEMA,
    CONFIDENCE_LEVELS,
)


def test_schema_requires_all_four_assessment_sections():
    assert set(ASSESSMENT_SCHEMA["required"]) == {
        "potential_barriers",
        "visible_features",
        "limitations",
        "recommended_checks",
    }


def test_barrier_schema_requires_evidence_and_confidence():
    barrier = ASSESSMENT_SCHEMA["properties"]["potential_barriers"]["items"]

    assert set(barrier["required"]) == {
        "observation",
        "visible_evidence",
        "confidence",
    }
    assert barrier["properties"]["confidence"]["enum"] == [
        "low",
        "medium",
        "high",
    ]


def test_visible_features_require_evidence():
    feature = ASSESSMENT_SCHEMA["properties"]["visible_features"]["items"]

    assert set(feature["required"]) == {"feature", "visible_evidence"}


def test_all_sections_use_array_types():
    properties = ASSESSMENT_SCHEMA["properties"]

    assert all(
        properties[name]["type"] == "ARRAY"
        for name in (
            "potential_barriers",
            "visible_features",
            "limitations",
            "recommended_checks",
        )
    )


def test_confidence_levels_are_fixed():
    assert CONFIDENCE_LEVELS == ("low", "medium", "high")
