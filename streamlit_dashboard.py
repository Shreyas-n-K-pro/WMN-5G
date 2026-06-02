#!/usr/bin/env python3
import streamlit as st
import pandas as pd
import numpy as np
import time
import json
import os
import subprocess
import signal
import glob
import random
from datetime import datetime
import sys
from tools.subscriber_manager import list_subscribers, add_subscriber, delete_subscriber

# Page Configuration for Sleek Modern Look
st.set_page_config(
    page_title="5G Core Automation Control Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode UI Styling
st.markdown("""
    <style>
    .stApp {
        background-color: #0E1117;
        color: #E2E8F0;
    }
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #06B6D4 0%, #EC4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .section-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #06B6D4;
        border-bottom: 2px solid #1A1D24;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1.0rem;
    }
    .metric-card {
        background-color: #1A1D24;
        border: 1px solid #3A3F4C;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .metric-value {
        font-size: 2.0rem;
        font-weight: 800;
        color: #10B981;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.1rem;
    }
    </style>
    """, unsafe_allow_html=True)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(_BASE_DIR, "visualizations", "simulation_state.json")
VIS_DIR = os.path.join(_BASE_DIR, "visualizations")

def _default_state():
    return {
        "imsi": "999700000000001",
        "state": "DEREGISTERED",
        "ue_ip": "0.0.0.0",
        "apn": "internet",
        "logs": [],
        "metrics": {"tx_packets": 0, "rx_packets": 0, "tx_bytes": 0, "rx_bytes": 0, "latency_ms": 0, "dl_mbps": 0, "ul_mbps": 0}
    }

def list_simulation_state_files():
    # include the legacy single file plus any sim_*.json files
    files = []
    try:
        files.extend(glob.glob(os.path.join(VIS_DIR, "sim_*.json")))
        if os.path.exists(STATE_FILE):
            files.append(STATE_FILE)
    except Exception:
        pass
    # sort by modification time descending
    files = sorted(files, key=lambda p: os.path.getmtime(p), reverse=True)
    return files

def load_simulation_state(path=None):
    """Loads simulation state JSON from provided path, or the latest available."""
    if path:
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return _default_state()

    files = list_simulation_state_files()
    if files:
        try:
            with open(files[0], "r") as f:
                return json.load(f)
        except Exception:
            return _default_state()
    return _default_state()

def load_all_simulation_states():
    states = []
    for p in list_simulation_state_files():
        try:
            with open(p, "r") as f:
                data = json.load(f)
                data["_path"] = p
                data["_mtime"] = os.path.getmtime(p)
                states.append(data)
        except Exception:
            continue
    return states

def ensure_session_state():
    if 'sim_procs' not in st.session_state:
        st.session_state['sim_procs'] = {}  # key -> {pid, state_file, imsi, started_at}

# ==========================================
# Sidebar Controls & Orchestration
# ==========================================
st.sidebar.markdown("<h2 style='color:#06B6D4; font-weight:800;'>⚡ 5G LAB CONTROL</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("### 🛠️ Lab Node Operations")
if st.sidebar.button("🚀 Re-build Visualizations", use_container_width=True):
    with st.spinner("Generating diagrams..."):
        try:
            subprocess.run([sys.executable, "tools/generate_visualizations.py"], check=True)
            st.sidebar.success("✓ Visualizations Updated!")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

st.sidebar.markdown("### 📱 UE Signal Simulator")
ensure_session_state()
sim_imsi = st.sidebar.text_input("Simulate IMSI", value="999700000000001")
sim_apn = st.sidebar.text_input("PDU APN Context", value="internet")
sim_cycles = st.sidebar.number_input("Traffic cycles", min_value=1, max_value=1000, value=30)
sim_key = st.sidebar.text_input("USIM Key (K)", value="8baf473f2f8fd09487cccbd7097c6862")
sim_opc = st.sidebar.text_input("OPc", value="11111111111111111111111111111111")
poll_enable = st.sidebar.checkbox("Auto-refresh dashboard", value=True)
poll_interval = st.sidebar.slider("Poll interval (seconds)", min_value=1, max_value=10, value=3)

def start_simulation(imsi, apn, cycles, key, opc):
    # create unique state file for this sim
    ts = int(time.time())
    uid = f"{imsi}_{ts}_{random.randint(1000,9999)}"
    state_file = os.path.join(VIS_DIR, f"sim_{uid}.json")
    args = [sys.executable, "tools/ue_simulator.py", "--imsi", imsi, "--apn", apn, "--cycles", str(cycles), "--state-file", state_file, "--key", key, "--opc", opc]
    proc = subprocess.Popen(args)
    st.session_state['sim_procs'][str(proc.pid)] = {
        "pid": proc.pid,
        "state_file": state_file,
        "imsi": imsi,
        "apn": apn,
        "cycles": cycles,
        "started_at": ts
    }
    return proc.pid

def stop_simulation(pid):
    try:
        os.kill(int(pid), signal.SIGINT)
        time.sleep(0.2)
    except Exception:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except Exception:
            pass
    # remove from session state if present
    st.session_state['sim_procs'].pop(str(pid), None)

if st.sidebar.button("▶️ Start UE Registration Flow", use_container_width=True):
    st.sidebar.info("Starting UE simulation in background...")
    try:
        pid = start_simulation(sim_imsi, sim_apn, sim_cycles, sim_key, sim_opc)
        st.sidebar.success(f"Started simulation (pid={pid})")
    except Exception as e:
        st.sidebar.error(f"Failed to start simulator: {e}")

# Active simulations list and controls
if st.session_state.get('sim_procs'):
    st.sidebar.markdown("#### Active Simulations")
    remove_pid = None
    for pid, info in list(st.session_state['sim_procs'].items()):
        started = datetime.fromtimestamp(info['started_at']).strftime('%Y-%m-%d %H:%M:%S')
        st.sidebar.markdown(f"- **IMSI**: {info['imsi']} • **PID**: {pid} • started: {started}")
        if st.sidebar.button(f"⏹️ Stop {pid}", key=f"stop_{pid}"):
            stop_simulation(pid)
            st.sidebar.info(f"Stopping {pid}...")

    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Clear finished simulation records", use_container_width=True):
        # remove entries whose process no longer exists
        to_remove = []
        for pid, info in list(st.session_state['sim_procs'].items()):
            try:
                os.kill(int(pid), 0)
            except Exception:
                to_remove.append(pid)
        for p in to_remove:
            st.session_state['sim_procs'].pop(p, None)
        st.sidebar.success("Cleared finished records")

# Polling auto-refresh behavior
if poll_enable:
    time.sleep(poll_interval)
    # some Streamlit versions removed `experimental_rerun`; use query param tweak to force rerun
    try:
        st.experimental_set_query_params(_r=int(time.time()))
    except Exception:
        # fallback: try the old name if available
        try:
            st.experimental_rerun()
        except Exception:
            pass

# ==========================================
# Main Dashboard UI Layout
# ==========================================
st.markdown("<h1 class='main-title'>5G Core Lab Automation Control Center</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#64748B; font-size:1.1rem; margin-top:-0.5rem;'>Model Context Protocol (MCP) Orchestrated Open5GS Network Management</p>", unsafe_allow_html=True)

# Load current state
all_states = load_all_simulation_states()
select_options = ["Latest"] + [f"{os.path.basename(s.get('_path',''))} | IMSI:{s.get('imsi','?')}" for s in all_states]
selected = st.selectbox("Select simulation to view", options=select_options, index=0)
if selected == "Latest":
    state = load_simulation_state()
else:
    # find the matching path
    fname = selected.split(" | ")[0]
    target = os.path.join(VIS_DIR, fname)
    state = load_simulation_state(path=target)

# Live Stats / Telemetry Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>Subscriber State</div>
            <div class='metric-value' style='color:#06B6D4;'>{state.get("state", "UNKNOWN")}</div>
        </div>
        """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>Assigned UE IP</div>
            <div class='metric-value' style='color:#F59E0B;'>{(state.get("ue_ip") if state.get("ue_ip") and state.get("ue_ip")!="0.0.0.0" else '—')}</div>
        </div>
        """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>Active Slice APN</div>
            <div class='metric-value' style='color:#EC4899;'>{state.get("apn", "internet")}</div>
        </div>
        """, unsafe_allow_html=True)
with col4:
    metrics = state.get("metrics", {})
    lat = metrics.get("latency_ms", 0)
    st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>GTP Tunnel Latency</div>
            <div class='metric-value'>{lat} ms</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div class='section-title'>📡 Live Core Network Topology</div>", unsafe_allow_html=True)

tab_top, tab_flow, tab_heatmap, tab_arch = st.tabs([
    "🌐 Service Topology", "🔄 5G Signalling Sequence Flow", "🔥 Slice Traffic Heatmap", "🏗️ SBA Architecture Map"
])

with tab_top:
    top_path = f"{VIS_DIR}/5g_network_topology.png"
    if os.path.exists(top_path):
        st.image(top_path, caption="Open5GS 5G Standalone network interfaces and nodes routing map", use_container_width=True)
    else:
        st.warning("Network topology image not found. Click 'Re-build Visualizations' in the sidebar to generate.")

with tab_flow:
    col_img, col_log = st.columns([2, 1])
    with col_img:
        flow_path = f"{VIS_DIR}/5g_call_flow.png"
        if os.path.exists(flow_path):
            st.image(flow_path, caption="Dynamic 5G SA NAS & NGAP Signalling Protocol Flow", use_container_width=True)
        else:
            st.warning("Call flow image not found.")
    with col_log:
        st.markdown("<h4 style='color:#06B6D4;'>📜 Live Signalling Event Stream</h4>", unsafe_allow_html=True)
        logs = state.get("logs", [])
        if logs:
            for log in reversed(logs):
                st.markdown(f"**`{log.get('timestamp', '')}`** | `{log.get('source', '')}` ➔ `{log.get('destination', '')}`")
                st.info(f"{log.get('message', '')}")
        else:
            st.markdown("<p style='color:#64748B;'>No active signalling events recorded. Start registration in the sidebar.</p>", unsafe_allow_html=True)

with tab_heatmap:
    heat_path = f"{VIS_DIR}/traffic_heatmap.png"
    if os.path.exists(heat_path):
        st.image(heat_path, caption="Bandwidth Consumption Heatmap (Mbps) across slices", use_container_width=True)
    else:
        st.warning("Heatmap not found.")

with tab_arch:
    arch_path = f"{VIS_DIR}/architecture_overview.png"
    if os.path.exists(arch_path):
        st.image(arch_path, caption="Open5GS Control Plane SBA bus and User Plane UPF interface separation", use_container_width=True)
    else:
        st.warning("Architecture diagram not found.")

# ==========================================
# Real-Time Telemetry Performance Charts
# ==========================================
st.markdown("<div class='section-title'>📈 Live GTP User Plane Telemetry</div>", unsafe_allow_html=True)
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("#### User Plane Throughput (Mbps)")
    # Generate mock live timeseries data matching current state rates
    curr_dl = metrics.get("dl_mbps", 0) if state.get("state") == "DATA_TRANSFER" else 0
    curr_ul = metrics.get("ul_mbps", 0) if state.get("state") == "DATA_TRANSFER" else 0
    
    chart_data = pd.DataFrame({
        "Downlink": [max(0, curr_dl + np.random.randint(-15, 15)) if curr_dl else 0 for _ in range(20)],
        "Uplink": [max(0, curr_ul + np.random.randint(-5, 5)) if curr_ul else 0 for _ in range(20)]
    })
    st.line_chart(chart_data)

with col_chart2:
    st.markdown("#### Round Trip Time Latency (RTT ms)")
    curr_lat = metrics.get("latency_ms", 0) if state.get("state") == "DATA_TRANSFER" else 0
    lat_data = pd.DataFrame({
        "RTT": [max(5, curr_lat + np.random.uniform(-2, 2)) if curr_lat else 0 for _ in range(20)]
    })
    st.area_chart(lat_data, color="#F59E0B")

# ==========================================
# Subscriber CRUD Management Grid
# ==========================================
st.markdown("<div class='section-title'>👥 Subscriber DB Administration</div>", unsafe_allow_html=True)

col_grid, col_crud = st.columns([2, 1])

with col_grid:
    st.markdown("#### Registered Subscribers (MongoDB)")
    try:
        subs = list_subscribers()
        if subs:
            df = pd.DataFrame(subs)
            # Style the dataframe beautifully
            st.dataframe(df, use_container_width=True)
        else:
            st.markdown("<p style='color:#64748B;'>No subscribers found in database.</p>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Cannot connect to MongoDB on localhost:27017. Ensure 'mongo' container is running: {e}")

with col_crud:
    st.markdown("#### ➕ Add Subscriber")
    with st.form("add_sub_form"):
        new_imsi = st.text_input("IMSI", placeholder="e.g. 001011234567895")
        new_key = st.text_input("USIM Key (K)", placeholder="32 hex character key")
        new_opc = st.text_input("Operator Code (OPc)", placeholder="32 hex character operator code")
        new_apn = st.text_input("APN Profile", value="internet")
        
        submitted = st.form_submit_button("Provision Subscriber")
        if submitted:
            try:
                res = add_subscriber(new_imsi, new_key, new_opc, new_apn)
                st.success(f"✓ Provisioned IMSI {new_imsi} successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add subscriber: {e}")

    st.markdown("#### 🗑️ Delete Subscriber")
    with st.form("del_sub_form"):
        del_imsi = st.text_input("IMSI to delete")
        del_submitted = st.form_submit_button("De-provision Subscriber", type="primary")
        if del_submitted:
            try:
                res = delete_subscriber(del_imsi)
                if res["status"] == "success":
                    st.success(f"✓ Removed IMSI {del_imsi} successfully!")
                    st.rerun()
                else:
                    st.error(res["message"])
            except Exception as e:
                st.error(f"Failed to delete subscriber: {e}")
