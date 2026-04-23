# -*- coding: utf-8 -*-
"""
common.py — Helpers partages pour le pipeline retention_extractor.

Responsabilites :
  - Charger la config (config.json sinon config.example.json).
  - Resoudre les chemins du repo (racine, data/retention, out/clips).
  - Obtenir un access_token OAuth2 a partir de yt_token_analytics.json.
  - Petits utilitaires : formatage de timestamp, chargement/ecriture JSON.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

HERE = Path(__file__).resolve().parent


def _find_repo_root() -> Path:
    """
    Cherche le dossier qui contient yt_token_analytics.json. On supporte :
      - override explicite via LCDMH_REPO_ROOT
      - deploiement dans F:\\Automate_YT\\retention_extractor\\  (parent.parent)
      - deploiement dans <repo>/scripts/retention_extractor/     (parent.parent.parent)
      - fallback : parent.parent.parent
    """
    env = os.environ.get("LCDMH_REPO_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            return p

    candidates = [
        HERE.parent,          # common.py at root (rare)
        HERE.parent.parent,   # deploiement plat F:\Automate_YT\retention_extractor\common.py
        HERE.parent.parent.parent,  # repo: scripts/retention_extractor/common.py
    ]
    for p in candidates:
        if (p / "yt_token_analytics.json").exists():
            return p

    return HERE.parent.parent.parent


REPO_ROOT = _find_repo_root()
TOKEN_PATH = REPO_ROOT / "yt_token_analytics.json"
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "retention"
DEFAULT_OUT_DIR = REPO_ROOT / "out" / "clips"

CONFIG_DIR = HERE
CONFIG_PATH = CONFIG_DIR / "config.json"
CONFIG_EXAMPLE_PATH = CONFIG_DIR / "config.example.json"


def load_config() -> dict[str, Any]:
    """Retourne config.json si present, sinon config.example.json."""
    path = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE_PATH
    if not path.exists():
        print(f"[common] Aucun fichier de config trouve : {path}", file=sys.stderr)
        sys.exit(1)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.pop("_comment", None)
    cfg["_loaded_from"] = str(path)
    return cfg


def data_dir() -> Path:
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_DATA_DIR


def curves_dir() -> Path:
    p = data_dir() / "curves"
    p.mkdir(parents=True, exist_ok=True)
    return p


def peaks_dir() -> Path:
    p = data_dir() / "peaks"
    p.mkdir(parents=True, exist_ok=True)
    return p


def out_dir(cfg: dict[str, Any] | None = None) -> Path:
    if cfg and cfg.get("output_dir"):
        p = REPO_ROOT / cfg["output_dir"]
    else:
        p = DEFAULT_OUT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_access_token() -> str:
    """
    Rafraichit l'access_token OAuth2 a partir de yt_token_analytics.json
    (ou de la variable d'environnement YT_TOKEN_ANALYTICS au format JSON).
    """
    token_env = os.environ.get("YT_TOKEN_ANALYTICS", "")
    if token_env:
        try:
            creds = json.loads(token_env)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"YT_TOKEN_ANALYTICS n'est pas du JSON valide : {exc}")
    elif TOKEN_PATH.exists():
        creds = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    else:
        raise RuntimeError(
            "Aucun credential OAuth trouve. Lance scripts/generate_yt_token.py "
            f"pour creer {TOKEN_PATH}, ou expose YT_TOKEN_ANALYTICS en env."
        )

    for key in ("client_id", "client_secret", "refresh_token"):
        if not creds.get(key):
            raise RuntimeError(f"Champ manquant dans les credentials : {key}")

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Refresh token refuse ({r.status_code}) : {r.text[:300]}")
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError(f"Reponse OAuth sans access_token : {r.json()}")
    return token


def fmt_ts(seconds: float) -> str:
    """Formate en HH:MM:SS (entier). Utilise pour --download-sections et noms de fichiers."""
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_ts_filename(seconds: float) -> str:
    """Variante pour nom de fichier (sans ':')."""
    return fmt_ts(seconds).replace(":", "-")


def iso8601_duration_to_seconds(duration_str: str) -> int:
    """Convertit une duree ISO 8601 (PT1H2M33S) en secondes."""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str or "")
    if not m:
        return 0
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mn * 60 + s
