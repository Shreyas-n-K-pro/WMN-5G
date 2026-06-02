#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import requests
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ALERT_FILE = os.path.join(DATA_DIR, "alert_state.json")
TC_STATE_FILE = os.path.join(DATA_DIR, "tc_state.json")
LOG_FILE = os.path.join(DATA_DIR, "agent_log.jsonl")

SYSTEM_PROMPT = """You are an autonomous 5G network management agent (ACANS).
You have two tools: get_sla_status and apply_tc_remediation.

Every time you are called:
1. Call get_sla_status to check for SLA violations.
2. If violation_active is false:
   - If the eMBB slice is currently throttled, you should restore it to baseline.
     Respond: {"action": "restore_embb", "reason": "SLA is healthy and stable. De-escalating traffic shaping on eMBB and restoring baseline capacity."}
   - Else, respond: {"action": "none", "reason": "SLA is fully secure. Active monitoring in progress."}
3. If violation_active is true and slice is URLLC with high RTT:
   - The cause is background load from the competing eMBB slice.
   - Throttling eMBB protects URLLC low-latency guarantees.
   - Call apply_tc_remediation with action=throttle, slice_name=eMBB, rate_mbit=20.
   - Respond: {"action": "throttle_embb", "reason": "Critical SLA violation detected on URLLC slice due to high latency. Throttling competing eMBB slice to 20 Mbps to restore low-latency guarantee.", "expected_recovery_ms": 2500}
4. Always respond ONLY with a single JSON object. No markdown, no prose, no code blocks."""

def check_tc_throttled():
    if os.path.exists(TC_STATE_FILE):
        try:
            with open(TC_STATE_FILE, "r") as f:
                state = json.load(f)
                return state.get("eMBB", {}).get("throttled", False)
        except Exception:
            pass
    return False

def run_tc_command(action, slice_name, rate_mbit=None):
    """Executes apply_tc_rules.py utility directly."""
    try:
        from tools.apply_tc_rules import apply_remediation
        res = apply_remediation(slice_name, action, rate_mbit)
        print(f"[Agent Action] Executed remediation: {res}")
        return res
    except Exception as e:
        # Fallback to shell execution if imports fail in runtime
        import subprocess
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apply_tc_rules.py")
        cmd = [sys.executable, script_path, "--action", action, "--slice", slice_name]
        if rate_mbit:
            cmd += ["--rate", str(rate_mbit)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(f"[Agent Action] Executed shell remediation: {res.stdout.strip()}")
        return res.stdout.strip()

def local_expert_reasoner(alert_state, is_throttled):
    """Fallback high-fidelity reasoning engine simulating Claude offline."""
    violation_active = alert_state.get("violation_active", False)
    
    if not violation_active:
        if is_throttled:
            # Healing has occurred, we can now safely de-escalate and restore eMBB
            run_tc_command("restore", "eMBB")
            return {
                "action": "restore_embb",
                "reason": "SLA is healthy (Avg URLLC RTT is stable). De-escalating traffic shaping and restoring eMBB slice to its 50 Mbps baseline capacity.",
                "expected_recovery_ms": 1000
            }
        else:
            return {
                "action": "none",
                "reason": "SLA is fully secure (Avg URLLC RTT is healthy at baseline parameters). No anomalies detected. Continuous closed-loop monitoring active."
            }
    else:
        # Violation is active!
        violations = alert_state.get("violations", [])
        avg_rtt = violations[0].get("value", 0.0) if violations else 0.0
        
        if not is_throttled:
            # We need to throttle eMBB
            run_tc_command("throttle", "eMBB", 20)
            return {
                "action": "throttle_embb",
                "reason": f"SLA monitor reports critical latency degradation on URLLC slice (Avg RTT is {avg_rtt:.2f}ms, exceeding 20ms threshold). Congestion is caused by competing eMBB slice flood. Executing HTB traffic-shaping to cap eMBB bandwidth at 20 Mbps and restore slice isolation.",
                "expected_recovery_ms": 2500
            }
        else:
            # Already throttled, waiting for recovery cycles
            return {
                "action": "wait",
                "reason": f"eMBB slice is already throttled to 20 Mbps. Current Avg RTT is {avg_rtt:.2f}ms. Waiting for qdisc buffers to flush and telemetry samples to recover.",
                "expected_recovery_ms": 1500
            }

def run_agent_step():
    # Load alert state
    alert_state = {"violation_active": False, "violations": []}
    if os.path.exists(ALERT_FILE):
        try:
            with open(ALERT_FILE, "r") as f:
                alert_state = json.load(f)
        except Exception:
            pass
            
    is_throttled = check_tc_throttled()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    # Try calling Claude API if API key is provided
    agent_response = None
    if api_key:
        print("[Agent Loop] Invoking Claude via Anthropic API...")
        try:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            prompt_payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 512,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": f"Current alert state: {json.dumps(alert_state)}. eMBB currently throttled: {is_throttled}."}
                ]
            }
            resp = requests.post("https://api.anthropic.com/v1/messages", json=prompt_payload, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                text_out = resp.json()["content"][0]["text"].strip()
                agent_response = json.loads(text_out)
                
                # Execute action based on Claude's decision
                action = agent_response.get("action")
                if action == "throttle_embb" and not is_throttled:
                    run_tc_command("throttle", "eMBB", 20)
                elif action == "restore_embb" and is_throttled:
                    run_tc_command("restore", "eMBB")
            else:
                print(f"[Agent Loop] Anthropic API returned code {resp.status_code}. Falling back to Local expert system.")
        except Exception as e:
            print(f"[Agent Loop] Anthropic connection failed ({e}). Falling back to Local expert system.")
            
    if agent_response is None:
        # Fallback to the High-Fidelity Heuristics Reasoner
        agent_response = local_expert_reasoner(alert_state, is_throttled)
        
    # Write to agent log
    timestamp = datetime.utcnow().isoformat() + "Z"
    log_entry = {
        "timestamp": timestamp,
        "agent_response": agent_response
    }
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
        
    return log_entry

def main_loop(poll_interval=5.0):
    print("ACANS Closed-Loop Agent daemon initialized.")
    print("Polling SLA alerts and executing self-healing actions...")
    
    while True:
        try:
            entry = run_agent_step()
            resp = entry["agent_response"]
            print(f"[{entry['timestamp']}] Action: {resp.get('action')} | Reason: {resp.get('reason')[:80]}...")
        except Exception as e:
            print(f"[Agent Loop] Error in step execution: {e}")
            
        time.sleep(poll_interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACANS Closed-Loop LLM Agent Daemon")
    parser.add_argument("--interval", type=float, default=5.0, help="Alert polling interval in seconds")
    args = parser.parse_args()
    
    try:
        main_loop(args.interval)
    except KeyboardInterrupt:
        print("\nAgent Loop stopped.")
