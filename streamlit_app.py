from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import cv2
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.cloud_io import (  # noqa: E402
    UploadedImageValidationError,
    decode_uploaded_image,
    encode_annotated_png,
    inspection_csv_bytes,
    inspection_json_bytes,
)
from app.services.inspection_engine import (  # noqa: E402
    ENGINE_VERSION,
    InspectionEngine,
    InspectionInputError,
    InspectionResult,
)

st.set_page_config(
    page_title="AI Wire Harness Inspection",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def load_inspection_engine() -> InspectionEngine:
    """Load reusable processing resources once per Streamlit worker."""
    return InspectionEngine(project_root=PROJECT_ROOT)


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        :root { --navy:#081d30; --blue:#176aa6; --cyan:#28a8df; --green:#16824b; --red:#c93038; --amber:#b67a12; }
        .stApp { background: #f2f5f7; }
        [data-testid="stHeader"] { background: rgba(242,245,247,.92); }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, #081d30 0%, #0c2942 100%); }
        [data-testid="stSidebar"] * { color: #eaf3f8; }
        [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div { color: #56bce9; }
        .industrial-header { padding: 1.2rem 1.35rem; margin-bottom: 1rem; color: white; background: linear-gradient(120deg, #081d30, #123d5e); border-left: 6px solid #28a8df; border-radius: .35rem; }
        .industrial-header .kicker { color:#7fd4f5; font-size:.73rem; font-weight:800; letter-spacing:.13em; }
        .industrial-header h1 { margin:.2rem 0 .3rem; color:white; font-size:2rem; line-height:1.1; }
        .industrial-header p { margin:0; color:#c7dce9; font-size:.93rem; }
        .status-card { padding:1rem 1.1rem; margin:.3rem 0 .9rem; border-radius:.3rem; background:white; border:1px solid #d8e0e6; border-left:7px solid #647787; }
        .status-card strong { display:block; font-size:1.5rem; color:#081d30; }
        .status-card span { color:#647787; font-size:.8rem; }
        .status-not_evaluated { border-left-color:#b67a12; }
        .status-review_required { border-left-color:#176aa6; }
        .status-pass { border-left-color:#16824b; }
        .status-fail { border-left-color:#c93038; }
        .section-label { margin:1.1rem 0 .45rem; color:#176aa6; font-size:.72rem; font-weight:800; letter-spacing:.12em; }
        .model-box { padding:.7rem .75rem; border:1px solid rgba(255,255,255,.2); border-radius:.3rem; background:rgba(255,255,255,.07); }
        .model-box strong,.model-box span { display:block; }.model-box strong { color:#fff; }.model-box span { margin-top:.2rem; color:#b9d1df; font-size:.75rem; line-height:1.35; }
        div[data-testid="stMetric"] { padding:.8rem; background:white; border:1px solid #d8e0e6; border-radius:.3rem; }
        div[data-testid="stDataFrame"] { border:1px solid #d8e0e6; border-radius:.3rem; }
        .evidence-note { padding:.8rem 1rem; color:#6f520d; background:#fff7df; border:1px solid #ead293; border-radius:.3rem; font-size:.82rem; }
        @media (max-width: 700px) {
          .industrial-header { padding:1rem; }.industrial-header h1 { font-size:1.5rem; }
          [data-testid="column"] { min-width:100% !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _result_table_rows(result: InspectionResult) -> list[dict[str, object]]:
    return [
        {
            "Rule": rule.rule_name,
            "Status": rule.status,
            "Expected": rule.expected_value or "—",
            "Actual": rule.actual_value or "—",
            "Reason": rule.message,
        }
        for rule in result.rule_results
    ]


def _measurement_rows(result: InspectionResult) -> list[dict[str, object]]:
    return [
        {
            "Measurement": item.name,
            "Value": round(item.value, 3),
            "Unit": item.unit,
            "Method": item.method,
        }
        for item in result.measurements
    ]


def _branch_rows(result: InspectionResult) -> list[dict[str, object]]:
    return [
        {
            "Branch": item.branch_id,
            "Nodes": f"{item.source_node_id} → {item.target_node_id}",
            "Path (px)": round(item.path_length_pixels, 2),
            "Straight (px)": round(item.straight_distance_pixels, 2),
            "Orientation (°)": round(item.orientation_degrees, 2),
        }
        for item in result.branches
    ]


def _junction_rows(result: InspectionResult) -> list[dict[str, object]]:
    return [
        {
            "Junction": item.node_id,
            "Pixel": f"({item.x}, {item.y})",
            "Branch count": item.branch_count,
            "Branch orientations": ", ".join(
                f"{branch_id}: {angle:.1f}°"
                for branch_id, angle in item.branch_orientations
            ),
        }
        for item in result.junctions
    ]


def _terminal_distance_rows(result: InspectionResult) -> list[dict[str, object]]:
    return [
        {
            "Junction": item.junction_node_id,
            "End terminal": item.terminal_node_id,
            "Path (px)": round(item.path_distance_pixels, 2),
            "Straight (px)": round(item.straight_distance_pixels, 2),
        }
        for item in result.junction_terminal_distances
    ]


def _branch_pair_rows(result: InspectionResult) -> list[dict[str, object]]:
    return [
        {
            "Junction": item.junction_node_id,
            "Branches": f"{item.first_branch_id} ↔ {item.second_branch_id}",
            "Via junction (px)": round(item.via_junction_distance_pixels, 2),
            "Midpoint straight (px)": round(
                item.midpoint_straight_distance_pixels, 2
            ),
            "Angular separation (°)": round(item.angular_separation_degrees, 2),
        }
        for item in result.branch_pair_distances
    ]


def _render_result(result: InspectionResult, original_bgr: object) -> None:
    st.markdown(
        f'<div class="status-card status-{result.overall_status.lower()}"><span>OVERALL INSPECTION STATUS</span><strong>{result.overall_status.replace("_", " ")}</strong><span>No production PASS/FAIL is issued without validated weights, rules, references, and calibration.</span></div>',
        unsafe_allow_html=True,
    )

    metric_columns = st.columns(5)
    metric_columns[0].metric("Image", f"{result.image_width} × {result.image_height}", "pixels")
    metric_columns[1].metric("Detections", len(result.detections), "validated objects")
    centreline = next(item for item in result.measurements if item.measurement_id == "M-CENTRELINE")
    metric_columns[2].metric("Centreline", f"{centreline.value:,.1f} px", "uncalibrated")
    metric_columns[3].metric("Branches", len(result.branches), "resolved paths")
    metric_columns[4].metric("Processing", f"{result.processing_time_ms:,.0f} ms", result.model_status.device.upper())

    st.markdown('<div class="section-label">VISUAL EVIDENCE</div>', unsafe_allow_html=True)
    original_column, annotated_column = st.columns(2)
    with original_column:
        st.caption("ORIGINAL UPLOAD")
        st.image(cv2.cvtColor(original_bgr, cv2.COLOR_BGR2RGB), use_container_width=True)
    with annotated_column:
        st.caption("ANNOTATED ENGINEERING OUTPUT")
        st.image(cv2.cvtColor(result.annotated_image, cv2.COLOR_BGR2RGB), use_container_width=True)

    st.markdown('<div class="section-label">RULE-WISE RESULTS</div>', unsafe_allow_html=True)
    st.dataframe(_result_table_rows(result), use_container_width=True, hide_index=True)

    st.markdown('<div class="section-label">DETECTED OBJECTS</div>', unsafe_allow_html=True)
    if result.detections:
        st.dataframe(
            [
                {
                    "Label": item.label,
                    "Confidence": item.confidence,
                    "Bounding box": item.bounding_box,
                }
                for item in result.detections
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No validated object detector is installed, so no component detections or confidence values are reported.")

    st.markdown('<div class="section-label">AVAILABLE MEASUREMENTS</div>', unsafe_allow_html=True)
    st.dataframe(_measurement_rows(result), use_container_width=True, hide_index=True)
    with st.expander(f"Node-to-node branch measurements ({len(result.branches)})"):
        st.dataframe(_branch_rows(result), use_container_width=True, hide_index=True)
    with st.expander(f"Junction branch counts and orientations ({len(result.junctions)})"):
        st.dataframe(_junction_rows(result), use_container_width=True, hide_index=True)
    with st.expander(
        f"Junction-to-end-terminal distances ({len(result.junction_terminal_distances)})"
    ):
        st.dataframe(
            _terminal_distance_rows(result), use_container_width=True, hide_index=True
        )
    with st.expander(f"Branch-to-branch distances ({len(result.branch_pair_distances)})"):
        st.dataframe(_branch_pair_rows(result), use_container_width=True, hide_index=True)

    for warning in result.warnings:
        st.warning(warning)
    for error in result.errors:
        st.error(error)

    st.markdown('<div class="section-label">DOWNLOAD RESULTS</div>', unsafe_allow_html=True)
    png_column, json_column, csv_column = st.columns(3)
    base_name = result.inspection_id.lower()
    png_column.download_button(
        "Download annotated PNG",
        data=encode_annotated_png(result),
        file_name=f"{base_name}-annotated.png",
        mime="image/png",
        use_container_width=True,
    )
    json_column.download_button(
        "Download JSON summary",
        data=inspection_json_bytes(result),
        file_name=f"{base_name}.json",
        mime="application/json",
        use_container_width=True,
    )
    csv_column.download_button(
        "Download CSV summary",
        data=inspection_csv_bytes(result),
        file_name=f"{base_name}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def main() -> None:
    _inject_style()
    engine = load_inspection_engine()
    model_status = engine.model_status

    st.markdown(
        """
        <div class="industrial-header">
          <div class="kicker">CLOUD ENGINEERING WORKSTATION</div>
          <h1>AI Wire Harness Inspection System</h1>
          <p>Upload a harness image, run the implemented OpenCV pipeline, review evidence, and download results.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.subheader("Project details")
        st.write("AI Wire Harness Final Inspection System")
        st.caption(f"Cloud adapter v{ENGINE_VERSION}")
        st.markdown(
            f'<div class="model-box"><strong>MODEL {model_status.state}</strong><span>{model_status.message}</span><span>Device: {model_status.device.upper()}</span></div>',
            unsafe_allow_html=True,
        )
        st.divider()
        variant = st.selectbox("Harness variant", engine.available_variants())
        confidence_threshold = st.slider(
            "Model confidence threshold",
            min_value=0.05,
            max_value=0.95,
            value=0.50,
            step=0.05,
            disabled=not model_status.available,
            help="Disabled because no validated object-detection model is installed.",
        )
        with st.expander("OpenCV engineering parameters"):
            component_ratio = st.number_input(
                "Minimum component area ratio",
                min_value=0.00001,
                max_value=0.01,
                value=0.0002,
                step=0.00005,
                format="%.5f",
            )
            closing_kernel = st.select_slider("Closing kernel", options=[3, 5, 7, 9, 11], value=7)
            closing_iterations = st.slider("Closing iterations", 1, 5, 2)
            junction_radius = st.slider("Junction cluster radius (px)", 1, 20, 6)
        st.divider()
        st.caption("Uploads are processed in memory and are not persisted by this Streamlit application.")

    if not model_status.available:
        st.warning(
            "Trained AI weights and a validated detector adapter are not present. The application will run the real OpenCV engineering pipeline and mark production rules NOT EVALUATED."
        )

    uploaded_file = st.file_uploader(
        "Upload a wire harness image",
        type=["jpg", "jpeg", "png"],
        help="JPEG or PNG, maximum 15 MB and 40 megapixels.",
    )
    if uploaded_file is None:
        st.markdown(
            '<div class="evidence-note">Choose an image to preview it. Inspection runs only after you press <strong>Run AI Inspection</strong>.</div>',
            unsafe_allow_html=True,
        )
        return

    payload = uploaded_file.getvalue()
    upload_key = hashlib.sha256(payload).hexdigest()
    try:
        image = decode_uploaded_image(
            payload,
            filename=uploaded_file.name,
            content_type=uploaded_file.type,
        )
    except UploadedImageValidationError as error:
        st.error(str(error))
        return

    if st.session_state.get("upload_key") != upload_key:
        st.session_state["upload_key"] = upload_key
        st.session_state.pop("inspection_result", None)

    st.caption(f"{uploaded_file.name} · {len(payload) / (1024 * 1024):.2f} MB · {image.shape[1]} × {image.shape[0]} px")
    if "inspection_result" not in st.session_state:
        st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption="Original image preview", use_container_width=True)

    if st.button("Run AI Inspection", type="primary", use_container_width=True):
        config = {
            "confidence_threshold": confidence_threshold,
            "minimum_component_area_ratio": component_ratio,
            "closing_kernel_size": closing_kernel,
            "closing_iterations": closing_iterations,
            "junction_cluster_radius": junction_radius,
        }
        try:
            with st.spinner("Running segmentation, topology extraction, and pixel measurements…"):
                st.session_state["inspection_result"] = engine.inspect_harness(
                    image,
                    variant=variant,
                    config=config,
                )
        except (InspectionInputError, ValueError, RuntimeError) as error:
            st.error(f"Inspection could not be completed: {error}")
            st.session_state.pop("inspection_result", None)

    result = st.session_state.get("inspection_result")
    if isinstance(result, InspectionResult):
        _render_result(result, image)


if __name__ == "__main__":
    main()
