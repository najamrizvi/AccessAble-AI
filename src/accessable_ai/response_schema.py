"""Structured response contract for AccessAble AI."""

from typing import Any


CONFIDENCE_LEVELS = ("low", "medium", "high")

ASSESSMENT_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "potential_barriers": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "observation": {"type": "STRING"},
                    "visible_evidence": {"type": "STRING"},
                    "confidence": {
                        "type": "STRING",
                        "enum": list(CONFIDENCE_LEVELS),
                    },
                },
                "required": [
                    "observation",
                    "visible_evidence",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "visible_features": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "feature": {"type": "STRING"},
                    "visible_evidence": {"type": "STRING"},
                },
                "required": ["feature", "visible_evidence"],
                "additionalProperties": False,
            },
        },
        "limitations": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "recommended_checks": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": [
        "potential_barriers",
        "visible_features",
        "limitations",
        "recommended_checks",
    ],
    "additionalProperties": False,
}
