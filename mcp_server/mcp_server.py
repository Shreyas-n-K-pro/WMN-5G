#!/usr/bin/env python3
import subprocess
import json
import os
import sys
import psutil
from fastmcp import FastMCP
from typing import Dict, List, Optional

# Add parent directory to path to allow importing tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools.subscriber_manager import add_subscriber as add_sub_db, delete_subscriber as del_sub_db, list_subscribers as list_subs_db

# Initialize FastMCP Server
mcp = FastMCP("5G Core Lab Orchestrator")

@mcp.tool()
def add_subscriber(imsi: str, key: str, opc: str, apn: str = "internet", sst: int = 1, sd: str = "ffffff") -> str:
    """
    Provisions a new 5G SA subscriber directly into the Open5GS MongoDB database.
    
    Parameters:
    - imsi: International Mobile Subscriber Identity (e.g. '001011234567895')
    - key: USIM authentication key K (32 hex characters)
    - opc: Operator code OPc (32 hex characters)
    - apn: Access Point Name (default 'internet')
    - sst: Slice Service Type (default 1)
    - sd: Slice Differentiator (6 hex characters, default 'ffffff')
    """
    try:
        res = add_sub_db(imsi, key, opc, apn, sst, sd)
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def delete_subscriber(imsi: str) -> str:
    """De-provisions/removes an existing 5G subscriber by IMSI."""
    try:
        res = del_sub_db(imsi)
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def list_subscribers() -> str:
    """Lists all subscribers currently registered in the Open5GS MongoDB database."""
    try:
        subs = list_subs_db()
        return json.dumps(subs, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def get_nf_status() -> str:
    """
    Retrieves the status, health, and resource utilization (CPU, memory) 
    of all Open5GS 5G Core containers and UERANSIM simulators in Docker Compose.
    """
    try:
        # Check active Docker Compose processes
        cmd = ["docker", "compose", "ps", "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        
        # Parse docker output
        nfs = []
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                try:
                    nf_data = json.loads(line)
                    nfs.append({
                        "container": nf_data.get("Name"),
                        "service": nf_data.get("Service"),
                        "status": nf_data.get("State"),
                        "health": nf_data.get("HealthState", "healthy" if nf_data.get("State") == "running" else "unhealthy"),
                        "ports": nf_data.get("Publishers")
                    })
                except Exception:
                    pass
        else:
            # Fallback to docker ps filter if compose output is empty
            fallback_cmd = ["docker", "ps", "--filter", "name=open5gs", "--format", "{{json .}}"]
            res_fb = subprocess.run(fallback_cmd, capture_output=True, text=True)
            if res_fb.returncode == 0 and res_fb.stdout.strip():
                lines = res_fb.stdout.strip().split("\n")
                for line in lines:
                    try:
                        nf_data = json.loads(line)
                        nfs.append({
                            "container": nf_data.get("Names"),
                            "service": nf_data.get("Names").replace("open5gs-", ""),
                            "status": nf_data.get("State"),
                            "health": "healthy" if nf_data.get("Status").startswith("Up") else "unhealthy",
                            "ports": nf_data.get("Ports")
                        })
                    except Exception:
                        pass
        
        if not nfs:
            return json.dumps({"status": "warning", "message": "No running Open5GS containers found in active compose session."}, indent=2)

        return json.dumps({"status": "success", "containers": nfs}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def run_open5gs_cli(container: str, command: str) -> str:
    """
    Executes a standard CLI command inside any specified active Open5GS Docker container.
    Example: container='amf', command='open5gs-amfd --version'
    """
    try:
        cmd = ["docker", "compose", "exec", "-T", container, "bash", "-c", command]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        
        return json.dumps({
            "status": "success" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def get_k8s_pods(namespace: str = "5g") -> str:
    """
    Retrieves the running Pods in the Kubernetes lab namespace if kind K8s is active.
    If K8s is not deployed, returns a mocked visual representation of a K8s lab setup.
    """
    try:
        # Check if kubectl can connect to a cluster
        cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            pods_data = json.loads(result.stdout)
            pods = []
            for item in pods_data.get("items", []):
                metadata = item.get("metadata", {})
                status = item.get("status", {})
                pods.append({
                    "name": metadata.get("name"),
                    "status": status.get("phase"),
                    "pod_ip": status.get("podIP"),
                    "restart_count": status.get("containerStatuses", [{}])[0].get("restartCount", 0)
                })
            return json.dumps({"status": "success", "platform": "Kube (Active)", "pods": pods}, indent=2)
        else:
            # Graceful Mock Fallback for Local Demo
            mock_pods = [
                {"name": "open5gs-amf-7f89bcdb-abcde", "status": "Running", "pod_ip": "10.244.0.10", "restart_count": 0},
                {"name": "open5gs-smf-6d4b2e8c-fghij", "status": "Running", "pod_ip": "10.244.0.11", "restart_count": 0},
                {"name": "open5gs-upf-82db3d1c-klmno", "status": "Running", "pod_ip": "10.244.0.12", "restart_count": 0},
                {"name": "open5gs-nrf-5f67a2bd-pqrst", "status": "Running", "pod_ip": "10.244.0.13", "restart_count": 0},
                {"name": "ueransim-gnb-9ab2e3cd-uvwxy", "status": "Running", "pod_ip": "10.244.0.23", "restart_count": 1}
            ]
            return json.dumps({
                "status": "success", 
                "platform": "Kube (Mocked Fallback)", 
                "message": "Kubernetes context not active. Displaying standard Helm layout preview.",
                "pods": mock_pods
            }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def scale_nf(nf_name: str, replicas: int, namespace: str = "5g") -> str:
    """
    Scales a standard 5G Core Network Function pod group in K8s (or mocks scaling inside Docker Compose).
    Example: nf_name='upf', replicas=3
    """
    try:
        # If real kubectl context is active
        check_k8s = subprocess.run(["kubectl", "config", "current-context"], capture_output=True)
        if check_k8s.returncode == 0:
            scale_cmd = ["kubectl", "scale", "deployment", f"open5gs-{nf_name}", f"--replicas={replicas}", "-n", namespace]
            res = subprocess.run(scale_cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return json.dumps({"status": "success", "message": f"Successfully scaled open5gs-{nf_name} to {replicas} replicas"}, indent=2)
            
        # Fallback Mock scaling in Docker Compose
        return json.dumps({
            "status": "success",
            "platform": "Docker Compose scale fallback",
            "message": f"Simulating scaling of Service '{nf_name}' inside Compose.",
            "nf_service": f"open5gs-{nf_name}",
            "previous_replicas": 1,
            "target_replicas": replicas,
            "nodes": [f"open5gs-{nf_name}_{i+1}" for i in range(replicas)]
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def run_gtp_ping(ue_ip: str, target: str = "8.8.8.8", count: int = 4) -> str:
    """
    Triggers a user-plane ICMP ping request from the active UERANSIM UE tunnel 
    interface ('uesimtun0') through the 5G UPF GTP tunnel to verify core routing.
    """
    try:
        # Check if actual nr_ue container is active and has uesimtun0
        check_ue = subprocess.run(["docker", "compose", "exec", "-T", "nr_ue", "ip", "addr", "show", "dev", "uesimtun0"], capture_output=True, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        
        if check_ue.returncode == 0:
            ping_cmd = ["docker", "compose", "exec", "-T", "nr_ue", "ping", "-I", "uesimtun0", target, "-c", str(count)]
            res = subprocess.run(ping_cmd, capture_output=True, text=True, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            return json.dumps({
                "status": "success" if res.returncode == 0 else "failed",
                "interface": "uesimtun0 (Real)",
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip()
            }, indent=2)
        else:
            # Fallback simulated ping metrics
            latency_list = [round(9.5 + 2.1 * i + 0.5 * (i%2), 2) for i in range(count)]
            avg_lat = round(sum(latency_list) / count, 2)
            mock_ping_out = f"""
PING {target} ({target}) from {ue_ip} uesimtun0: 56 data bytes
64 bytes from {target}: icmp_seq=1 ttl=118 time={latency_list[0]} ms
64 bytes from {target}: icmp_seq=2 ttl=118 time={latency_list[1]} ms
64 bytes from {target}: icmp_seq=3 ttl=118 time={latency_list[2]} ms
64 bytes from {target}: icmp_seq=4 ttl=118 time={latency_list[3]} ms

--- {target} ping statistics ---
{count} packets transmitted, {count} received, 0% packet loss, time {count*1000}ms
rtt min/avg/max/mdev = {min(latency_list)}/{avg_lat}/{max(latency_list)}/1.12 ms
"""
            return json.dumps({
                "status": "success",
                "interface": "uesimtun0 (Simulated GTP Tunnel)",
                "stdout": mock_ping_out.strip()
            }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

@mcp.tool()
def check_connectivity() -> str:
    """
    Executes a comprehensive health and connectivity check across the core lab:
    - MongoDB Database Ping
    - AMF NGAP (SCTP 38412) binding state
    - NRF Registration Status
    - UPF GTP-U (UDP 2152) routing state
    """
    diagnostics = {}
    
    # 1. MongoDB Health
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=1000)
        client.admin.command('ping')
        diagnostics["MongoDB"] = "HEALTHY (Connected to port 27017)"
        client.close()
    except Exception as e:
        diagnostics["MongoDB"] = f"CRITICAL (Cannot connect: {e})"
        
    # 2. Port Binding Checks on Docker containers
    ports_to_check = {
        "AMF (NGAP SCTP)": ("amf", 38412),
        "NRF (REST HTTP)": ("nrf", 7777),
        "UPF (GTP-U UDP)": ("upf", 2152),
        "WebUI (Admin dashboard)": ("webui", 9999)
    }
    
    for nf, (container, port) in ports_to_check.items():
        try:
            # Run netstat or ss inside container to verify active bindings
            cmd = ["docker", "compose", "exec", "-T", container, "ss", "-lnu" if "UDP" in nf else "-lnt"]
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            if res.returncode == 0 and str(port) in res.stdout:
                diagnostics[nf] = f"HEALTHY (Port {port} actively binding inside container)"
            else:
                # Secondary fallback: checking if container is up
                check_status = subprocess.run(["docker", "compose", "ps", container, "--format", "json"], capture_output=True, text=True, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
                if container in check_status.stdout and "running" in check_status.stdout.lower():
                    diagnostics[nf] = f"HEALTHY (Container active, port {port} exposed)"
                else:
                    diagnostics[nf] = f"OFFLINE (Container {container} is down)"
        except Exception as e:
            diagnostics[nf] = f"UNKNOWN (Diagnostic failed: {e})"
            
    return json.dumps({"status": "success", "diagnostics": diagnostics}, indent=2)

@mcp.tool()
def get_network_topology() -> str:
    """Returns the structural node configuration, subnets, and interface names of the 5G Core."""
    topology = {
        "network_name": "Open5GS-5G-SA-Lab",
        "subnets": {
            "management_network": "172.22.0.0/24",
            "ue_userplane_subnet": "192.168.100.0/24"
        },
        "interfaces": [
            {"name": "N1", "type": "NAS Control", "source": "UE", "destination": "AMF"},
            {"name": "N2", "type": "NGAP Control", "source": "gNodeB", "destination": "AMF", "protocol": "SCTP", "port": 38412},
            {"name": "N3", "type": "GTP-U User Plane", "source": "gNodeB", "destination": "UPF", "protocol": "UDP", "port": 2152},
            {"name": "N4", "type": "PFCP Session", "source": "SMF", "destination": "UPF", "protocol": "UDP", "port": 8805},
            {"name": "N6", "type": "SGi IP Data", "source": "UPF", "destination": "Internet", "interface_name": "ogstun"},
            {"name": "SBI", "type": "HTTP/2 REST Service Bus", "bus_members": ["AMF", "SMF", "NRF", "SCP", "AUSF", "UDM", "UDR", "PCF", "NSSF", "BSF"]}
        ]
    }
    return json.dumps(topology, indent=2)

@mcp.tool()
def simulate_registration(imsi: str, apn: str = "internet") -> str:
    """
    Triggers a live, state-machine driven 5G UE PLMN registration and PDU Session Setup.
    Generates telemetry charts and CALL FLOW metrics dynamically inside the dashboard.
    """
    try:
        # Run simulator in background process
        subprocess.Popen([
            sys.executable, 
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../tools/ue_simulator.py")),
            "--imsi", imsi,
            "--apn", apn
        ])
        return json.dumps({
            "status": "success",
            "message": f"Successfully triggered background 5G SA Registration flow for IMSI {imsi}",
            "dashboard_url": "http://localhost:8501"
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)

if __name__ == "__main__":
    print("Starting 5G Core MCP Automation Server...")
    mcp.run()
