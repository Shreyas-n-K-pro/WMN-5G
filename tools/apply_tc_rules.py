#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
TC_STATE_FILE = os.path.join(DATA_DIR, "tc_state.json")

def load_tc_state():
    if os.path.exists(TC_STATE_FILE):
        try:
            with open(TC_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "eMBB": {"rate_mbit": 50, "ceil_mbit": 50, "throttled": False},
        "URLLC": {"rate_mbit": 10, "ceil_mbit": 20, "throttled": False}
    }

def save_tc_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def run_command_in_upf(cmd_list):
    """Executes command inside UPF container if it is running, else logs simulation fallback."""
    # First, check if UPF container is running
    try:
        check_proc = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=upf"], 
            capture_output=True, text=True
        )
        upf_active = bool(check_proc.stdout.strip())
    except Exception:
        upf_active = False

    if upf_active:
        full_cmd = ["docker", "exec", "upf"] + cmd_list
        print(f"[Real Mode] Executing: {' '.join(full_cmd)}")
        res = subprocess.run(full_cmd, capture_output=True, text=True)
        return {
            "status": "success" if res.returncode == 0 else "failed",
            "exit_code": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip()
        }
    else:
        print(f"[Simulated Mode] Executing dummy: {' '.join(cmd_list)}")
        return {
            "status": "success",
            "exit_code": 0,
            "stdout": "Simulated output: Command executed successfully.",
            "stderr": ""
        }

def initialize_tc():
    print("Initializing root qdisc and classes on dev ogstun...")
    # Clean previous settings if any
    run_command_in_upf(["tc", "qdisc", "del", "dev", "ogstun", "root"])
    
    # Create root htb qdisc
    res = run_command_in_upf(["tc", "qdisc", "add", "dev", "ogstun", "root", "handle", "1:", "htb", "default", "30"])
    
    # Add eMBB Class (capped at 50 Mbps default)
    run_command_in_upf(["tc", "class", "add", "dev", "ogstun", "parent", "1:", "classid", "1:10", "htb", "rate", "50mbit", "ceil", "50mbit"])
    
    # Add URLLC Class (guaranteed 10 Mbps, ceil 20 Mbps, priority 1)
    run_command_in_upf(["tc", "class", "add", "dev", "ogstun", "parent", "1:", "classid", "1:20", "htb", "rate", "10mbit", "ceil", "20mbit", "prio", "1"])
    
    # Add TBF leaf qdisc to URLLC to enforce low latency/burst limits
    run_command_in_upf(["tc", "qdisc", "add", "dev", "ogstun", "parent", "1:20", "handle", "20:", "tbf", "rate", "10mbit", "burst", "32kbit", "latency", "10ms"])
    
    # Attach Filters targeting default static UE IPs
    # UE-1 eMBB is 192.168.100.2
    run_command_in_upf(["tc", "filter", "add", "dev", "ogstun", "parent", "1:", "protocol", "ip", "u32", "match", "ip", "dst", "192.168.100.2/32", "flowid", "1:10"])
    
    # UE-2 URLLC is 192.168.100.3
    run_command_in_upf(["tc", "filter", "add", "dev", "ogstun", "parent", "1:", "protocol", "ip", "u32", "match", "ip", "dst", "192.168.100.3/32", "flowid", "1:20"])
    
    state = {
        "eMBB": {"rate_mbit": 50, "ceil_mbit": 50, "throttled": False},
        "URLLC": {"rate_mbit": 10, "ceil_mbit": 20, "throttled": False}
    }
    save_tc_state(state)
    return "TC Rules Initialized."

def apply_remediation(slice_name, action, rate_mbit=None):
    state = load_tc_state()
    if slice_name not in state:
        return f"Error: Slice {slice_name} not found."
    
    classid = "1:10" if slice_name == "eMBB" else "1:20"
    
    if action == "throttle":
        target_rate = rate_mbit or (20 if slice_name == "eMBB" else 5)
        cmd = ["tc", "class", "change", "dev", "ogstun", "parent", "1:", "classid", classid, "htb", "rate", f"{target_rate}mbit", "ceil", f"{target_rate}mbit"]
        res = run_command_in_upf(cmd)
        
        state[slice_name]["rate_mbit"] = target_rate
        state[slice_name]["ceil_mbit"] = target_rate
        state[slice_name]["throttled"] = True
        save_tc_state(state)
        return f"Throttled {slice_name} to {target_rate} Mbps. Result: {res['status']}"
        
    elif action == "restore":
        default_rate = 50 if slice_name == "eMBB" else 10
        default_ceil = 50 if slice_name == "eMBB" else 20
        cmd = ["tc", "class", "change", "dev", "ogstun", "parent", "1:", "classid", classid, "htb", "rate", f"{default_rate}mbit", "ceil", f"{default_ceil}mbit"]
        res = run_command_in_upf(cmd)
        
        state[slice_name]["rate_mbit"] = default_rate
        state[slice_name]["ceil_mbit"] = default_ceil
        state[slice_name]["throttled"] = False
        save_tc_state(state)
        return f"Restored {slice_name} to defaults ({default_rate}/{default_ceil} Mbps). Result: {res['status']}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACANS Traffic Control Orchestrator")
    parser.add_argument("--action", required=True, choices=["init", "throttle", "restore"], help="TC rule action")
    parser.add_argument("--slice", choices=["eMBB", "URLLC"], help="Network slice")
    parser.add_argument("--rate", type=int, help="Target rate in Mbps")
    
    args = parser.parse_args()
    
    if args.action == "init":
        print(initialize_tc())
    else:
        if not args.slice:
            parser.error("--slice is required for throttle and restore actions")
        print(apply_remediation(args.slice, args.action, args.rate))
