from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.accessable_ai import assessment_service


def test_opening_app_does_not_trigger_assessment(monkeypatch):
    calls = []

    def fake_assess_image(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Assessment must not run automatically.")

    monkeypatch.setattr(
        assessment_service,
        "assess_image",
        fake_assess_image,
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert calls == []
    assert len(app.button) == 1
    assert app.button[0].label == "Assess image"
    assert app.button[0].disabled is True

from io import BytesIO

from PIL import Image


def make_png_bytes():
    buffer = BytesIO()
    image = Image.new("RGB", (128, 128), color="teal")
    image.save(buffer, format="PNG")
    image.close()
    return buffer.getvalue()


def test_uploading_image_does_not_trigger_assessment(monkeypatch):
    calls = []

    def fake_assess_image(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Uploading must not trigger assessment.")

    monkeypatch.setattr(
        assessment_service,
        "assess_image",
        fake_assess_image,
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    app.file_uploader[0].set_value(("test-entrance.png", make_png_bytes(), "image/png")).run()

    assert not app.exception
    assert calls == []
    assert app.button[0].label == "Assess image"
    assert app.button[0].disabled is False

def test_assessment_runs_only_after_button_click(monkeypatch):
    calls = []

    expected_result = {
        "potential_barriers": [
            {
                "observation": "A possible step at the entrance",
                "visible_evidence": "A raised edge is visible.",
                "confidence": "medium",
            }
        ],
        "visible_features": [
            {
                "feature": "Entrance door",
                "visible_evidence": "A door is visible in the image.",
            }
        ],
        "limitations": ["A photograph cannot establish full accessibility."],
        "recommended_checks": ["Verify the entrance on site."],
    }

    def fake_assess_image(image_bytes, api_key):
        calls.append((image_bytes, api_key))
        return expected_result

    monkeypatch.setattr(
        assessment_service,
        "assess_image",
        fake_assess_image,
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-fake-key")

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    app.file_uploader[0].set_value(
        ("test-entrance.png", make_png_bytes(), "image/png")
    ).run()

    assert calls == []
    assert app.button[0].disabled is False

    app.button[0].click().run()

    assert not app.exception
    assert len(calls) == 1
    assert calls[0][1] == "test-only-fake-key"
    assert calls[0][0]
    assert "Assessment completed." in [
        item.value for item in app.success
    ]
    assert app.session_state["accessable_assessment_result"] == expected_result

def test_missing_api_key_shows_message_without_assessment(monkeypatch):
    calls = []

    def fake_assess_image(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Assessment must not run without an API key.")

    monkeypatch.setattr(
        assessment_service,
        "assess_image",
        fake_assess_image,
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    app.file_uploader[0].set_value(
        ("test-entrance.png", make_png_bytes(), "image/png")
    ).run()

    app.button[0].click().run()

    assert not app.exception
    assert calls == []
    assert any(
        "Gemini API key not configured" in item.value
        for item in app.error
    )

def test_gemini_service_error_shows_safe_message(monkeypatch):
    def fake_assess_image(*args, **kwargs):
        from src.accessable_ai.gemini_client import GeminiResponseError

        raise GeminiResponseError(
            "The Gemini service could not complete the request."
        )

    monkeypatch.setattr(
        assessment_service,
        "assess_image",
        fake_assess_image,
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-fake-key")

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    app.file_uploader[0].set_value(
        ("test-entrance.png", make_png_bytes(), "image/png")
    ).run()

    app.button[0].click().run()

    assert not app.exception
    assert any(
        "AI service could not complete the assessment" in item.value
        for item in app.error
    )
    assert not any(
        "private provider diagnostic" in item.value
        for item in app.error
    )


def test_invalid_upload_is_rejected_before_assessment(monkeypatch):
    calls = []

    def fake_assess_image(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Invalid images must not be assessed.")

    monkeypatch.setattr(
        assessment_service,
        "assess_image",
        fake_assess_image,
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-fake-key")

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()

    app.file_uploader[0].set_value(
        ("broken.png", b"not an image", "image/png")
    ).run()

    assert not app.exception
    assert calls == []
    assert app.button[0].disabled is True
    assert any(
        "invalid, damaged" in item.value
        for item in app.error
    )
