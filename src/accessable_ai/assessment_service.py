from typing import Any, Callable

from src.accessable_ai.gemini_client import (
    analyze_image,
    create_gemini_client,
)
from src.accessable_ai.image_validation import validate_and_normalize_image


def assess_image(
    image_bytes: bytes,
    api_key: str,
    *,
    client_factory: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Validate an uploaded image and return its validated AI assessment.

    This function performs no logging and does not persist uploaded data.
    The Gemini request occurs only when this function is explicitly called.
    """
    validated_image = validate_and_normalize_image(image_bytes)

    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("A Gemini API key is required.")

    factory = (
        client_factory
        if client_factory is not None
        else create_gemini_client
    )

    client = factory(api_key)

    return analyze_image(
        client,
        validated_image.image_bytes,
        validated_image.mime_type,
    )
