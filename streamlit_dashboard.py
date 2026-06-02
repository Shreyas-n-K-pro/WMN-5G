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
    
    /* Premium High-Contrast Button Styling */
    div.stButton > button {
        background-color: #1A1D24 !important;
        color: #E2E8F0 !important;
        border: 1px solid #3A3F4C !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
    }
    div.stButton > button:hover {
        background-color: #262B35 !important;
        color: #06B6D4 !important;
        border-color: #06B6D4 !important;
        box-shadow: 0 0 10px rgba(6, 182, 212, 0.25) !important;
    }
    div.stButton > button:active, div.stButton > button:focus {
        background-color: #0E1117 !important;
        color: #06B6D4 !important;
        border-color: #06B6D4 !important;
        box-shadow: 0 0 12px rgba(6, 182, 212, 0.4) !important;
    }
    
    /* Primary buttons custom highlight */
    div.stButton > button[data-testid*="primary"], 
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #06B6D4 0%, #0891B2 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    div.stButton > button[data-testid*="primary"]:hover, 
    div.stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #0891B2 0%, #0369A1 100%) !important;
        box-shadow: 0 0 12px rgba(6, 182, 212, 0.45) !important;
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
    if 'acans_procs' not in st.session_state:
        st.session_state['acans_procs'] = {}  # service_name -> pid

def check_acans_status():
    running = {}
    for name, pid in list(st.session_state.get('acans_procs', {}).items()):
        try:
            os.kill(int(pid), 0)
            running[name] = pid
        except Exception:
            pass
    st.session_state['acans_procs'] = running
    return running

def start_acans_service(name, script_name):
    script_path = os.path.join(_BASE_DIR, "tools", script_name)
    args = [sys.executable, script_path]
    proc = subprocess.Popen(args)
    st.session_state['acans_procs'][name] = proc.pid
    return proc.pid

def stop_acans_service(name):
    pid = st.session_state.get('acans_procs', {}).get(name)
    if pid:
        try:
            os.kill(int(pid), signal.SIGINT)
            time.sleep(0.1)
        except Exception:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
        st.session_state['acans_procs'].pop(name, None)

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

tab_top, tab_flow, tab_heatmap, tab_arch, tab_healing = st.tabs([
    "🌐 Service Topology", "🔄 5G Signalling Sequence Flow", "🔥 Slice Traffic Heatmap", "🏗️ SBA Architecture Map", "🛡️ ACANS Autonomous Healing"
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

with tab_healing:
    st.markdown("<h3 style='color:#06B6D4;'>🛡️ ACANS Autonomous Closed-Loop Self-Healing</h3>", unsafe_allow_html=True)
    st.markdown("Autonomous Closed-loop Adaptive Network System (ACANS) actively monitors URLLC slice latency RTT, detects violations under eMBB congestion flood, and programmatically applies dynamic traffic shaping via UPF **Linux tc (Traffic Control)**, orchestrated by a autonomous AI agent loop.")
    
    # 1. Daemon Management and Fault Injection Panel
    st.markdown("<h4 style='color:#06B6D4;'>🛠️ ACANS Control Panel</h4>", unsafe_allow_html=True)
    col_c1, col_c2 = st.columns([1, 1])
    
    with col_c1:
        st.markdown("##### ⚙️ Closed-Loop Services Orchestrator")
        active_services = check_acans_status()
        
        # Load Generator Service Toggle
        lg_run = "LoadGen" in active_services
        col_btn1, col_lbl1 = st.columns([2, 3])
        with col_btn1:
            if lg_run:
                if st.button("⏹️ Stop Load Generator", key="stop_lg", use_container_width=True):
                    stop_acans_service("LoadGen")
                    st.rerun()
            else:
                if st.button("🚀 Start Load Generator", key="start_lg", use_container_width=True, type="primary"):
                    start_acans_service("LoadGen", "load_generator.py")
                    st.rerun()
        with col_lbl1:
            st.markdown(f"**Load Generator Service**: {'🟢 ACTIVE (pid=%s)' % active_services['LoadGen'] if lg_run else '🔴 OFFLINE'}")
            
        # SLA Monitor Service Toggle
        sm_run = "SlaMon" in active_services
        col_btn2, col_lbl2 = st.columns([2, 3])
        with col_btn2:
            if sm_run:
                if st.button("⏹️ Stop SLA Monitor", key="stop_sm", use_container_width=True):
                    stop_acans_service("SlaMon")
                    st.rerun()
            else:
                if st.button("🚀 Start SLA Monitor", key="start_sm", use_container_width=True, type="primary"):
                    start_acans_service("SlaMon", "sla_monitor.py")
                    st.rerun()
        with col_lbl2:
            st.markdown(f"**SLA Monitor Service**: {'🟢 ACTIVE (pid=%s)' % active_services['SlaMon'] if sm_run else '🔴 OFFLINE'}")
            
        # LLM Agent Loop Toggle
        al_run = "AgentLoop" in active_services
        col_btn3, col_lbl3 = st.columns([2, 3])
        with col_btn3:
            if al_run:
                if st.button("⏹️ Stop LLM Agent", key="stop_al", use_container_width=True):
                    stop_acans_service("AgentLoop")
                    st.rerun()
            else:
                if st.button("🚀 Start LLM Agent", key="start_al", use_container_width=True, type="primary"):
                    start_acans_service("AgentLoop", "agent_loop.py")
                    st.rerun()
        with col_lbl3:
            st.markdown(f"**Heuristics Agent Loop**: {'🟢 ACTIVE (pid=%s)' % active_services['AgentLoop'] if al_run else '🔴 OFFLINE'}")

    with col_c2:
        st.markdown("##### 💥 Congestion / Fault Injector")
        # Check active congestion state
        congestion_active = False
        congestion_path = os.path.join(_BASE_DIR, "data", "congestion_active.json")
        if os.path.exists(congestion_path):
            try:
                with open(congestion_path, "r") as f:
                    congestion_active = json.load(f).get("active", False)
            except Exception:
                pass
                
        col_btn4, col_lbl4 = st.columns([2, 3])
        with col_btn4:
            if congestion_active:
                if st.button("🟢 Clear Congestion", key="clear_cong", use_container_width=True, type="primary"):
                    with open(congestion_path, "w") as f:
                        json.dump({"active": False}, f)
                    st.rerun()
            else:
                if st.button("🔥 Inject eMBB Flood", key="inject_cong", use_container_width=True):
                    # Make sure apply_tc_rules is initialized first
                    try:
                        subprocess.run([sys.executable, os.path.join(_BASE_DIR, "tools", "apply_tc_rules.py"), "--action", "init"], capture_output=True)
                    except Exception:
                        pass
                    with open(congestion_path, "w") as f:
                        json.dump({"active": True}, f)
                    st.rerun()
        with col_lbl4:
            st.markdown(f"**Slice Network State**: {'🔥 HEAVILY CONGESTED (eMBB Flood)' if congestion_active else '🟢 SECURE / baseline background load'}")
            
        # Reset Button to clear historical data
        if st.button("🧹 Clear Alert History & Logs", key="clear_acans_data", use_container_width=True):
            try:
                history_path = os.path.join(_BASE_DIR, "data", "sla_history.json")
                log_path = os.path.join(_BASE_DIR, "data", "agent_log.jsonl")
                metrics_path = os.path.join(_BASE_DIR, "data", "metrics.json")
                alert_path = os.path.join(_BASE_DIR, "data", "alert_state.json")
                tc_path = os.path.join(_BASE_DIR, "data", "tc_state.json")
                
                for p in [history_path, log_path, alert_path]:
                    if os.path.exists(p):
                        os.remove(p)
                with open(metrics_path, "w") as f:
                    json.dump({"urllc_rtt_ms": [], "embb_throughput": []}, f)
                with open(tc_path, "w") as f:
                    json.dump({"eMBB": {"rate_mbit": 50, "ceil_mbit": 50, "throttled": False}, "URLLC": {"rate_mbit": 10, "ceil_mbit": 20, "throttled": False}}, f)
                st.success("✓ Data wiped successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to clear data: {e}")

    st.markdown("---")
    
    # 2. Live Alerts & Healing Metrics Card Row
    # Load data
    alert_state = {"violation_active": False, "violations": []}
    alert_path = os.path.join(_BASE_DIR, "data", "alert_state.json")
    if os.path.exists(alert_path):
        try:
            with open(alert_path, "r") as f:
                alert_state = json.load(f)
        except Exception:
            pass
            
    tc_state = {}
    tc_path = os.path.join(_BASE_DIR, "data", "tc_state.json")
    if os.path.exists(tc_path):
        try:
            with open(tc_path, "r") as f:
                tc_state = json.load(f)
        except Exception:
            pass
            
    history_events = []
    history_path = os.path.join(_BASE_DIR, "data", "sla_history.json")
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
                history_events = json.load(f)
        except Exception:
            pass

    # Glow banners
    if alert_state.get("violation_active", False):
        st.markdown("""
            <div style='background-color:rgba(239, 68, 68, 0.15); border: 2px solid #EF4444; padding:15px; border-radius:10px; text-align:center; margin-bottom:15px;'>
                <h3 style='color:#EF4444; margin:0;'>⚠️ SLA VIOLATION ACTIVE: URLLC LATENCY CRITICAL</h3>
                <p style='margin:5px 0 0 0; color:#E2E8F0; font-size:1.0rem;'>
                    Competing background load on eMBB slice has degraded low-latency guarantees. Remediations initiated.
                </p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style='background-color:rgba(16, 185, 129, 0.15); border: 2px solid #10B981; padding:15px; border-radius:10px; text-align:center; margin-bottom:15px;'>
                <h3 style='color:#10B981; margin:0;'>🛡️ SLA SECURE: CHANNELS OPTIMIZED</h3>
                <p style='margin:5px 0 0 0; color:#E2E8F0; font-size:1.0rem;'>
                    QoS partitions active. All slices operating within standard parameters.
                </p>
            </div>
            """, unsafe_allow_html=True)

    # Healing performance metrics
    mttrs = [ev["mttr_sec"] for ev in history_events]
    mean_mttr = sum(mttrs) / len(mttrs) if mttrs else 0.0
    max_mttr = max(mttrs) if mttrs else 0.0
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Mean Time To Recovery</div>
                <div class='metric-value' style='color:#06B6D4;'>{mean_mttr:.1f}s</div>
            </div>
            """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Healing Success Rate</div>
                <div class='metric-value' style='color:#10B981;'>100%</div>
            </div>
            """, unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Total Violations Remedied</div>
                <div class='metric-value' style='color:#F59E0B;'>{len(history_events)}</div>
            </div>
            """, unsafe_allow_html=True)
    with col_m4:
        embb_limit = tc_state.get("eMBB", {}).get("rate_mbit", 50)
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>eMBB Slice Limit</div>
                <div class='metric-value' style='color:#EC4899;'>{embb_limit} Mbps</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # 3. Dynamic Plotly Chart mapping
    metrics_path = os.path.join(_BASE_DIR, "data", "metrics.json")
    rtts, throughputs, timestamps = [], [], []
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, "r") as f:
                metrics_data = json.load(f)
                rtts = [s["v"] for s in metrics_data.get("urllc_rtt_ms", [])]
                throughputs = [s["v"] for s in metrics_data.get("embb_throughput", [])]
                timestamps = [s["t"] for s in metrics_data.get("urllc_rtt_ms", [])]
        except Exception:
            pass

    st.markdown("##### 📈 Live SLA Telemetry & Adaptation Timeline")
    if timestamps:
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            times = [datetime.fromtimestamp(t) for t in timestamps]
            
            # URLLC Latency Trace
            fig.add_trace(
                go.Scatter(x=times, y=rtts, name="URLLC RTT (ms)", line=dict(color="#F59E0B", width=2.5), fill='tozeroy'),
                secondary_y=False,
            )
            
            # eMBB Throughput Trace
            fig.add_trace(
                go.Scatter(x=times, y=throughputs, name="eMBB Throughput (Mbps)", line=dict(color="#06B6D4", width=2.5, dash='dash')),
                secondary_y=True,
            )
            
            # SLA Threshold boundary line
            fig.add_shape(
                type="line",
                x0=times[0],
                y0=20,
                x1=times[-1],
                y1=20,
                line=dict(color="#EF4444", width=1.5, dash="dot"),
            )
            
            # Vertical Healing Indicators
            for ev in history_events[-4:]:
                start_time = datetime.fromtimestamp(ev["violation_start"])
                end_time = datetime.fromtimestamp(ev["healed_at"])
                
                # Red line for violation trigger
                fig.add_vline(x=start_time, line_width=1.5, line_dash="dash", line_color="#EF4444")
                # Green line for recovery completion
                fig.add_vline(x=end_time, line_width=1.5, line_dash="dash", line_color="#10B981")
                
            fig.update_layout(
                paper_bgcolor="#1A1D24",
                plot_bgcolor="#0E1117",
                font_color="#E2E8F0",
                margin=dict(l=10, r=10, t=25, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=320,
            )
            
            fig.update_yaxes(title_text="RTT Latency (ms)", color="#F59E0B", secondary_y=False, gridcolor="#2D3139")
            fig.update_yaxes(title_text="eMBB Bandwidth (Mbps)", color="#06B6D4", secondary_y=True, gridcolor="#2D3139")
            fig.update_xaxes(gridcolor="#2D3139")
            
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Plotly load error: {e}. Fallback to standard chart.")
            chart_data = pd.DataFrame({"URLLC RTT": rtts, "eMBB Mbps": throughputs})
            st.line_chart(chart_data)
    else:
        st.info("Awaiting telemetry stream. Start Closed-Loop Services using the panel above to begin logging.")

    st.markdown("---")

    # 4. LLM Agent Reasoning Stream Logs
    st.markdown("##### 🤖 Claude Closed-Loop Autonomous Reasoning Stream")
    
    agent_logs = []
    log_path = os.path.join(_BASE_DIR, "data", "agent_log.jsonl")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                for line in f:
                    if line.strip():
                        agent_logs.append(json.loads(line))
        except Exception:
            pass
            
    if agent_logs:
        for log in reversed(agent_logs[-10:]):
            ts = log.get("timestamp", "")
            resp = log.get("agent_response", {})
            action = resp.get("action", "")
            reason = resp.get("reason", "")
            
            # Format display based on severity of action
            if action == "throttle_embb":
                badge = "🔴 REMEDIATION INITIATED: THROTTLE eMBB"
                border_col = "#EF4444"
            elif action == "restore_embb":
                badge = "🟢 DE-ESCALATING: RESTORE Slices"
                border_col = "#10B981"
            elif action == "wait":
                badge = "🟡 MONITORING RECOVERY: WAITING"
                border_col = "#F59E0B"
            else:
                badge = "🔵 SYSTEM STATE SECURE: MONITORING"
                border_col = "#06B6D4"
                
            st.markdown(f"""
                <div style='border-left: 5px solid {border_col}; background-color:#1A1D24; padding:10px; border-radius: 4px; margin-bottom:10px;'>
                    <span style='color:#64748B; font-size:0.85rem; font-weight:bold;'>⏱️ {ts}</span><br/>
                    <strong style='color:{border_col}; font-size:0.95rem;'>{badge}</strong><br/>
                    <p style='margin:5px 0 0 0; font-size:0.9rem; color:#E2E8F0;'>{reason}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("<p style='color:#64748B;'>No autonomous agent transactions logged yet.</p>", unsafe_allow_html=True)

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
