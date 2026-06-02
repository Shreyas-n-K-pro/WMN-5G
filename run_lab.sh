#!/usr/bin/env bash
set -eo pipefail

# 5G Core MCP Automation Lab Orchestrator
# High-resolution console visual style
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0;0m'

clear
echo -e "${CYAN}${BOLD}======================================================================${NC}"
echo -e "${CYAN}${BOLD}     ⚡  5G CORE AUTOMATION LAB ORCHESTRATOR & MCP CONTROL  ⚡${NC}"
echo -e "${CYAN}${BOLD}======================================================================${NC}"
echo -e "Workspace: $(pwd)"
echo ""

# Ensure we are in the correct directory
cd "$(dirname "$0")"

# -------------------------------------------------------------
# 1. Dependency Checking
# -------------------------------------------------------------
echo -e "${BOLD}[Phase 1] Checking Core System Dependencies...${NC}"

# Docker
if command -v docker &> /dev/null; then
    echo -e "  ✓ Docker: ${GREEN}Detected (${$(docker --version)%%,*})${NC}"
else
    echo -e "  ✗ Docker: ${RED}Not found! Please install docker.${NC}"
fi

if docker compose version &> /dev/null; then
    echo -e "  ✓ Docker Compose: ${GREEN}Detected${NC}"
else
    echo -e "  ✗ Docker Compose: ${RED}Not found! Please install docker-compose-plugin.${NC}"
fi

# Python 3 & Virtual Environment
if [ -d ".venv" ]; then
    echo -e "  ✓ Python venv: ${GREEN}Active (.venv)${NC}"
    PYTHON="./.venv/bin/python3"
    PIP="./.venv/bin/pip"
else
    echo -e "  ⚠ Python venv: ${YELLOW}Not found. Initializing...${NC}"
    python3 -m pip install --user --break-system-packages virtualenv &> /dev/null || true
    python3 -m virtualenv .venv &> /dev/null || true
    if [ -f ".venv/bin/python3" ]; then
        PYTHON="./.venv/bin/python3"
        PIP="./.venv/bin/pip"
        $PIP install -r requirements.txt &> /dev/null
        echo -e "  ✓ Python venv: ${GREEN}Created and provisioned${NC}"
    else
        echo -e "  ✗ Python venv: ${RED}Failed to create. Falling back to system python3.${NC}"
        PYTHON="python3"
        PIP="pip3"
    fi
fi

# Make tools executable
chmod +x tools/subscriber_manager.py tools/ue_simulator.py tools/generate_visualizations.py

# -------------------------------------------------------------
# 2. Visualizations Layer Setup
# -------------------------------------------------------------
echo -e "\n${BOLD}[Phase 2] Generating Presentation Visualizations...${NC}"
if $PYTHON tools/generate_visualizations.py; then
    echo -e "  ✓ Visualizations: ${GREEN}Success (Topology, Call Flow, Heatmap, SBA Architecture)${NC}"
else
    echo -e "  ✗ Visualizations: ${RED}Failed to compile. Check python libraries.${NC}"
fi

# -------------------------------------------------------------
# 3. Docker Compose Orchestration Setup
# -------------------------------------------------------------
echo -e "\n${BOLD}[Phase 3] 5G SA Core Container Orchestration Options:${NC}"
echo -e "  [1] Start Docker Compose 5G Core & RAN Simulators (Requires images compiled)"
echo -e "  [2] Trigger compilation of Open5GS & UERANSIM images in background"
echo -e "  [3] Skip Docker setup (Run Local Signaling Simulation Mode instantly)"
read -rp "Select orchestrator mode [1-3] (Default: 3): " ORCH_MODE
ORCH_MODE=${ORCH_MODE:-3}

if [ "$ORCH_MODE" = "1" ]; then
    echo -e "\n${BOLD}Launching 5G Core Containers...${NC}"
    docker compose up -d
    
    echo -e "\n${YELLOW}Waiting for Subscriber database (MongoDB) to become available...${NC}"
    for i in {1..30}; do
        if docker compose exec -T mongo mongosh --eval "db.runCommand({ping:1})" &> /dev/null; then
            echo -e "${GREEN}✓ MongoDB is online! Port-forward active on localhost:27017${NC}"
            break
        fi
        sleep 2
    done
    
    # Provision default demo subscriber
    echo -e "\n${BOLD}Provisioning default UERANSIM test subscriber in MongoDB...${NC}"
    $PYTHON tools/subscriber_manager.py add \
        --imsi "999700000000001" \
        --key "8baf473f2f8fd09487cccbd7097c6862" \
        --opc "11111111111111111111111111111111" \
        --apn "internet" || true
    echo -e "${GREEN}✓ Default UERANSIM subscriber active!${NC}"

elif [ "$ORCH_MODE" = "2" ]; then
    echo -e "\n${BOLD}Launching background compilation for Open5GS & UERANSIM...${NC}"
    nohup docker build -t docker_open5gs base/ > base_build.log 2>&1 &
    nohup docker build -t docker_ueransim ueransim/ > ueransim_build.log 2>&1 &
    echo -e "${YELLOW}Builds started in the background! Logs: base_build.log, ueransim_build.log${NC}"
    echo -e "Running Local Simulation mode while build finishes..."

else
    echo -e "\n${GREEN}✓ Skipping container orchestration. Starting Local Signaling Simulation Mode.${NC}"
fi

# -------------------------------------------------------------
# 4. Service Launch: Streamlit Dashboard & MCP Server
# -------------------------------------------------------------
echo -e "\n${BOLD}[Phase 4] Service Launch Options:${NC}"
echo -e "  [1] Start Live Streamlit Dashboard & FastMCP Automation Server (Both)"
echo -e "  [2] Start Streamlit Dashboard only"
echo -e "  [3] Start FastMCP Automation Server only"
echo -e "  [4] Exit"
read -rp "Select service launcher [1-4] (Default: 1): " LAUNCH_MODE
LAUNCH_MODE=${LAUNCH_MODE:-1}

# Create a clean state file for immediate rendering
$PYTHON -c "
import os, json
os.makedirs('visualizations', exist_ok=True)
if not os.path.exists('visualizations/simulation_state.json'):
    with open('visualizations/simulation_state.json', 'w') as f:
        json.dump({'imsi':'999700000000001','state':'DEREGISTERED','ue_ip':'0.0.0.0','apn':'internet','logs':[],'metrics':{}}, f)
"

case "$LAUNCH_MODE" in
    1)
        echo -e "\n${BOLD}Starting Streamlit Dashboard and FastMCP server...${NC}"
        # Start Streamlit
        echo -e "${GREEN}→ Launching Streamlit on http://localhost:8501${NC}"
        nohup $PYTHON -m streamlit run streamlit_dashboard.py --server.port 8501 > streamlit.log 2>&1 &
        
        # Start MCP Server
        echo -e "${GREEN}→ Launching FastMCP Server on http://localhost:8000 (SSE Transport)${NC}"
        echo -e "${YELLOW}Press Ctrl+C to terminate services.${NC}"
        # Run FastMCP in foreground so user can monitor it or press Ctrl+C to exit
        $PYTHON mcp_server/mcp_server.py
        ;;
    2)
        echo -e "\n${BOLD}Starting Streamlit Dashboard...${NC}"
        echo -e "${GREEN}→ Launching Streamlit on http://localhost:8501${NC}"
        $PYTHON -m streamlit run streamlit_dashboard.py --server.port 8501
        ;;
    3)
        echo -e "\n${BOLD}Starting FastMCP Server...${NC}"
        $PYTHON mcp_server/mcp_server.py
        ;;
    *)
        echo -e "\nExiting orchestrator. Run './run_lab.sh' anytime to restart."
        exit 0
        ;;
esac
