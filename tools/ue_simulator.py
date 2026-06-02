#!/usr/bin/env python3
import time
import json
import random
import os
import argparse

STATE_FILE = "/home/shreyas-k/.gemini/antigravity/scratch/5g-mcp-automation/visualizations/simulation_state.json"

class UE5GSimulator:
    def __init__(self, imsi="999700000000001", key="8baf473f2f8fd09487cccbd7097c6862", opc="11111111111111111111111111111111"):
        self.imsi = imsi
        self.key = key
        self.opc = opc
        self.state = "DEREGISTERED"
        self.ue_ip = "0.0.0.0"
        self.apn = "internet"
        self.logs = []
        self.metrics = {"tx_packets": 0, "rx_packets": 0, "tx_bytes": 0, "rx_bytes": 0, "latency_ms": 0}
        self.is_running = False

    def log(self, message, source="UE", destination="gNB"):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        log_entry = {
            "timestamp": timestamp,
            "state": self.state,
            "source": source,
            "destination": destination,
            "message": message
        }
        self.logs.append(log_entry)
        print(f"[{timestamp}] {source} ➔ {destination} | {message}")
        self.save_state()

    def save_state(self):
        state_data = {
            "imsi": self.imsi,
            "state": self.state,
            "ue_ip": self.ue_ip,
            "apn": self.apn,
            "logs": self.logs[-15:],  # Keep last 15 logs
            "metrics": self.metrics,
            "timestamp": time.time()
        }
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            pass

    def run_full_registration(self):
        """Runs the entire 5G SA registration and session establishment call flow."""
        self.is_running = True
        self.logs = []
        
        # State: DEREGISTERED -> INITIATED
        self.state = "DEREGISTERED"
        self.log("UE Powered ON. Searching for 5G PLMN...")
        time.sleep(1.0)
        
        self.state = "INITIATED"
        self.log("Found 5G cell. Establishing RRC Connection...", source="UE", destination="gNB")
        time.sleep(0.8)
        self.log("RRC Connection Setup Complete. Carrier frequency 3.5GHz (n78).", source="gNB", destination="UE")
        time.sleep(0.8)
        
        # State: REGISTRATION_REQUEST
        self.state = "REGISTRATION_REQUEST"
        suci = f"suci-0-001-01-0-0-0-{self.imsi[-5:]}"
        self.log(f"Sending NAS Registration Request (SUCI: {suci}, 5G-GUTI: None)", source="UE", destination="gNB")
        time.sleep(0.8)
        self.log(f"Forwarding NGAP Initial UE Message containing NAS Registration Request", source="gNB", destination="AMF")
        time.sleep(0.8)
        
        # State: IDENTITY_VERIFY
        self.state = "IDENTITY_VERIFY"
        self.log("Sending Nausf_UEAuthentication_Authenticate Request", source="AMF", destination="AUSF")
        time.sleep(0.6)
        self.log("Retrieving authentication vector (RAND, AUTN, XRES*) from UDM", source="AUSF", destination="UDM")
        time.sleep(0.6)
        
        # State: AUTHENTICATING
        self.state = "AUTHENTICATING"
        rand = "e5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0"
        autn = "35f8d910a2158000"
        self.log(f"NAS Authentication Request (RAND: {rand[:8]}..., AUTN: {autn})", source="AMF", destination="gNB")
        time.sleep(0.6)
        self.log(f"Downlink NAS Transport (Authentication Request)", source="gNB", destination="UE")
        time.sleep(0.8)
        
        # State: AUTHENTICATED
        self.state = "AUTHENTICATED"
        self.log("Computing authentication response (RES*) from USIM Key K and OPc...", source="UE", destination="UE")
        time.sleep(1.0)
        res_star = "4f83ad7209bc1ef5a7bcdaef09"
        self.log(f"Uplink NAS Transport (Authentication Response, RES*: {res_star[:8]}...)", source="UE", destination="gNB")
        time.sleep(0.8)
        self.log("Forwarding NGAP Uplink NAS Transport (Authentication Response)", source="gNB", destination="AMF")
        time.sleep(0.6)
        self.log("Verifying RES* match. UE successfully authenticated.", source="AMF", destination="AMF")
        time.sleep(0.6)
        
        # State: SECURITY_MODE
        self.state = "SECURITY_MODE"
        self.log("NAS Security Mode Command (Cipher: 5G-EA2, Integrity: 5G-IA2)", source="AMF", destination="gNB")
        time.sleep(0.6)
        self.log("Downlink NAS Transport (Security Mode Command)", source="gNB", destination="UE")
        time.sleep(0.6)
        self.log("Securing NAS connection with cypher keys.", source="UE", destination="UE")
        time.sleep(0.8)
        self.log("NAS Security Mode Complete", source="UE", destination="gNB")
        time.sleep(0.6)
        self.log("Forwarding NGAP Uplink NAS Transport (Security Mode Complete)", source="gNB", destination="AMF")
        time.sleep(0.6)
        
        # State: REGISTERED
        self.state = "REGISTERED"
        allocated_guti = f"5G-GUTI-001-01-{random.randint(10000, 99999)}"
        self.log(f"NAS Registration Accept (Assigned GUTI: {allocated_guti})", source="AMF", destination="gNB")
        time.sleep(0.8)
        self.log("Downlink NAS Transport (Registration Accept) + RRC Reconfiguration Request", source="gNB", destination="UE")
        time.sleep(0.8)
        self.log("RRC Reconfiguration Complete", source="UE", destination="gNB")
        time.sleep(0.8)
        
        # State: PDU_SESSION_REQUEST
        self.state = "PDU_SESSION_REQUEST"
        self.log(f"Uplink NAS Transport (PDU Session Establishment Request, APN: '{self.apn}')", source="UE", destination="gNB")
        time.sleep(0.8)
        self.log("NGAP Uplink NAS Transport (Forwarding PDU Session Request)", source="gNB", destination="AMF")
        time.sleep(0.6)
        self.log("Nausf_UEContext_Creation Request", source="AMF", destination="SMF")
        time.sleep(0.6)
        self.log("Selecting User Plane Function (UPF) for default internet slice.", source="SMF", destination="SMF")
        time.sleep(0.6)
        self.log("Establishing GTP-U Tunnel (N4 Association)", source="SMF", destination="UPF")
        time.sleep(0.8)
        
        # State: PDU_SESSION_ESTABLISHED
        self.state = "PDU_SESSION_ESTABLISHED"
        self.ue_ip = f"192.168.100.{random.randint(2, 254)}"
        self.log(f"PDU Session Establishment Accept (Assigned UE IP: {self.ue_ip}, DNS: 8.8.8.8)", source="SMF", destination="AMF")
        time.sleep(0.8)
        self.log(f"NGAP PDU Session Resource Setup Request (UE IP: {self.ue_ip})", source="AMF", destination="gNB")
        time.sleep(0.8)
        self.log(f"RRC PDU Session Establishment (UE IP: {self.ue_ip})", source="gNB", destination="UE")
        time.sleep(0.8)
        self.log(f"GTP-U tunnel established between gNodeB and UPF. Interface 'uesimtun0' is UP.", source="UE", destination="UPF")
        time.sleep(1.0)
        
        # Start data transfer simulator loop
        self.run_data_loop()

    def run_data_loop(self, iterations=30):
        """Simulates ongoing user plane data transfer."""
        self.state = "DATA_TRANSFER"
        self.log(f"Data interface active. Starting standard traffic loop over GTP-U...", source="UE", destination="UPF")
        
        for i in range(iterations):
            if not self.is_running:
                break
            
            # Simulate ping / packet flow
            latency = round(random.uniform(8.5, 24.2), 2)
            dl_mbps = round(random.uniform(120.0, 480.0), 1)
            ul_mbps = round(random.uniform(30.0, 95.0), 1)
            
            tx_p = random.randint(15, 60)
            rx_p = random.randint(30, 120)
            
            self.metrics["tx_packets"] += tx_p
            self.metrics["rx_packets"] += rx_p
            self.metrics["tx_bytes"] += tx_p * random.randint(64, 1500)
            self.metrics["rx_bytes"] += rx_p * random.randint(120, 1500)
            self.metrics["latency_ms"] = latency
            self.metrics["dl_mbps"] = dl_mbps
            self.metrics["ul_mbps"] = ul_mbps
            
            self.log(f"GTP-U: PING 8.8.8.8 - time={latency}ms | DL={dl_mbps}Mbps, UL={ul_mbps}Mbps", source="UE", destination="UPF")
            time.sleep(1.5)
            
        self.state = "REGISTERED"
        self.log("Terminating traffic loop. User plane idle.")
        self.is_running = False

    def stop(self):
        self.is_running = False
        self.state = "DEREGISTERED"
        self.log("UE Powered OFF. Deregistered from Core.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="5G SA UE Call Flow & User Plane Simulator")
    parser.add_argument("--imsi", default="999700000000001", help="Subscriber IMSI")
    parser.add_argument("--key", default="8baf473f2f8fd09487cccbd7097c6862", help="Auth Key (32 hex)")
    parser.add_argument("--opc", default="11111111111111111111111111111111", help="OPc (32 hex)")
    parser.add_argument("--apn", default="internet", help="Access Point Name")
    parser.add_argument("--cycles", type=int, default=15, help="Number of traffic simulator cycles")
    
    args = parser.parse_args()
    
    sim = UE5GSimulator(args.imsi, args.key, args.opc)
    sim.apn = args.apn
    
    try:
        sim.run_full_registration()
    except KeyboardInterrupt:
        sim.stop()
        print("\nSimulation aborted by user.")
