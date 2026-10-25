import os

import streamlit as st

from src.accessable_ai.assessment_service import assess_image
from src.accessable_ai.gemini_client import GeminiResponseError
from src.accessable_ai.image_validation import (
    ImageValidationError,
    validate_and_normalize_image,
)
from src.accessable_ai.response_validation import ResponseValidationError


st.set_page_config(
    page_title="AccessAble AI",
    page_icon="\U0001F50E",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1180px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }
    .hero {
        padding: 1.8rem 0 1.2rem 0;
    }
    .eyebrow {
        color: #35F2D0;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
    }
    .hero h1 {
        color: #F3F7FB;
        font-size: clamp(2.2rem, 5vw, 3.6rem);
        line-height: 1.08;
        margin: 0.65rem 0;
    }
    .hero p {
        color: #B6C6D6;
        font-size: 1.08rem;
        max-width: 760px;
        line-height: 1.7;
    }
    .section-label {
        color: #35F2D0;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .notice {
        border: 1px solid #294354;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        background: #101F2E;
        color: #D7E3ED;
        line-height: 1.65;
    }
    div[data-testid="stFileUploader"] {
        border: 1px dashed #35F2D0;
        border-radius: 12px;
        padding: 0.7rem;
        background: #101F2E;
    }
    div.stButton > button[kind="primary"] {
        min-height: 3rem;
        font-weight: 700;
        border-radius: 10px;
    }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">AI-assisted visual review</div>
        <h1>AccessAble AI</h1>
        <p>
            Explore potential accessibility barriers in a photograph of an
            entrance or public space. Get evidence-linked observations,
            visible features, limitations, and practical checks.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="notice">
        <strong>Important:</strong> This tool provides preliminary observations
        from a photograph, not an accessibility certification. A single image
        cannot establish dimensions, the full route, usability, or compliance
        with applicable standards. Findings must be verified on site.
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")
left, right = st.columns([1.05, 0.95], gap="large")

with left:
    st.markdown('<div class="section-label">01 / Upload a photo</div>',
                unsafe_allow_html=True)
    st.subheader("Choose an entrance or public space")

    uploaded_file = st.file_uploader(
        "Upload an image",
        type=["jpg", "jpeg", "png", "webp"],
        help="JPEG, PNG, or WebP. Maximum file size: 10 MB.",
        key="accessable_image_upload",
    )

    st.caption(
        "Use a clear, well-lit photo. Avoid including faces, identity documents, "
        "or other sensitive information."
    )

    image_is_valid = False

    if uploaded_file is not None:
        try:
            validated_preview = validate_and_normalize_image(
                uploaded_file.getvalue()
            )
            image_is_valid = True
            st.image(
                validated_preview.image_bytes,
                caption="Selected image — not yet sent for analysis",
                use_container_width=True,
            )
        except ImageValidationError as exc:
            st.error(str(exc))

    assess_clicked = st.button(
        "Assess image",
        type="primary",
        use_container_width=True,
        disabled=uploaded_file is None or not image_is_valid,
    )

    if assess_clicked and uploaded_file is not None:
        st.session_state.pop("accessable_assessment_result", None)

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            st.error(
                "Gemini API key not configured. Set GEMINI_API_KEY in your "
                "environment before requesting an assessment."
            )
        else:
            try:
                with st.spinner("Reviewing visible features and potential barriers..."):
                    result = assess_image(uploaded_file.getvalue(), api_key)
                st.session_state["accessable_assessment_result"] = result
                st.success("Assessment completed.")
            except ImageValidationError as exc:
                st.error(str(exc))
            except GeminiResponseError as exc:
                st.error(
                    "The AI service could not complete the assessment. "
                    "Please try again later or check your API quota and settings."
                )
                if (
                    exc.diagnostic_code is not None
                    or exc.diagnostic_status != "UNKNOWN"
                ):
                    st.caption(
                        "Safe diagnostic: "
                        f"HTTP code = {exc.diagnostic_code or 'unavailable'}; "
                        f"status = {exc.diagnostic_status}"
                    )
            except ResponseValidationError:
                st.error(
                    "The service returned an assessment that could not be "
                    "validated. Please try again."
                )
            except ValueError as exc:
                if str(exc) == "A Gemini API key is required.":
                    st.error("A Gemini API key is required to assess an image.")
                else:
                    st.error("The assessment could not be completed.")
            except Exception:
                st.error(
                    "An unexpected error prevented the assessment. "
                    "No diagnostic details are displayed."
                )

with right:
    st.markdown('<div class="section-label">02 / Understand the result</div>',
                unsafe_allow_html=True)
    st.subheader("What the assessment covers")

    st.markdown(
        """
        **Potential barriers**
        Possible obstacles, supporting visible evidence, and qualitative confidence.

        **Visible features**
        Features that can actually be observed in the photograph.

        **Limitations**
        What the image or model cannot reliably determine.

        **Recommended checks**
        Practical items to verify in person.
        """
    )

    st.info(
        "Your image is processed by the selected AI provider only when you "
        "click Assess image. Do not upload sensitive photographs. This app "
        "does not intentionally save assessment history to disk."
    )

result = st.session_state.get("accessable_assessment_result")

if result is not None:
    st.divider()
    st.markdown('<div class="section-label">03 / Assessment report</div>',
                unsafe_allow_html=True)
    st.header("Assessment findings")
    st.caption(
        "AI-generated observations. Confirm all findings in the real environment."
    )

    barriers = result["potential_barriers"]
    features = result["visible_features"]
    limitations = result["limitations"]
    checks = result["recommended_checks"]

    summary_cols = st.columns(2)
    summary_cols[0].metric("Potential barriers", len(barriers))
    summary_cols[1].metric("Visible features", len(features))

    with st.expander("Potential barriers", expanded=True):
        if not barriers:
            st.write(
                "No potential barriers were identified in the returned analysis. "
                "This does not establish that the space is accessible."
            )
        for index, item in enumerate(barriers, start=1):
            st.markdown(f"**{index}. {item['observation']}**")
            st.write(f"Visible evidence: {item['visible_evidence']}")
            st.caption(f"Qualitative confidence: {item['confidence'].capitalize()}")
            if index < len(barriers):
                st.divider()

    with st.expander("Visible features", expanded=True):
        if not features:
            st.write("No visible features were reported.")
        for item in features:
            st.markdown(f"**{item['feature']}**")
            st.write(item["visible_evidence"])

    with st.expander("Limitations", expanded=True):
        for item in limitations:
            st.markdown(f"- {item}")

    with st.expander("Recommended checks", expanded=True):
        for item in checks:
            st.markdown(f"- {item}")

st.divider()
st.caption(
    "AccessAble AI — Preliminary visual assistance, not a substitute for "
    "an on-site accessibility assessment."
)
