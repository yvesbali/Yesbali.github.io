#!/usr/bin/env python3
"""
sync_facebook_planning.py
Synchronise les dates entre planning_v8.json et facebook_payload_test.json.
Appelé quand une carte est déplacée dans le Centre de Publication.

Usage:
    python sync_facebook_planning.py                  # sync planning → payload
    python sync_facebook_planning.py --reverse        # sync payload → planning
"""

import json
import sys
from pathlib import Path

# Chemins relatifs au repo GitHub
REPO_ROOT = Path(__file__).resolve().parent.parent
PLANNING_V8 = REPO_ROOT / "data" / "social_recyclage" / "planning_v8.json"
PAYLOAD_TEST = REPO_ROOT / "facebook" / "facebook_payload_test.json"


def sync_planning_to_payload():
    """
    Quand une carte est déplacée dans le Centre de Publication,
    met à jour les dates dans facebook_payload_test.json.
    """
    with open(PLANNING_V8, "r", encoding="utf-8") as f:
        planning = json.load(f)

    with open(PAYLOAD_TEST, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Index des posts payload par library_id
    payload_by_id = {p["id"]: p for p in payload["posts"]}

    changes = 0
    for entry in planning:
        lib_id = entry.get("library_id", "")
        if lib_id and lib_id in payload_by_id:
            post = payload_by_id[lib_id]
            new_date = entry.get("date", "")
            new_time = entry.get("heure", "")
            
            if new_date and post.get("scheduled_date") != new_date:
                old = post["scheduled_date"]
                post["scheduled_date"] = new_date
                changes += 1
                print(f"  📅 {lib_id}: {old} → {new_date}")
            
            if new_time and post.get("scheduled_time") != new_time:
                post["scheduled_time"] = new_time

    if changes > 0:
        with open(PAYLOAD_TEST, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\n✅ {changes} dates mises à jour dans facebook_payload_test.json")
    else:
        print("✅ Aucun changement de date détecté")
    
    return changes


def sync_payload_to_planning():
    """
    Sens inverse : met à jour planning_v8.json depuis facebook_payload_test.json.
    Utile après modification manuelle du payload.
    """
    with open(PLANNING_V8, "r", encoding="utf-8") as f:
        planning = json.load(f)

    with open(PAYLOAD_TEST, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Index planning entries by library_id
    planning_by_id = {}
    for entry in planning:
        lid = entry.get("library_id", "")
        if lid:
            if lid not in planning_by_id:
                planning_by_id[lid] = []
            planning_by_id[lid].append(entry)

    changes = 0
    for post in payload["posts"]:
        pid = post["id"]
        if pid in planning_by_id:
            for entry in planning_by_id[pid]:
                if entry.get("date") != post["scheduled_date"]:
                    entry["date"] = post["scheduled_date"]
                    changes += 1

    if changes > 0:
        with open(PLANNING_V8, "w", encoding="utf-8") as f:
            json.dump(planning, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"✅ {changes} dates mises à jour dans planning_v8.json")
    else:
        print("✅ Aucun changement")

    return changes


if __name__ == "__main__":
    if "--reverse" in sys.argv:
        sync_payload_to_planning()
    else:
        sync_planning_to_payload()
