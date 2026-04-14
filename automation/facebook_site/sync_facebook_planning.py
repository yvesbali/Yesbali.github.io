#!/usr/bin/env python3
"""
sync_facebook_planning.py
Synchronise les dates entre planning_v8.json et facebook_payload_test.json.
Appelé quand une carte est déplacée dans le Centre de Publication.

Usage:
    python automation/facebook_site/sync_facebook_planning.py
    python automation/facebook_site/sync_facebook_planning.py --reverse
"""

import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent

# Vraie racine du repo : .../Yesbali.github.io
REPO_ROOT = SCRIPT_DIR.parents[1]


def _first_existing(candidates):
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


PLANNING_CANDIDATES = [
    REPO_ROOT / "data" / "social_recyclage" / "planning_v8.json",
    REPO_ROOT / "automation" / "data" / "social_recyclage" / "planning_v8.json",
]

PAYLOAD_CANDIDATES = [
    REPO_ROOT / "facebook" / "facebook_payload_test.json",
    REPO_ROOT / "automation" / "facebook" / "facebook_payload_test.json",
]

PLANNING_V8 = _first_existing(PLANNING_CANDIDATES)
PAYLOAD_TEST = _first_existing(PAYLOAD_CANDIDATES)


def _load_json(path: Path, label: str, candidates):
    if not path.exists():
        tried = "\n".join(f"  - {p}" for p in candidates)
        raise FileNotFoundError(
            f"{label} introuvable.\n"
            f"Chemins testés :\n{tried}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sync_planning_to_payload():
    """
    Met à jour les dates/heures du payload Facebook à partir du planning recyclage.
    """
    planning = _load_json(PLANNING_V8, "planning_v8.json", PLANNING_CANDIDATES)
    payload = _load_json(PAYLOAD_TEST, "facebook_payload_test.json", PAYLOAD_CANDIDATES)

    posts = payload.get("posts", [])
    payload_by_id = {p.get("id", ""): p for p in posts if p.get("id")}

    changes = 0

    for entry in planning:
        lib_id = entry.get("library_id", "")
        if not lib_id:
            continue

        post = payload_by_id.get(lib_id)
        if not post:
            continue

        new_date = entry.get("date", "")
        new_time = entry.get("heure", "")

        if new_date and post.get("scheduled_date") != new_date:
            old = post.get("scheduled_date", "")
            post["scheduled_date"] = new_date
            changes += 1
            print(f"📅 {lib_id}: date {old} -> {new_date}")

        if new_time and post.get("scheduled_time") != new_time:
            old = post.get("scheduled_time", "")
            post["scheduled_time"] = new_time
            changes += 1
            print(f"🕒 {lib_id}: heure {old} -> {new_time}")

    if changes > 0:
        _save_json(PAYLOAD_TEST, payload)
        print(f"\n✅ {changes} modifications appliquées dans {PAYLOAD_TEST}")
    else:
        print("✅ Aucun changement détecté")

    return changes


def sync_payload_to_planning():
    """
    Sens inverse : met à jour planning_v8.json depuis facebook_payload_test.json.
    """
    planning = _load_json(PLANNING_V8, "planning_v8.json", PLANNING_CANDIDATES)
    payload = _load_json(PAYLOAD_TEST, "facebook_payload_test.json", PAYLOAD_CANDIDATES)

    planning_by_id = {}
    for entry in planning:
        lib_id = entry.get("library_id", "")
        if lib_id:
            planning_by_id.setdefault(lib_id, []).append(entry)

    changes = 0

    for post in payload.get("posts", []):
        pid = post.get("id", "")
        if not pid or pid not in planning_by_id:
            continue

        for entry in planning_by_id[pid]:
            new_date = post.get("scheduled_date", "")
            new_time = post.get("scheduled_time", "")

            if new_date and entry.get("date") != new_date:
                old = entry.get("date", "")
                entry["date"] = new_date
                changes += 1
                print(f"📅 {pid}: date {old} -> {new_date}")

            if new_time and entry.get("heure") != new_time:
                old = entry.get("heure", "")
                entry["heure"] = new_time
                changes += 1
                print(f"🕒 {pid}: heure {old} -> {new_time}")

    if changes > 0:
        _save_json(PLANNING_V8, planning)
        print(f"\n✅ {changes} modifications appliquées dans {PLANNING_V8}")
    else:
        print("✅ Aucun changement détecté")

    return changes


if __name__ == "__main__":
    try:
        if "--reverse" in sys.argv:
            sync_payload_to_planning()
        else:
            sync_planning_to_payload()
    except Exception as e:
        print(f"❌ Erreur : {e}")
        sys.exit(1)