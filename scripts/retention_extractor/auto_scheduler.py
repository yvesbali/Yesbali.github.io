#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_scheduler.py — Phase B du pipeline retention_extractor.

Lit les deux fichiers de planning (source de verite) et les clips produits,
puis :
  1. analyse les trous (jours sans publication) sur une fenetre glissante,
  2. propose une programmation qui fait du fan-out YouTube -> FB/IG/Pinterest,
  3. applique (sur demande) les entrees dans planning.json et planning_v8.json.

CLI :
  python auto_scheduler.py --analyze              # affiche les trous (JSON)
  python auto_scheduler.py --propose              # propose une programmation
  python auto_scheduler.py --apply                # ecrit dans les plannings
  python auto_scheduler.py --analyze --days 21    # fenetre 3 semaines

Importable :
  from auto_scheduler import analyze_gaps, list_available_clips,
                             propose_schedule, apply_schedule

Notes :
  - Pas d'appel reseau cote analyse / proposition (tout est local).
  - apply_schedule ne touche PAS la privacy YouTube : on laisse ca aux
    boutons "Publier" et a sync_playlists, qui sont deja en place.
  - Les dates sont manipulees en UTC-naive (comme le reste du repo).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REPO_ROOT, out_dir, read_json, write_json  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Constantes : chemins, plateformes, heures optimales, quotas
# ──────────────────────────────────────────────────────────────────────
PLANNING_MAIN = REPO_ROOT / "data" / "publication_center" / "planning.json"
PLANNING_V8 = REPO_ROOT / "data" / "social_recyclage" / "planning_v8.json"

# Heures optimales reprises de page_publication_center.py.
OPTIMAL_HOURS: dict[str, list[str]] = {
    "youtube":  ["10:00", "14:00", "18:00"],
    "facebook": ["08:00", "12:00", "19:00"],
    "instagram": ["08:00", "12:00", "18:00"],
    "pinterest": ["12:00", "19:00", "21:00"],
    "blogger":  ["09:00", "14:00"],
}

# Objectif par defaut (publications par SEMAINE).
DEFAULT_TARGETS: dict[str, int] = {
    "youtube":   2,
    "facebook":  3,
    "instagram": 3,
    "pinterest": 2,
    "blogger":   1,
}

# Plateformes multi-fichiers : certaines entrees vont dans planning.json
# (articles + short_souvenir), d'autres dans planning_v8.json (FB/IG recycle).
PLATFORMS = ("youtube", "facebook", "instagram", "pinterest", "blogger")

# Plateforme -> fichier cible pour un short_souvenir.
TARGET_FILE_BY_PLATFORM: dict[str, str] = {
    "youtube":   "planning.json",
    "pinterest": "planning.json",
    "blogger":   "planning.json",
    "facebook":  "planning_v8.json",
    "instagram": "planning_v8.json",
}

# Nom affiche dans planning_v8.json (capitalise).
V8_PLATFORM_NAME: dict[str, str] = {
    "facebook": "Facebook",
    "instagram": "Instagram",
}


# ──────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────
def _ensure_file(path: Path, default: Any) -> None:
    """Cree le fichier de planning si absent, avec un contenu par defaut."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, default)


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _iter_days(start: date, days: int) -> Iterable[date]:
    for i in range(days):
        yield start + timedelta(days=i)


def _slugify(text: str, length: int = 20) -> str:
    """Slug ASCII minuscule, tirets a la place des espaces/caracteres bizarres."""
    if not text:
        return "clip"
    norm = unicodedata.normalize("NFKD", text)
    norm = norm.encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    if not norm:
        norm = "clip"
    return norm[:length]


def _week_key(d: date) -> tuple[int, int]:
    """Cle semaine ISO : (annee, numero_semaine)."""
    iso = d.isocalendar()
    return (iso[0], iso[1])


def _normalize_platform(name: str) -> str:
    if not name:
        return ""
    return name.strip().lower()


def _load_planning_main() -> list[dict]:
    _ensure_file(PLANNING_MAIN, [])
    data = read_json(PLANNING_MAIN, [])
    return data if isinstance(data, list) else []


def _load_planning_v8() -> list[dict]:
    _ensure_file(PLANNING_V8, [])
    data = read_json(PLANNING_V8, [])
    return data if isinstance(data, list) else []


# ──────────────────────────────────────────────────────────────────────
# 1) analyze_gaps
# ──────────────────────────────────────────────────────────────────────
def analyze_gaps(
    start_date: date | None = None,
    days: int = 14,
    target_per_week: dict[str, int] | None = None,
) -> dict:
    """
    Compte les publications par plateforme / par jour sur la fenetre
    [start_date, start_date + days[ et renvoie les trous a combler.

    Retour :
      {
        "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 14},
        "current": {
          "facebook": [{"date": "YYYY-MM-DD", "count": N}, ...],
          ...
        },
        "targets": {"facebook": 3, ...},     # par SEMAINE
        "gaps": [
          {"date": "YYYY-MM-DD", "platform": "facebook",
           "suggested_hour": "08:00", "week": "2026-W17"},
          ...
        ]
      }
    """
    if start_date is None:
        start_date = date.today()
    targets = dict(DEFAULT_TARGETS)
    if target_per_week:
        targets.update({k.lower(): v for k, v in target_per_week.items()})

    window_days = list(_iter_days(start_date, days))
    window_end = window_days[-1] + timedelta(days=1)

    # Init : current[plateforme][date_str] = 0
    current: dict[str, dict[str, int]] = {
        p: {d.isoformat(): 0 for d in window_days} for p in PLATFORMS
    }

    # planning.json
    for entry in _load_planning_main():
        d = _parse_date(entry.get("date", ""))
        if not d or d < start_date or d >= window_end:
            continue
        plat = _normalize_platform(entry.get("plateforme", ""))
        if plat in current:
            current[plat][d.isoformat()] += 1

    # planning_v8.json (FB / IG uniquement en pratique)
    for entry in _load_planning_v8():
        d = _parse_date(entry.get("date", ""))
        if not d or d < start_date or d >= window_end:
            continue
        plat = _normalize_platform(entry.get("plateforme", ""))
        if plat in current:
            current[plat][d.isoformat()] += 1

    # Calcul des gaps : on veut que chaque semaine atteigne `target`.
    # Strategie : pour chaque plateforme, on regarde semaine par semaine
    # les dates de la fenetre. S'il manque N publications pour atteindre
    # la cible, on genere N gaps etales sur les jours les moins charges.
    gaps: list[dict] = []
    for plat in PLATFORMS:
        target = int(targets.get(plat, 0))
        if target <= 0:
            continue
        # Regroupement par semaine ISO.
        weeks: dict[tuple[int, int], list[date]] = {}
        for d in window_days:
            weeks.setdefault(_week_key(d), []).append(d)

        for wk, wk_days in weeks.items():
            # Cumul actuel sur les jours de la fenetre pour cette semaine.
            count = sum(current[plat][d.isoformat()] for d in wk_days)
            # Combien manque-t-il pour atteindre la cible ? On ne programme
            # QUE sur les jours presents dans la fenetre (pas les jours avant).
            missing = max(0, target - count)
            if missing <= 0:
                continue
            # Jours candidats : ceux qui ont le moins de publis sur la
            # plateforme, stables par date croissante.
            ranked = sorted(
                wk_days,
                key=lambda d: (current[plat][d.isoformat()], d.toordinal()),
            )
            picked = ranked[:missing]
            for d in picked:
                hour = OPTIMAL_HOURS.get(plat, ["09:00"])[0]
                gaps.append({
                    "date": d.isoformat(),
                    "platform": plat,
                    "suggested_hour": hour,
                    "week": f"{wk[0]}-W{wk[1]:02d}",
                })
                # On incremente current pour eviter de reproposer ce meme
                # jour lors du comptage suivant (plateforme identique).
                current[plat][d.isoformat()] += 1

    # Transforme current en liste pour le retour (plus parlant).
    current_out: dict[str, list[dict]] = {}
    for plat in PLATFORMS:
        current_out[plat] = [
            {"date": d.isoformat(), "count": current[plat][d.isoformat()]}
            for d in window_days
        ]

    return {
        "window": {
            "start": start_date.isoformat(),
            "end": (window_end - timedelta(days=1)).isoformat(),
            "days": days,
        },
        "current": current_out,
        "targets": {p: int(targets.get(p, 0)) for p in PLATFORMS},
        "gaps": sorted(gaps, key=lambda g: (g["date"], g["platform"])),
    }


# ──────────────────────────────────────────────────────────────────────
# 2) list_available_clips
# ──────────────────────────────────────────────────────────────────────
def list_available_clips() -> list[dict]:
    """
    Parcourt out/clips/**/*.republish.json et renvoie la liste des clips
    deja uploades (au moins une entree dans uploads[]) et dont le statut
    est None / pending_review / published. Les rejected sont exclus.
    """
    clips_root = out_dir()
    results: list[dict] = []
    if not clips_root.exists():
        return results

    for sidecar_path in sorted(clips_root.rglob("*.republish.json")):
        data = read_json(sidecar_path, default=None)
        if not isinstance(data, dict):
            continue
        uploads = data.get("uploads") or []
        if not uploads:
            # Pas encore uploade : on ne peut pas le fan-out sur FB/IG.
            continue
        last = uploads[-1]
        yt_video_id = last.get("video_id") or ""
        if not yt_video_id:
            continue

        status = data.get("status") or "pending_review"
        if status == "rejected":
            continue

        results.append({
            "sidecar_path": str(sidecar_path),
            "yt_video_id": yt_video_id,
            "yt_url": last.get("url") or f"https://www.youtube.com/watch?v={yt_video_id}",
            "source_video_id": data.get("source_video_id", ""),
            "title": data.get("suggested_title", "") or data.get("source_title", ""),
            "description": data.get("suggested_description", "") or "",
            "thumbnail": f"https://i.ytimg.com/vi/{yt_video_id}/maxresdefault.jpg",
            "duration_s": float(data.get("duration_s") or 0.0),
            "status": status,
            "priority_score": float(data.get("score") or 0.0),
        })

    # Tri : meilleur score d'abord.
    results.sort(key=lambda c: c["priority_score"], reverse=True)
    return results


# ──────────────────────────────────────────────────────────────────────
# 3) propose_schedule
# ──────────────────────────────────────────────────────────────────────
def _build_main_entry(
    *,
    titre: str,
    plateforme: str,
    date_str: str,
    heure: str,
    url: str,
    video_id: str,
    image_url: str,
    type_: str,
) -> dict:
    slug = _slugify(titre, 20)
    ymd = date_str.replace("-", "")
    return {
        "type": type_,
        "titre": titre,
        "plateforme": plateforme,
        "date": date_str,
        "heure": heure,
        "url": url,
        "image_url": image_url,
        "video_id": video_id,
        "id": f"{type_}_{slug}_{ymd}",
        "status": "programmé",
        "created_at": datetime.utcnow().isoformat(),
    }


def _build_v8_entry(
    *,
    titre: str,
    plateforme: str,
    date_str: str,
    heure: str,
    url: str,
    video_id: str,
    thumbnail: str,
    description: str,
) -> dict:
    return {
        "date": date_str,
        "heure": heure,
        "plateforme": plateforme,  # "Facebook" / "Instagram"
        "type_contenu": "souvenir",
        "video_id": video_id,
        "titre": titre,
        "thumbnail": thumbnail,
        "url": url,
        "description": description,
    }


def propose_schedule(
    gaps: list[dict],
    clips: list[dict],
    reuse_across_platforms: bool = True,
    max_fanout_per_clip: int = 4,
) -> list[dict]:
    """
    Apparie les clips aux trous. Chaque clip peut etre utilise sur plusieurs
    plateformes (fan-out) si reuse_across_platforms=True. Un meme clip ne
    sera PAS programme deux fois sur la meme plateforme dans la fenetre.

    Renvoie une liste d'items :
      {
        "target_file": "planning.json" | "planning_v8.json",
        "platform": "youtube" | "Facebook" | ...,
        "date": "YYYY-MM-DD",
        "heure": "HH:MM",
        "clip": { ... champs de list_available_clips() ... },
        "entry": { ... entree prete a ajouter dans le fichier cible ... },
        "gap_index": i,   # indice dans la liste gaps
      }
    """
    if not gaps or not clips:
        return []

    # Suivi usage par clip : {sidecar_path: {fanout_count, platforms_used}}
    usage: dict[str, dict] = {
        c["sidecar_path"]: {"count": 0, "platforms": set()}
        for c in clips
    }
    clips_by_id = {c["sidecar_path"]: c for c in clips}

    # Index "prochain clip libre" : on itere clips dans l'ordre donne
    # (deja trie par score desc) et on cherche pour chaque gap le premier
    # qui n'a pas deja ete utilise sur la plateforme demandee.
    proposals: list[dict] = []

    for gi, gap in enumerate(gaps):
        plat = gap["platform"].lower()
        gap_date = gap["date"]
        gap_hour = gap.get("suggested_hour") or OPTIMAL_HOURS.get(plat, ["09:00"])[0]

        # Choix du clip : premier clip qui (a) a encore du fan-out dispo,
        # (b) n'a pas deja ete programme sur la meme plateforme.
        chosen: dict | None = None
        for c in clips:
            u = usage[c["sidecar_path"]]
            if u["count"] >= max_fanout_per_clip:
                continue
            if plat in u["platforms"]:
                continue
            if not reuse_across_platforms and u["count"] > 0:
                continue
            chosen = c
            break

        if chosen is None:
            # Plus de clip dispo : on sort, les gaps restants ne sont pas
            # comblables cette fois-ci.
            break

        target_file = TARGET_FILE_BY_PLATFORM.get(plat, "planning.json")

        if target_file == "planning_v8.json":
            plat_display = V8_PLATFORM_NAME.get(plat, plat.capitalize())
            entry = _build_v8_entry(
                titre=chosen["title"],
                plateforme=plat_display,
                date_str=gap_date,
                heure=gap_hour,
                url=chosen["yt_url"],
                video_id=chosen["yt_video_id"],
                thumbnail=chosen["thumbnail"],
                description=chosen["description"][:4000],
            )
        else:
            # planning.json : youtube / pinterest / blogger -> short_souvenir
            plat_display = plat  # minuscule comme les autres entrees existantes
            entry = _build_main_entry(
                titre=chosen["title"],
                plateforme=plat_display,
                date_str=gap_date,
                heure=gap_hour,
                url=chosen["yt_url"],
                video_id=chosen["yt_video_id"],
                image_url=chosen["thumbnail"],
                type_="short_souvenir",
            )

        proposals.append({
            "target_file": target_file,
            "platform": plat_display,
            "platform_key": plat,
            "date": gap_date,
            "heure": gap_hour,
            "clip": {
                "sidecar_path": chosen["sidecar_path"],
                "yt_video_id": chosen["yt_video_id"],
                "yt_url": chosen["yt_url"],
                "title": chosen["title"],
                "thumbnail": chosen["thumbnail"],
                "priority_score": chosen["priority_score"],
            },
            "entry": entry,
            "gap_index": gi,
        })

        usage[chosen["sidecar_path"]]["count"] += 1
        usage[chosen["sidecar_path"]]["platforms"].add(plat)

    return proposals


# ──────────────────────────────────────────────────────────────────────
# 4) apply_schedule
# ──────────────────────────────────────────────────────────────────────
def apply_schedule(proposal: list[dict], dry_run: bool = True) -> dict:
    """
    Si dry_run : retourne un apercu sans toucher aux fichiers.
    Sinon : append les entrees dans planning.json / planning_v8.json et
    journalise dans le sidecar du clip (champ "scheduled" = [ ... ]).
    """
    summary: dict[str, Any] = {
        "added": 0,
        "files_touched": [],
        "errors": [],
        "dry_run": dry_run,
        "preview": [],
    }
    if not proposal:
        return summary

    # Groupage par fichier cible.
    add_to_main: list[dict] = []
    add_to_v8: list[dict] = []
    sidecar_updates: dict[str, list[dict]] = {}

    for item in proposal:
        tgt = item.get("target_file")
        entry = item.get("entry")
        if not entry or tgt not in ("planning.json", "planning_v8.json"):
            summary["errors"].append({
                "reason": "invalid_item",
                "item": item,
            })
            continue
        if tgt == "planning.json":
            add_to_main.append(entry)
        else:
            add_to_v8.append(entry)

        sc_path = (item.get("clip") or {}).get("sidecar_path") or ""
        if sc_path:
            sidecar_updates.setdefault(sc_path, []).append({
                "at": datetime.utcnow().isoformat(),
                "target_file": tgt,
                "platform": item.get("platform"),
                "date": item.get("date"),
                "heure": item.get("heure"),
            })

        summary["preview"].append({
            "target_file": tgt,
            "platform": item.get("platform"),
            "date": item.get("date"),
            "heure": item.get("heure"),
            "yt_video_id": (item.get("clip") or {}).get("yt_video_id"),
            "titre": entry.get("titre"),
        })

    summary["added"] = len(add_to_main) + len(add_to_v8)

    if dry_run:
        return summary

    # Ecritures reelles.
    if add_to_main:
        _ensure_file(PLANNING_MAIN, [])
        main_data = _load_planning_main()
        main_data.extend(add_to_main)
        try:
            write_json(PLANNING_MAIN, main_data)
            summary["files_touched"].append(str(PLANNING_MAIN))
        except Exception as exc:
            summary["errors"].append({
                "reason": "write_main_failed",
                "detail": str(exc),
            })

    if add_to_v8:
        _ensure_file(PLANNING_V8, [])
        v8_data = _load_planning_v8()
        v8_data.extend(add_to_v8)
        try:
            write_json(PLANNING_V8, v8_data)
            summary["files_touched"].append(str(PLANNING_V8))
        except Exception as exc:
            summary["errors"].append({
                "reason": "write_v8_failed",
                "detail": str(exc),
            })

    # Mise a jour des sidecars.
    for sc_path, logs in sidecar_updates.items():
        try:
            p = Path(sc_path)
            data = read_json(p, default=None)
            if not isinstance(data, dict):
                continue
            data.setdefault("scheduled", []).extend(logs)
            write_json(p, data)
        except Exception as exc:
            summary["errors"].append({
                "reason": "sidecar_update_failed",
                "sidecar_path": sc_path,
                "detail": str(exc),
            })

    return summary


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-scheduler : comble les trous du planning avec les clips produits."
    )
    parser.add_argument("--analyze", action="store_true",
                        help="Affiche l'analyse des trous (JSON).")
    parser.add_argument("--propose", action="store_true",
                        help="Propose une programmation (JSON), sans ecrire.")
    parser.add_argument("--apply", action="store_true",
                        help="Ecrit les entrees dans planning.json / planning_v8.json.")
    parser.add_argument("--days", type=int, default=14,
                        help="Taille de la fenetre en jours (defaut 14).")
    parser.add_argument("--start", type=str, default="",
                        help="Date de debut YYYY-MM-DD (defaut : aujourd'hui).")
    parser.add_argument("--max-fanout", type=int, default=4,
                        help="Nb max de plateformes par clip (defaut 4).")
    args = parser.parse_args()

    if not (args.analyze or args.propose or args.apply):
        parser.print_help()
        return 1

    start = _parse_date(args.start) if args.start else date.today()
    if start is None:
        print(f"Date de debut invalide : {args.start}", file=sys.stderr)
        return 2

    gaps_report = analyze_gaps(start_date=start, days=args.days)

    if args.analyze and not (args.propose or args.apply):
        print(json.dumps(gaps_report, ensure_ascii=False, indent=2))
        return 0

    clips = list_available_clips()
    proposals = propose_schedule(
        gaps_report["gaps"], clips, max_fanout_per_clip=args.max_fanout
    )

    if args.propose and not args.apply:
        print(json.dumps({
            "window": gaps_report["window"],
            "gaps_total": len(gaps_report["gaps"]),
            "clips_available": len(clips),
            "proposals": proposals,
        }, ensure_ascii=False, indent=2))
        return 0

    if args.apply:
        result = apply_schedule(proposals, dry_run=False)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result.get("errors") else 3

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
