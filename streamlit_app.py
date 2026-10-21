from __future__ import annotations

import base64
import io
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, initialize_database
from app.models import Checkpoint, ProductModel
from app.services.checkpoint_service import CheckpointService
from app.services.color_inspection_service import ColorInspectionService
from app.services.harness_graph_service import HarnessGraphService
from app.services.harness_segmentation_service import HarnessSegmentationService
from app.services.mock_inspection_service import MockInspectionService
from app.services.reporting_service import ReportingService

st.set_page_config(
    page_title="AI Wire Harness Inspection System",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def init_backend_services():
    initialize_database()
    return {
        "mock_inspection": MockInspectionService(),
        "segmentation": HarnessSegmentationService(),
        "graph": HarnessGraphService(),
        "color": ColorInspectionService(),
        "reporting": ReportingService(),
    }


def inject_custom_css():
    st.markdown(
        """
        <style>
        :root {
          --navy-950: #071b2d;
          --navy-900: #0b2947;
          --navy-800: #123c63;
          --blue-600: #176aa6;
          --blue-100: #e5f2fb;
          --green-600: #16824b;
          --green-100: #ddf4e7;
          --red-600: #c93038;
          --red-100: #fce5e7;
          --amber-600: #b56c00;
          --amber-100: #fff0d5;
          --slate-700: #445469;
          --slate-500: #708094;
          --slate-200: #dfe5ec;
          --slate-100: #edf1f5;
        }

        /* Streamlit base override */
        .stApp {
          background-color: #edf1f5;
          font-family: 'Segoe UI', Arial, sans-serif;
          color: #182536;
        }
        [data-testid="stHeader"] {
          background: rgba(237, 241, 245, 0.95);
        }
        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #071b2d 0%, #0b2b4c 65%, #0e3558 100%);
          border-right: 1px solid rgba(255,255,255,0.08);
        }
        [data-testid="stSidebar"] * {
          color: #e2ecf5;
        }
        [data-testid="stSidebar"] .stRadio label {
          color: #c7d8e6 !important;
          font-size: 0.92rem;
          font-weight: 500;
          padding: 6px 10px;
          border-radius: 4px;
          transition: background 0.15s;
        }
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:hover {
          background: rgba(255,255,255,0.08);
          color: #ffffff !important;
        }

        /* Topbar Header */
        .industrial-topbar {
          background: #0b2947;
          color: #ffffff;
          padding: 14px 24px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          box-shadow: 0 4px 14px rgba(7, 28, 49, 0.16);
          margin-bottom: 22px;
        }
        .industrial-topbar .title-group {
          display: flex;
          align-items: center;
          gap: 12px;
          font-family: 'Arial Narrow', 'Segoe UI', sans-serif;
          font-size: 1.15rem;
          letter-spacing: 1.2px;
          font-weight: 700;
        }
        .industrial-topbar .status-group {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        /* Status Pills */
        .status-pill {
          display: inline-block;
          padding: 4px 10px;
          border-radius: 3px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.8px;
          text-transform: uppercase;
        }
        .status-pill--pass {
          background: #ddf4e7;
          color: #09663a;
          border: 1px solid #a9dec0;
        }
        .status-pill--ng {
          background: #fce5e7;
          color: #a91f27;
          border: 1px solid #f1b9bd;
        }
        .status-pill--warning {
          background: #fff0d5;
          color: #8d5604;
          border: 1px solid #f0ce93;
        }
        .status-pill--info {
          background: #e5f2fb;
          color: #075b8f;
          border: 1px solid #b5d9ee;
        }

        /* Metric Cards */
        .metric-card-wrapper {
          background: #ffffff;
          border: 1px solid #dce3ea;
          border-radius: 6px;
          padding: 16px 18px;
          box-shadow: 0 4px 12px rgba(18, 42, 66, 0.05);
          border-top: 4px solid #176aa6;
          margin-bottom: 14px;
        }
        .metric-card-wrapper.green { border-top-color: #16824b; }
        .metric-card-wrapper.red { border-top-color: #c93038; }
        .metric-card-wrapper.amber { border-top-color: #b56c00; }
        .metric-card-wrapper .label {
          color: #708094;
          font-size: 0.75rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.6px;
        }
        .metric-card-wrapper .value {
          color: #0b2947;
          font-size: 1.85rem;
          font-weight: 700;
          font-family: 'Arial Narrow', 'Segoe UI', sans-serif;
          margin: 4px 0;
        }
        .metric-card-wrapper .detail {
          color: #708094;
          font-size: 0.75rem;
        }

        /* Generic Panels */
        .industrial-panel {
          background: #ffffff;
          border: 1px solid #dce3ea;
          border-radius: 6px;
          box-shadow: 0 4px 12px rgba(18, 42, 66, 0.05);
          padding: 18px 20px;
          margin-bottom: 18px;
        }
        .panel-title {
          font-family: 'Arial Narrow', 'Segoe UI', sans-serif;
          font-size: 1.25rem;
          color: #0b2947;
          font-weight: 700;
          margin: 0 0 12px 0;
        }
        .eyebrow {
          color: #176aa6;
          font-size: 0.68rem;
          font-weight: 800;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          margin-bottom: 3px;
        }

        /* Info strip */
        .info-strip {
          background: #ffffff;
          border: 1px solid #dce3ea;
          border-radius: 5px;
          padding: 10px 16px;
          display: flex;
          flex-wrap: wrap;
          gap: 24px;
          margin-bottom: 16px;
        }
        .info-item span {
          display: block;
          font-size: 0.68rem;
          color: #708094;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .info-item strong {
          display: block;
          font-size: 0.95rem;
          color: #0b2947;
        }

        /* Overall Result Card */
        .overall-box {
          padding: 18px;
          border-radius: 6px;
          text-align: center;
          font-weight: 800;
          font-size: 2.2rem;
          font-family: 'Arial Narrow', sans-serif;
          margin-bottom: 16px;
          letter-spacing: 1px;
        }
        .overall-box--ready {
          background: #edf1f5;
          color: #445469;
          border: 2px dashed #cbd4df;
        }
        .overall-box--pass {
          background: #ddf4e7;
          color: #09663a;
          border: 2px solid #16824b;
        }
        .overall-box--ng {
          background: #fce5e7;
          color: #a91f27;
          border: 2px solid #c93038;
        }

        /* NG Detail Panel */
        .ng-card {
          background: #fff8f8;
          border: 1px solid #f3cbcf;
          border-left: 5px solid #c93038;
          border-radius: 4px;
          padding: 14px 16px;
          margin-top: 14px;
        }
        .ng-card strong {
          color: #a91f27;
          font-size: 1rem;
        }
        .ng-card p {
          margin: 6px 0;
          font-size: 0.85rem;
          color: #445469;
        }

        /* Sidebar Brand */
        .sidebar-brand {
          padding: 12px 6px 20px;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          margin-bottom: 16px;
        }
        .sidebar-brand h2 {
          color: #ffffff;
          font-size: 1.15rem;
          font-family: 'Arial Narrow', sans-serif;
          letter-spacing: 1px;
          margin: 0;
        }
        .sidebar-brand span {
          color: #56b6ec;
        }
        .sidebar-brand small {
          color: #93acc1;
          font-size: 0.65rem;
          letter-spacing: 2px;
          display: block;
          margin-top: 3px;
        }

        @media (max-width: 700px) {
          .industrial-topbar { padding: 10px; }
          [data-testid="column"] { min-width: 100% !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar():
    st.markdown(
        """
        <div class="industrial-topbar">
          <div class="title-group">
            <span>⚙️ AI Wire Harness Inspection System</span>
          </div>
          <div class="status-group">
            <span class="status-pill status-pill--pass">SYSTEM READY</span>
            <span style="font-size:0.85rem; color:#91adc3;">Operator: <strong>Development Mode</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_sample_image() -> np.ndarray | None:
    candidate_paths = [
        PROJECT_ROOT / "data" / "test_images" / "harness_sample_01.jpeg",
        PROJECT_ROOT / "data" / "test_images" / "harness_sample_01.jpeg.jpeg",
    ]
    for path in candidate_paths:
        if path.is_file():
            image = cv2.imread(str(path))
            if image is not None:
                return image
    return None


def annotate_inspection_image(image_bgr: np.ndarray, results: list) -> np.ndarray:
    annotated = image_bgr.copy()
    for res in results:
        x, y, w, h = res.roi_x, res.roi_y, res.roi_width, res.roi_height
        color = (22, 130, 75) if res.status == "PASS" else (56, 48, 201)  # BGR
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)
        label = f"{res.checkpoint_id} [{res.status}]"
        cv2.putText(annotated, label, (x, max(25, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return annotated


def render_dashboard():
    st.markdown('<div class="eyebrow">MANAGEMENT OVERVIEW</div><h1 style="color:#0b2947; margin:0 0 16px 0; font-family:\'Arial Narrow\'; font-size:2rem;">Production Dashboard</h1>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-card-wrapper"><div class="label">Inspections Today</div><div class="value">142</div><div class="detail">18 in the last hour</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-card-wrapper green"><div class="label">Pass Today</div><div class="value">136</div><div class="detail">95.8% first pass yield</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-card-wrapper red"><div class="label">NG Today</div><div class="value">6</div><div class="detail">4.2% defect rate</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="metric-card-wrapper amber"><div class="label">Average Cycle</div><div class="value">4.8 s</div><div class="detail">Target ≤ 6.0 seconds</div></div>', unsafe_allow_html=True)

    left_col, right_col = st.columns([1.7, 1.0])
    with left_col:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">SHIFT PERFORMANCE</div><div class="panel-title">Inspection trend (hourly)</div>', unsafe_allow_html=True)
        hours = [f"{7+i:02d}:00" for i in range(12)]
        pass_counts = [58, 72, 66, 84, 76, 92, 87, 78, 95, 88, 83, 91]
        ng_counts = [2, 3, 1, 4, 3, 2, 5, 2, 1, 3, 2, 2]
        chart_data = {"Pass": pass_counts, "Defect (NG)": ng_counts}
        st.bar_chart(chart_data, height=220)
        st.markdown('</div>', unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">CELL READINESS</div><div class="panel-title">System health</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="display:flex; flex-direction:column; gap:10px; margin-top:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>Vision Core Engine</span><span class="status-pill status-pill--pass">ONLINE</span>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>Inspection Database</span><span class="status-pill status-pill--pass">CONNECTED</span>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>AI Processing Engine</span><span class="status-pill status-pill--info">MOCK / HEURISTIC</span>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>Camera Acquisition</span><span class="status-pill status-pill--info">SIMULATED GigE</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.info("Phase 1 development workstation. Camera and AI evaluation results are deterministic.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="industrial-panel"><div class="eyebrow">LATEST ACTIVITY</div><div class="panel-title">Recent inspections</div>', unsafe_allow_html=True)
    recent_data = [
        {"Inspection ID": "INS-240812-0142", "Model": "MOD-12345-A", "Time": "14:32:08", "Cycle": "4.6 s", "Result": "PASS"},
        {"Inspection ID": "INS-240812-0141", "Model": "MOD-12345-A", "Time": "14:29:51", "Cycle": "5.1 s", "Result": "NG"},
        {"Inspection ID": "INS-240812-0140", "Model": "MOD-12345-A", "Time": "14:27:12", "Cycle": "4.7 s", "Result": "PASS"},
        {"Inspection ID": "INS-240812-0139", "Model": "MOD-12345-A", "Time": "14:24:42", "Cycle": "4.5 s", "Result": "PASS"},
    ]
    st.dataframe(recent_data, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_live_inspection(services):
    st.markdown('<div class="eyebrow">OPERATOR STATION</div><h1 style="color:#0b2947; margin:0 0 16px 0; font-family:\'Arial Narrow\'; font-size:2rem;">Live Inspection</h1>', unsafe_allow_html=True)

    st.markdown("""
    <div class="info-strip">
      <div class="info-item"><span>Work Order</span><strong>WO-DEMO-001</strong></div>
      <div class="info-item"><span>Product Model</span><strong>DEMO-HARNESS-001</strong></div>
      <div class="info-item"><span>Description</span><strong>Client Wire Harness Sample</strong></div>
      <div class="info-item"><span>Revision</span><strong>V1.0</strong></div>
      <div class="info-item"><span>Barcode</span><strong>DEMO-WH-001</strong></div>
      <div class="info-item"><span>Operator</span><strong>Development</strong></div>
    </div>
    """, unsafe_allow_html=True)

    if "live_image" not in st.session_state:
        st.session_state["live_image"] = None
        st.session_state["live_result"] = None

    viewer_col, aside_col = st.columns([1.7, 1.0])

    with viewer_col:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">CAMERA 1 — TOP VIEW</div><div class="panel-title">Inspection visual stage</div>', unsafe_allow_html=True)

        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 1])
        with ctrl_col1:
            if st.button("📁 Load demo image", use_container_width=True):
                demo = load_sample_image()
                if demo is not None:
                    st.session_state["live_image"] = demo
                    st.session_state["live_result"] = None
                else:
                    st.error("Demo image not found in data/test_images.")
        with ctrl_col2:
            uploaded = st.file_uploader("Upload test image", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
            if uploaded is not None:
                file_bytes = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
                decoded = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                st.session_state["live_image"] = decoded
                st.session_state["live_result"] = None
        with ctrl_col3:
            if st.button("▶️ Start inspection", type="primary", disabled=st.session_state["live_image"] is None, use_container_width=True):
                with st.spinner("Evaluating 12 checkpoints on harness..."):
                    db = SessionLocal()
                    try:
                        model = db.query(ProductModel).filter_by(model_id="DEMO-HARNESS-001").first()
                        checkpoints = db.query(Checkpoint).filter_by(model_id="DEMO-HARNESS-001", enabled=True).all()
                        st.session_state["live_result"] = services["mock_inspection"].evaluate(model, checkpoints, cycle_time_seconds=2.0)
                    finally:
                        db.close()

        img = st.session_state["live_image"]
        result = st.session_state["live_result"]

        if img is not None:
            if result is not None:
                annotated = annotate_inspection_image(img, result.results)
                st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_container_width=True, caption=f"Annotated Inspection Image ({img.shape[1]} × {img.shape[0]} px)")
            else:
                st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), use_container_width=True, caption=f"Loaded Raw Image ({img.shape[1]} × {img.shape[0]} px)")
        else:
            st.markdown('<div class="evidence-note">Choose an image to preview it. Inspection runs only after you press <strong>Start inspection</strong>.</div>', unsafe_allow_html=True)
            st.info("No wire harness image loaded. Click 'Load demo image' or upload a file above to begin.")

        st.markdown('</div>', unsafe_allow_html=True)

    with aside_col:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">INSPECTION OUTCOME</div><div class="panel-title">Overall result</div>', unsafe_allow_html=True)

        if result is None:
            st.markdown('<div class="overall-box overall-box--ready">READY</div>', unsafe_allow_html=True)
            st.caption("Upload or load an image, then press START INSPECTION.")
        else:
            box_class = "overall-box--pass" if result.state == "PASS" else "overall-box--ng"
            st.markdown(f'<div class="overall-box {box_class}">{result.state}</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #edf1f5;">
              <span>Total Checkpoints</span><strong>{result.total_checkpoints}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #edf1f5; color:#16824b;">
              <span>Passed</span><strong>{result.passed}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #edf1f5; color:#c93038;">
              <span>Failed</span><strong>{result.failed}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #edf1f5;">
              <span>Cycle Time</span><strong>{result.cycle_time_seconds:.1f} s</strong>
            </div>
            """, unsafe_allow_html=True)

            ng_results = [r for r in result.results if r.status == "NG"]
            if ng_results:
                st.markdown('<div style="margin-top:16px;" class="eyebrow">DEFECT DETAILS</div>', unsafe_allow_html=True)
                for ng in ng_results:
                    st.markdown(f"""
                    <div class="ng-card">
                      <strong>🚨 {ng.checkpoint_id}: {ng.checkpoint_name}</strong>
                      <p><strong>Category:</strong> {ng.category} | <strong>Type:</strong> {ng.inspection_type}</p>
                      <p><strong>Expected:</strong> {ng.expected_value} | <strong>Actual:</strong> {ng.actual_value}</p>
                      <p><strong>Confidence:</strong> {ng.confidence*100:.1f}%</p>
                      <p><em>{ng.status_reason}</em></p>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


def render_engineering_view(services):
    st.markdown('<div class="eyebrow">VISION ENGINEERING</div><h1 style="color:#0b2947; margin:0 0 16px 0; font-family:\'Arial Narrow\'; font-size:2rem;">Engineering View</h1>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🔬 Segmentation Diagnostics",
        "🌐 Harness Graph Topology",
        "🎨 Colour Inspection (CP-008)",
        "📋 Checkpoint Configuration",
    ])

    sample = load_sample_image()

    with tab1:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">IMAGE PROCESSING STAGES</div><div class="panel-title">Feasibility Segmentation Pipeline</div>', unsafe_allow_html=True)
        if sample is not None:
            seg_result = services["segmentation"].segment(sample)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Harness Occupancy", f"{seg_result.metrics.harness_occupied_percentage:.2f}%")
            m2.metric("Contours Count", seg_result.metrics.contour_count)
            m3.metric("Otsu Threshold", seg_result.metrics.otsu_threshold)
            m4.metric("Noise Removed", seg_result.metrics.removed_component_count)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.image(seg_result.binary_mask, caption="1 · Binary Mask (Inverted Otsu)", use_container_width=True)
            with c2:
                st.image(cv2.cvtColor(seg_result.contour_image, cv2.COLOR_BGR2RGB), caption="2 · External Contours", use_container_width=True)
            with c3:
                st.image(seg_result.skeleton_image, caption="3 · Centreline Skeleton", use_container_width=True)
        else:
            st.error("Sample image not found in data/test_images.")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">TOPOLOGY MEASUREMENTS</div><div class="panel-title">Experimental Harness Graph</div>', unsafe_allow_html=True)
        if sample is not None:
            seg_res = services["segmentation"].segment(sample)
            graph_res = services["graph"].analyse(seg_res.binary_mask, base_image=sample)

            g1, g2, g3 = st.columns(3)
            g1.metric("Total Wire Centreline", f"{graph_res.metrics.total_wire_length_pixels:,.1f} px")
            g2.metric("Extracted Branches", graph_res.metrics.extracted_branch_count)
            g3.metric("Junctions / Terminals", f"{graph_res.metrics.clustered_junction_count} / {graph_res.metrics.topology_terminal_count}")

            v1, v2 = st.columns(2)
            with v1:
                st.image(cv2.cvtColor(graph_res.annotated_image, cv2.COLOR_BGR2RGB), caption="Graph Overlay (Skeleton & Nodes)", use_container_width=True)
            with v2:
                st.image(graph_res.skeleton_image, caption="1-pixel Skeleton Representation", use_container_width=True)

            st.subheader("Node-to-node branch distances")
            branches_table = [
                {
                    "Branch": b.branch_id,
                    "Nodes": f"{b.source_node_id} → {b.target_node_id}",
                    "Path (px)": f"{b.path_length_pixels:.2f}",
                    "Straight (px)": f"{b.straight_distance_pixels:.2f}",
                    "Orientation": f"{b.orientation_degrees:.1f}°",
                }
                for b in graph_res.measurements.node_to_node_distances
            ]
            st.dataframe(branches_table, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">COLOUR VERIFICATION</div><div class="panel-title">ROI Colour Inspection (CP-008)</div>', unsafe_allow_html=True)
        db = SessionLocal()
        try:
            cp = db.query(Checkpoint).filter_by(checkpoint_id="CP-008").first()
            if cp and sample is not None:
                color_eval = services["color"].inspect(sample, cp, debug=True)
                r_col1, r_col2 = st.columns([1, 2])
                with r_col1:
                    if color_eval.debug_images and "roi" in color_eval.debug_images:
                        st.image(cv2.cvtColor(color_eval.debug_images["roi"], cv2.COLOR_BGR2RGB), caption=f"CP-008 Crop ({cp.roi_width}×{cp.roi_height} px)", width=180)
                with r_col2:
                    st.write(f"**Checkpoint:** {cp.checkpoint_id} — {cp.checkpoint_name}")
                    st.write(f"**Expected Color:** `{cp.expected_value}`")
                    st.write(f"**Observed Color:** `{color_eval.observed_color}`")
                    st.write(f"**Mean RGB:** `{color_eval.mean_rgb}`")
                    st.write(f"**Mean HSV:** `{color_eval.mean_hsv}`")
                    st.write(f"**Result:** :{'green' if color_eval.status == 'PASS' else 'red'}[**{color_eval.status}**]")
                    st.caption(color_eval.status_reason)
        finally:
            db.close()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="industrial-panel"><div class="eyebrow">DATABASE RECORDS</div><div class="panel-title">Configured Checkpoints</div>', unsafe_allow_html=True)
        db = SessionLocal()
        try:
            all_cp = db.query(Checkpoint).filter_by(model_id="DEMO-HARNESS-001").all()
            table = [
                {
                    "ID": c.checkpoint_id,
                    "Name": c.checkpoint_name,
                    "Category": c.category,
                    "Type": c.inspection_type,
                    "X": c.roi_x,
                    "Y": c.roi_y,
                    "W": c.roi_width,
                    "H": c.roi_height,
                    "Expected": c.expected_value or "—",
                    "Tolerance": c.tolerance or "—",
                }
                for c in all_cp
            ]
            st.dataframe(table, use_container_width=True, hide_index=True)
        finally:
            db.close()
        st.markdown('</div>', unsafe_allow_html=True)


def render_models():
    st.markdown('<div class="eyebrow">CONFIGURATION</div><h1 style="color:#0b2947; margin:0 0 16px 0; font-family:\'Arial Narrow\'; font-size:2rem;">Models / Recipes</h1>', unsafe_allow_html=True)
    st.markdown('<div class="industrial-panel"><div class="panel-title">Configured Product Models</div>', unsafe_allow_html=True)
    models_data = [
        {
            "Model ID": "DEMO-HARNESS-001",
            "Model Name": "Client Wire Harness Sample",
            "Revision": "V1.0",
            "Checkpoints": "12 demo checkpoints",
            "Reference Image": "harness_sample_01.jpeg",
            "Created Date": "12 Aug 2026",
            "Status": "ACTIVE",
        }
    ]
    st.dataframe(models_data, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_cameras():
    st.markdown('<div class="eyebrow">DEVICE MANAGEMENT</div><h1 style="color:#0b2947; margin:0 0 16px 0; font-family:\'Arial Narrow\'; font-size:2rem;">Camera Setup</h1>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="industrial-panel" style="border-top:4px solid #16824b;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:1.6rem;">📷</span>
            <span class="status-pill status-pill--pass">CONNECTED</span>
          </div>
          <div class="panel-title">Camera 1 — Top View</div>
          <p style="color:#708094; font-size:0.85rem;">Overall geometry, routing, component presence, colour and calibrated measurement.</p>
          <hr style="margin:12px 0; border:0; border-top:1px solid #edf1f5;" />
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Type:</strong> Industrial GigE Vision</p>
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Resolution:</strong> 4096 × 3000 (12 MP)</p>
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Trigger:</strong> Software / Hardware TTL</p>
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Lens:</strong> 16mm Low Distortion</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="industrial-panel" style="border-top:4px solid #708094;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:1.6rem;">📹</span>
            <span class="status-pill status-pill--neutral">DISCONNECTED</span>
          </div>
          <div class="panel-title">Camera 2 — Angled View</div>
          <p style="color:#708094; font-size:0.85rem;">Connector seating, terminal orientation, lock features and raised components.</p>
          <hr style="margin:12px 0; border:0; border-top:1px solid #edf1f5;" />
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Type:</strong> Secondary USB3 Vision</p>
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Resolution:</strong> 3840 × 2160 (4K)</p>
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Trigger:</strong> Software</p>
          <p style="margin:4px 0; font-size:0.85rem;"><strong>Status:</strong> Standby / Optional</p>
        </div>
        """, unsafe_allow_html=True)


def render_reports(services):
    st.markdown('<div class="eyebrow">QUALITY RECORDS</div><h1 style="color:#0b2947; margin:0 0 16px 0; font-family:\'Arial Narrow\'; font-size:2rem;">Inspection Report</h1>', unsafe_allow_html=True)

    sample = load_sample_image()
    if sample is None:
        st.error("Demo sample image missing from data/test_images.")
        return

    db = SessionLocal()
    try:
        model = db.query(ProductModel).filter_by(model_id="DEMO-HARNESS-001").first()
        checkpoints = db.query(Checkpoint).filter_by(model_id="DEMO-HARNESS-001", enabled=True).all()
        report = services["reporting"].generate(model, checkpoints, sample)
    finally:
        db.close()

    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(f'<div class="metric-card-wrapper red"><div class="label">Overall Result</div><div class="value">{report.inspection.state}</div><div class="detail">{report.inspection.passed} PASS · {report.inspection.failed} NG</div></div>', unsafe_allow_html=True)
    r2.markdown(f'<div class="metric-card-wrapper"><div class="label">Total Wire Length</div><div class="value">{report.graph.metrics.total_wire_length_pixels:,.0f} px</div><div class="detail">Weighted 8-connected skeleton</div></div>', unsafe_allow_html=True)
    r3.markdown(f'<div class="metric-card-wrapper"><div class="label">Branches Extracted</div><div class="value">{report.graph.metrics.extracted_branch_count}</div><div class="detail">Resolved node paths</div></div>', unsafe_allow_html=True)
    r4.markdown(f'<div class="metric-card-wrapper"><div class="label">Junctions / Terminals</div><div class="value">{report.graph.metrics.clustered_junction_count} / {report.graph.metrics.topology_terminal_count}</div><div class="detail">Topology clusters</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="industrial-panel"><div class="eyebrow">MEASUREMENT EVIDENCE</div><div class="panel-title">Annotated Topology & Measurements</div>', unsafe_allow_html=True)
    st.image(cv2.cvtColor(report.annotated_image, cv2.COLOR_BGR2RGB), use_container_width=True, caption=f"Report ID: {report.report_id} · Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="industrial-panel"><div class="eyebrow">CHECKPOINT AUDIT TRAIL</div><div class="panel-title">All Evaluated Rules</div>', unsafe_allow_html=True)
    filter_val = st.radio("Status filter", ["ALL", "PASS", "NG"], horizontal=True)
    cp_rows = [
        {
            "ID": r.checkpoint_id,
            "Name": r.checkpoint_name,
            "Category": r.category,
            "Type": r.inspection_type,
            "Expected": r.expected_value or "—",
            "Actual": r.actual_value or "—",
            "Status": r.status,
            "Reason": r.status_reason,
        }
        for r in report.inspection.results
        if filter_val == "ALL" or r.status == filter_val
    ]
    st.dataframe(cp_rows, use_container_width=True, hide_index=True)

    csv_data = services["reporting"].export_csv(report)
    st.download_button(
        "📥 Download Official Inspection Report (CSV)",
        data=csv_data,
        file_name=f"inspection_report_{report.report_id}.csv",
        mime="text/csv",
        type="primary",
    )
    st.markdown('</div>', unsafe_allow_html=True)


def main():
    inject_custom_css()
    services = init_backend_services()

    with st.sidebar:
        st.markdown("""
        <div class="sidebar-brand">
          <h2>HARNESS<span>VISION</span></h2>
          <small>FINAL INSPECTION HMI</small>
        </div>
        """, unsafe_allow_html=True)

        st.caption("OPERATIONS")
        page = st.radio(
            "Navigation",
            [
                "🔎 Live Inspection",
                "📊 Dashboard",
                "🔬 Engineering View",
                "📦 Models / Recipes",
                "📹 Cameras",
                "📑 Reports",
            ],
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("""
        <div style="font-size:0.68rem; color:#7591a9; letter-spacing:1.5px; font-weight:700;">SYSTEM CONNECTION</div>
        <div style="display:flex; align-items:center; gap:8px; margin-top:8px;">
          <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#35ca7a;"></span>
          <span style="font-size:0.85rem; font-weight:700; color:#ffffff;">ONLINE</span>
        </div>
        <small style="color:#93acc1; font-size:0.75rem;">FastAPI & SQLite Ready</small>
        """, unsafe_allow_html=True)

    render_topbar()

    if page == "📊 Dashboard":
        render_dashboard()
    elif page == "🔎 Live Inspection":
        render_live_inspection(services)
    elif page == "🔬 Engineering View":
        render_engineering_view(services)
    elif page == "📦 Models / Recipes":
        render_models()
    elif page == "📹 Cameras":
        render_cameras()
    elif page == "📑 Reports":
        render_reports(services)


if __name__ == "__main__":
    main()
