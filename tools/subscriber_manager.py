#!/usr/bin/env python3
import sys
import argparse
import json
from pymongo import MongoClient

# Default configuration matching Open5GS standards
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "open5gs"
COLLECTION_NAME = "subscribers"

def get_mongo_client(uri=None):
    """Establishes and returns a MongoClient connection."""
    target_uri = uri or DEFAULT_MONGO_URI
    return MongoClient(target_uri, serverSelectionTimeoutMS=2000)

def add_subscriber(imsi, key, opc, apn="internet", sst=1, sd="ffffff", mongo_uri=None):
    """
    Inserts a standard 5G subscriber with authentication keys, network slicing,
    and PDU session details into the Open5GS MongoDB collection.
    """
    client = get_mongo_client(mongo_uri)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # Validate inputs
    if not imsi.isdigit() or len(imsi) < 10:
        raise ValueError("IMSI must be a numeric string of at least 10 digits")
    if len(key) != 32:
        raise ValueError("Key (K) must be exactly 32 hex characters")
    if len(opc) != 32:
        raise ValueError("OPc must be exactly 32 hex characters")

    # Construct the BSON subscriber document structure matching modern Open5GS
    subscriber_doc = {
        "imsi": imsi,
        "subscribed_rau_tau_timer": 12,
        "network_access_mode": 0,
        "subscriber_status": 0,
        "access_restriction_data": 32,
        "slice": [
            {
                "sst": int(sst),
                "sd": sd.lower(),
                "default_indicator": True,
                "session": [
                    {
                        "name": apn,
                        "type": 1,  # 1 = IPv4, 2 = IPv6, 3 = IPv4v6
                        "qos": {
                            "index": 9,  # 5QI 9 (standard internet non-GBR)
                            "arp": {
                                "priority_level": 8,
                                "pre_emption_capability": 1,
                                "pre_emption_vulnerability": 1
                            }
                        },
                        "ambr": {
                            "downlink": {"value": 1, "unit": 3},  # 1 Gbps
                            "uplink": {"value": 500, "unit": 2}    # 500 Mbps
                        }
                    }
                ]
            }
        ],
        "security": {
            "k": key.lower(),
            "amf": "8000",
            "op": None,
            "opc": opc.lower(),
            "sqn": 100,
            "rand": "00000000000000000000000000000000"
        }
    }

    # Upsert: overwrite if IMSI exists, otherwise create
    result = collection.update_one(
        {"imsi": imsi},
        {"$set": subscriber_doc},
        upsert=True
    )
    
    status = "updated" if result.matched_count > 0 else "created"
    client.close()
    return {"status": "success", "imsi": imsi, "action": status}

def delete_subscriber(imsi, mongo_uri=None):
    """Removes a subscriber by IMSI."""
    client = get_mongo_client(mongo_uri)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    result = collection.delete_one({"imsi": imsi})
    client.close()

    if result.deleted_count > 0:
        return {"status": "success", "imsi": imsi, "action": "deleted"}
    else:
        return {"status": "error", "message": f"Subscriber {imsi} not found"}

def list_subscribers(mongo_uri=None):
    """Retrieves all subscribers, returning parsed summaries."""
    client = get_mongo_client(mongo_uri)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    subscribers = []
    for doc in collection.find():
        imsi = doc.get("imsi", "Unknown")
        sec = doc.get("security", {})
        slices = doc.get("slice", [])
        
        apn = "internet"
        sst = 1
        sd = "ffffff"
        if slices:
            sst = slices[0].get("sst", 1)
            sd = slices[0].get("sd", "ffffff")
            sessions = slices[0].get("session", [])
            if sessions:
                apn = sessions[0].get("name", "internet")

        subscribers.append({
            "imsi": imsi,
            "k": sec.get("k", "N/A"),
            "opc": sec.get("opc", "N/A"),
            "apn": apn,
            "sst": sst,
            "sd": sd
        })
    client.close()
    return subscribers

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Open5GS MongoDB Subscriber CLI Provisioning Utility")
    subparsers = parser.add_subparsers(dest="command")

    # Add
    parser_add = subparsers.add_parser("add", help="Add/Update a subscriber")
    parser_add.add_argument("--imsi", required=True, help="Subscriber IMSI")
    parser_add.add_argument("--key", required=True, help="Authentication Key (32 hex)")
    parser_add.add_argument("--opc", required=True, help="Operator Code OPc (32 hex)")
    parser_add.add_argument("--apn", default="internet", help="Access Point Name")
    parser_add.add_argument("--sst", type=int, default=1, help="Slice/Service Type")
    parser_add.add_argument("--sd", default="ffffff", help="Slice Differentiator (6 hex)")
    parser_add.add_argument("--uri", default=DEFAULT_MONGO_URI, help="MongoDB connection URI")

    # Delete
    parser_del = subparsers.add_parser("delete", help="Delete a subscriber")
    parser_del.add_argument("--imsi", required=True, help="Subscriber IMSI")
    parser_del.add_argument("--uri", default=DEFAULT_MONGO_URI, help="MongoDB connection URI")

    # List
    parser_list = subparsers.add_parser("list", help="List all subscribers")
    parser_list.add_argument("--uri", default=DEFAULT_MONGO_URI, help="MongoDB connection URI")

    args = parser.parse_args()

    if args.command == "add":
        try:
            res = add_subscriber(args.imsi, args.key, args.opc, args.apn, args.sst, args.sd, args.uri)
            print(json.dumps(res, indent=2))
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}), file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "delete":
        res = delete_subscriber(args.imsi, args.uri)
        print(json.dumps(res, indent=2))
        if res["status"] == "error":
            sys.exit(1)
            
    elif args.command == "list":
        subs = list_subscribers(args.uri)
        print(json.dumps(subs, indent=2))
        
    else:
        parser.print_help()
