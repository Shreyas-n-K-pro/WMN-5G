#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
METRICS_FILE = os.path.join(DATA_DIR, "metrics.json")
ALERT_FILE = os.path.join(DATA_DIR, "alert_state.json")
HISTORY_FILE = os.path.join(DATA_DIR, "sla_history.json")

SLA_RTT_THRESHOLD = 20.0  # ms

def load_alert_state():
    if os.path.exists(ALERT_FILE):
        try:
            with open(ALERT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "violation_active": False,
        "violations": [],
        "last_checked": "",
        "violation_start_time": 0.0
    }

def save_alert_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ALERT_FILE, "w") as f:
        json.dump(state, f, indent=2)

def append_to_history(start_time, end_time, mttr_sec):
    os.makedirs(DATA_DIR, exist_ok=True)
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass
            
    history.append({
        "violation_start": start_time,
        "healed_at": end_time,
        "mttr_sec": round(mttr_sec, 2),
        "timestamp_str": datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
    })
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def monitor_loop(poll_interval=0.5):
    print("SLA Monitor daemon started. Listening for metrics...")
    
    while True:
        if not os.path.exists(METRICS_FILE):
            time.sleep(poll_interval)
            continue
            
        try:
            with open(METRICS_FILE, "r") as f:
                metrics = json.load(f)
        except Exception:
            time.sleep(poll_interval)
            continue
            
        rtt_list = metrics.get("urllc_rtt_ms", [])
        
        # Calculate rolling average of the last 5 samples
        last_samples = [s["v"] for s in rtt_list[-5:]]
        
        if last_samples:
            avg_rtt = sum(last_samples) / len(last_samples)
        else:
            avg_rtt = 0.0
            
        alert_state = load_alert_state()
        violation_detected = (avg_rtt > SLA_RTT_THRESHOLD)
        
        current_time = time.time()
        
        if violation_detected:
            # We have a violation!
            if not alert_state.get("violation_active", False):
                # New violation event
                print(f"[SLA Monitor] ALERT! SLA Violation detected. Avg RTT: {avg_rtt:.2f} ms")
                alert_state["violation_active"] = True
                alert_state["violation_start_time"] = current_time
                
            # Update current violations details
            alert_state["violations"] = [{
                "slice": "URLLC",
                "metric": "rtt_ms",
                "value": round(avg_rtt, 2),
                "threshold": SLA_RTT_THRESHOLD,
                "severity": "critical",
                "detected_at": datetime.utcfromtimestamp(alert_state["violation_start_time"]).isoformat() + "Z"
            }]
            alert_state["last_checked"] = datetime.utcnow().isoformat() + "Z"
            save_alert_state(alert_state)
            
        else:
            # Under threshold (SLA is healthy)
            if alert_state.get("violation_active", False):
                # Transitioning from VIOLATION -> HEALTHY (Recovery occurred!)
                start_time = alert_state.get("violation_start_time", current_time)
                mttr_sec = current_time - start_time
                print(f"[SLA Monitor] HEALED! SLA secure again. RTT: {avg_rtt:.2f} ms. MTTR: {mttr_sec:.2f} seconds.")
                
                append_to_history(start_time, current_time, mttr_sec)
                
                # Clear state
                alert_state["violation_active"] = False
                alert_state["violations"] = []
                alert_state["violation_start_time"] = 0.0
                
            alert_state["last_checked"] = datetime.utcnow().isoformat() + "Z"
            save_alert_state(alert_state)
            
        time.sleep(poll_interval)

if __name__ == "__main__":
    try:
        monitor_loop()
    except KeyboardInterrupt:
        print("\nSLA Monitor stopped.")
