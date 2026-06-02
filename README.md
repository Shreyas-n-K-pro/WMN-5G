# ⚡ 5G Core MCP Automation Lab

A state-of-the-art, Model Context Protocol (MCP) orchestrated **5G Standalone (SA) Core Automation, Monitoring, and Autonomous Self-Healing Lab** using **Open5GS**, **Docker Compose**, **Python FastMCP**, and **Streamlit**.

This platform provides an end-to-end local 5G lab designed for DevOps and automation testing, featuring direct MongoDB provisioning, real-time control plane signalling sequence simulations, live GTP-U user plane throughput analytics, and **ACANS closed-loop SLA enforcement** for autonomous remediation.

---

## 🏗️ Core System Architecture

Our lab models a fully compliant **5G Service Based Architecture (SBA)** with a complete Control Plane / User Plane split:

```
                  ┌──────────────────────────────────────────────┐
                  │      Service Based Architecture (SBA)        │
                  │   [ NRF - SCP - UDM - UDR - PCF - NSSF ]     │
                  └───────────────┬───────────────────┬──────────┘
                                  │ N11               │ N4
                           ┌──────┴──────┐     ┌──────┴──────┐
                           │     AMF     │     │     SMF     │
                           └──────┬──────┘     └──────┬──────┘
                                  │ N2 (NGAP)         │
                           ┌──────┴──────┐     ┌──────┴──────┐
 [ UE ] ══════════════════>│   gNodeB    │════>│     UPF     │ ════> [ Internet ]
          N1 (NAS/SUCI)    │ (Simulated) │ N3  │(User Plane) │ N6 (GTP-U/TUN)
                           └─────────────┘     └─────────────┘
```

---

## 🚀 Key Features

1. **Model Context Protocol (MCP) Server**: Exposes rich, typed tools to standard LLMs (like Cursor, Claude Desktop) allowing them to provision subscribers, read network metrics, scale user-plane nodes, run GTP-U ping diagnoses, and trace live call flows.
2. **Direct MongoDB Subscriber CRUD**: Leverages direct Python `PyMongo` integration with the Open5GS subscriber repository to bypass slow CLI binary wraps, making provisioning instantaneous.
3. **Dual-Mode RAN & Signaling Simulator**:
   - **Real Mode**: Orchestrates UERANSIM containers with `NET_ADMIN` privileges in Docker.
   - **Deterministic Simulation Mode**: An advanced Python state-machine (`tools/ue_simulator.py`) that models 5G NAS/NGAP signaling states (Registration -> Identity Request -> Auth Vector -> Security Setup -> Registration Accept -> PDU Session Accept) and records precise millisecond-level transition events.
4. **Interactive Streamlit Dashboard**: A beautiful dark-theme visual console featuring:
   - Slices & subscriber throughput telemetry charts.
   - Real-time signaling sequence logs.
   - Core topology, sequence flow, and architecture maps.
   - Interactive subscriber database provisioning forms.
5. **ACANS Autonomous Closed-Loop Self-Healing**:
   - Dedicated **ACANS Dashboard tab** to monitor SLA violations and healing actions.
   - Integrated service orchestration for **Load Generator**, **SLA Monitor**, and **Agent Loop** daemons.
   - Congestion/fault injection controls for eMBB flood simulation and live remediation replay.
   - MTTR tracking and autonomous decision logs for throttle/restore workflows.
6. **High-Resolution Vector Graphics**: Dynamic network topology, sequence charts, and throughput heatmaps auto-compiled using Matplotlib and NetworkX.

---

## 🛠️ CLI Orchestration and Launching

Start the entire environment (Dependencies validation, visual compilation, container initialization, WebUI ports exposure, Streamlit, and FastMCP) with a single command:

```bash
./run_lab.sh
```

### Script Workflow:
1. **Validation**: Confirms Docker, compose, and Python virtual environment state.
2. **Visual Rendering**: Compiles high-resolution network maps to `visualizations/`.
3. **Orchestration**: Prompts you to build containers, run live Docker Compose, or execute in **Local Signaling Simulation Mode** instantly (perfect for rapid local testing).
4. **Service Launcher**: Spawns the **Streamlit Dashboard** on `http://localhost:8501` and binds the **FastMCP Server** to standard transport.

---

## 🛠️ Exposed MCP Tools Reference

When running the FastMCP server, the following CLI and LLM-ready tools are available:

| Tool Name | Parameters | Purpose |
| :--- | :--- | :--- |
| `add_subscriber` | `imsi`, `key`, `opc`, `apn`, `sst`, `sd` | Provisions a new 5G subscriber with customized network slicing into MongoDB. |
| `delete_subscriber`| `imsi` | De-provisions and removes a subscriber by IMSI. |
| `list_subscribers` | None | Lists all active subscriber records in the core database. |
| `get_nf_status` | None | Scans container state and checks CPU/Memory utilization of active 5G NFs. |
| `run_open5gs_cli` | `container`, `command` | Executes a diagnostic command directly inside any core container. |
| `get_k8s_pods` | `namespace` | Scans and lists running Pods in Kubernetes (or shows Helm preview). |
| `scale_nf` | `nf_name`, `replicas` | Dynamically scales user plane or control plane NFs. |
| `run_gtp_ping` | `ue_ip`, `target` | Triggers ICMP ping from the active UERANSIM UE GTP tunnel. |
| `check_connectivity`| None | Diagnoses MongoDB, AMF, NRF, and UPF port health. |
| `get_network_topology`| None | Returns full structural JSON config mapping of the 5G Core subnets. |
| `simulate_registration`| `imsi`, `apn` | Triggers background NAS signaling simulation sequence. |
| `get_sla_status` | None | Retrieves current SLA violation state and active URLLC alert details from the monitor. |
| `apply_tc_remediation` | `action`, `slice_name`, `rate_mbit` | Applies dynamic Linux tc shaping (throttle/restore) for slice-level remediation. |

---

## 📂 Project Directory Structure

```
5g-mcp-automation/
├── .env                          # 5G IP mapping and subnet configurations
├── docker-compose.yml            # Multi-container core & simulation compose
├── requirements.txt              # Matplotlib, Streamlit, PyMongo, FastMCP versions
├── run_lab.sh                    # Unified CLI lab orchestrator (run-it-all)
├── streamlit_dashboard.py        # Streamlit dark-mode control console
├── base/                         # Open5GS image compilation context
├── mcp_server/
│   └── mcp_server.py             # FastMCP Automation Server
├── data/                         # Runtime ACANS telemetry, alerts, history, and agent logs
├── tools/
│   ├── subscriber_manager.py     # Direct Mongo CRUD script
│   ├── ue_simulator.py           # 5G SA signaling state machine
│   ├── generate_visualizations.py # Matplotlib graphics builder
│   ├── load_generator.py         # ACANS telemetry and congestion load emulator
│   ├── sla_monitor.py            # SLA breach detector + recovery history tracker
│   ├── apply_tc_rules.py         # Linux tc class/qdisc remediation orchestrator
│   ├── agent_loop.py             # Autonomous closed-loop decision and action daemon
│   └── test_closed_loop.py       # Programmatic ACANS integration validation
├── visualizations/
│   ├── 5g_call_flow.png          # Visual signaling sequence chart
│   ├── 5g_network_topology.png   # Active interface topology map
│   ├── architecture_overview.png # SBA Control Plane vs User Plane diagram
│   ├── traffic_heatmap.png       # Subscriber throughput data heatmap
│   └── simulation_state.json     # Live telemetry log sync cache
└── k8s/
    ├── open5gs-values.yaml       # K8s Helm core config
    └── ueransim-values.yaml      # K8s Helm RAN simulator config
```

---

## ⚡ Quick Testing Flows

1. Run `./run_lab.sh` and select **Mode 3** (Skip container orchestration/Local Sim) and **Service Option 1** (Launch both Streamlit and FastMCP).
2. Open your browser to `http://localhost:8501` to view the Live 5G Control Center.
3. Click **Start UE Registration Flow** in the sidebar.
4. Watch the logs update and the telemetry charts animate in real-time as the simulated UE transitions from `DEREGISTERED` to `PDU_SESSION_ESTABLISHED` and begins transmitting GTP user plane traffic!

### ACANS Closed-Loop Validation

Run the built-in autonomous healing integration flow:

```bash
python tools/test_closed_loop.py
```

This test automatically:
1. Starts `load_generator.py`, `sla_monitor.py`, and `agent_loop.py`.
2. Injects eMBB congestion and verifies URLLC SLA violation detection.
3. Confirms autonomous eMBB throttling and RTT recovery below threshold.
4. Clears congestion and validates de-escalation (restore to baseline).
5. Prints MTTR history and latest autonomous reasoning/action logs.
