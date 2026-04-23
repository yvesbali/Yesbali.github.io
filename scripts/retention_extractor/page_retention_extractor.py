# -*- coding: utf-8 -*-
"""
page_retention_extractor.py — page Streamlit pour le pipeline retention_extractor.

Ce fichier est a placer a cote de F:\\Automate_YT\\app.py (comme les autres
page_*.py de ton app Streamlit). Il attend de trouver :
  F:\\Automate_YT\\retention_extractor\\        (les scripts du pipeline)
  F:\\Automate_YT\\yt_token_analytics.json      (credentials OAuth)

Import dans app.py :
  from page_retention_extractor import page_retention_extractor
Routing (radio button) :
  "Retention Extractor (clips best-of)": page_retention_extractor,

Fonctionne en 2 modes :
  - "Scenario complet" (un bouton) : lance list -> fetch -> detect -> extract [-> upload].
  - "Etapes detaillees" : tu relances seulement ce qui t'interesse.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

import streamlit as st

HERE = Path(__file__).resolve().parent
# Ou sont les scripts du pipeline (structure recommandee : retention_extractor/ a cote d'app.py)
PIPELINE_DIR = HERE / "retention_extractor"
TOKEN_PATH = HERE / "yt_token_analytics.json"
DATA_DIR = HERE / "data" / "retention"
CLIPS_DIR = HERE / "out" / "clips"
CONFIG_PATH = PIPELINE_DIR / "config.json"
CONFIG_EXAMPLE = PIPELINE_DIR / "config.example.json"


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════
def _which(name: str) -> str | None:
    from shutil import which
    return which(name)


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _check_env() -> dict:
    """Retourne l'etat des pre-requis pour afficher le bandeau en haut."""
    return {
        "pipeline_dir": PIPELINE_DIR.exists(),
        "run_pipeline": (PIPELINE_DIR / "run_pipeline.py").exists(),
        "token": TOKEN_PATH.exists(),
        "config": CONFIG_PATH.exists(),
        "config_example": CONFIG_EXAMPLE.exists(),
        "ffmpeg": _which("ffmpeg") is not None,
        "yt_dlp": _which("yt-dlp") is not None or _yt_dlp_via_python(),
        "python": sys.executable,
    }


def _yt_dlp_via_python() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def _load_config() -> dict:
    cfg = _read_json(CONFIG_PATH)
    if cfg is None:
        cfg = _read_json(CONFIG_EXAMPLE, {}) or {}
    cfg.pop("_comment", None)
    return cfg


def _save_config(cfg: dict) -> None:
    _write_json(CONFIG_PATH, cfg)


def _env_for_subprocess() -> dict:
    """Env qu'on passe aux scripts du pipeline (force REPO_ROOT sur HERE)."""
    env = os.environ.copy()
    env["LCDMH_REPO_ROOT"] = str(HERE)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# ══════════════════════════════════════════════════════════════════════
# Subprocess avec logs live
# ══════════════════════════════════════════════════════════════════════
def _run_live(cmd: list[str], log_placeholder) -> int:
    """Execute cmd en streamant stdout vers log_placeholder (code block)."""
    q: Queue[str] = Queue()
    logs: list[str] = []

    def reader(stream):
        try:
            for line in iter(stream.readline, ""):
                q.put(line.rstrip("\n"))
        finally:
            q.put("__DONE__")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=_env_for_subprocess(),
        cwd=str(HERE),
    )
    t = threading.Thread(target=reader, args=(proc.stdout,), daemon=True)
    t.start()

    while True:
        try:
            line = q.get(timeout=0.2)
        except Empty:
            if proc.poll() is not None:
                # drainer puis sortir
                while not q.empty():
                    logs.append(q.get_nowait())
                break
            continue
        if line == "__DONE__":
            break
        logs.append(line)
        # rafraichit le panneau avec les 200 dernieres lignes
        log_placeholder.code("\n".join(logs[-200:]))

    proc.wait()
    log_placeholder.code("\n".join(logs[-200:]))
    return proc.returncode


def _pipeline_cmd(args: list[str]) -> list[str]:
    return [sys.executable, str(PIPELINE_DIR / "run_pipeline.py"), *args]


def _single_step_cmd(script: str, args: list[str]) -> list[str]:
    return [sys.executable, str(PIPELINE_DIR / script), *args]


# ══════════════════════════════════════════════════════════════════════
# UI sections
# ══════════════════════════════════════════════════════════════════════
def _render_status_banner(env: dict) -> None:
    cols = st.columns(6)
    checks = [
        ("Pipeline", env["pipeline_dir"] and env["run_pipeline"]),
        ("Token OAuth", env["token"]),
        ("Config", env["config"] or env["config_example"]),
        ("ffmpeg", env["ffmpeg"]),
        ("yt-dlp", env["yt_dlp"]),
        ("Python", True),
    ]
    for col, (label, ok) in zip(cols, checks):
        col.markdown(f"**{label}**  \n{'✅' if ok else '❌'}")

    missing = [l for l, ok in checks if not ok]
    if missing:
        with st.expander("⚠ Pre-requis manquants — cliquer pour details", expanded=True):
            if not env["pipeline_dir"] or not env["run_pipeline"]:
                st.error(f"Dossier pipeline introuvable : `{PIPELINE_DIR}`. "
                         "Copie le dossier `scripts/retention_extractor/` depuis le repo "
                         "vers `F:\\Automate_YT\\retention_extractor\\`.")
            if not env["token"]:
                st.error(f"Fichier OAuth manquant : `{TOKEN_PATH}`. "
                         "Lance `python scripts/generate_yt_token.py` depuis le clone Git.")
            if not env["ffmpeg"]:
                st.warning("ffmpeg absent du PATH. `winget install Gyan.FFmpeg`.")
            if not env["yt_dlp"]:
                st.warning("yt-dlp manquant. `pip install yt-dlp`.")
            if not env["config"]:
                if env["config_example"] and st.button("Creer config.json depuis config.example.json"):
                    CONFIG_PATH.write_text(CONFIG_EXAMPLE.read_text(encoding="utf-8"),
                                           encoding="utf-8")
                    st.rerun()


def _render_config_editor(cfg: dict) -> dict:
    """Sidebar : edition rapide des parametres cles."""
    st.sidebar.header("⚙ Parametres rapides")
    cfg["min_duration_s"] = st.sidebar.number_input(
        "Duree min. video source (s)", min_value=60, max_value=7200,
        value=int(cfg.get("min_duration_s", 360)), step=60,
    )
    cfg["min_views"] = st.sidebar.number_input(
        "Vues min.", min_value=0, max_value=1000000,
        value=int(cfg.get("min_views", 500)), step=100,
    )
    cfg["peak_threshold_ratio"] = st.sidebar.slider(
        "Seuil de pic (× mediane)", 1.00, 1.50,
        float(cfg.get("peak_threshold_ratio", 1.05)), 0.01,
    )
    cfg["pad_seconds_before"] = st.sidebar.slider(
        "Pad avant pic (s)", 0, 180, int(cfg.get("pad_seconds_before", 60)), 10,
    )
    cfg["pad_seconds_after"] = st.sidebar.slider(
        "Pad apres pic (s)", 0, 180, int(cfg.get("pad_seconds_after", 60)), 10,
    )
    cfg["min_clip_duration_s"] = st.sidebar.slider(
        "Duree min. clip (s)", 60, 600, int(cfg.get("min_clip_duration_s", 180)), 30,
    )
    cfg["max_clip_duration_s"] = st.sidebar.slider(
        "Duree max. clip (s)", 120, 900, int(cfg.get("max_clip_duration_s", 360)), 30,
    )
    cfg["max_clips_per_video"] = st.sidebar.slider(
        "Clips max. par video", 1, 5, int(cfg.get("max_clips_per_video", 2)),
    )
    cfg["require_4k"] = st.sidebar.checkbox(
        "Exiger 4K (2160p natif)", value=bool(cfg.get("require_4k", False)),
    )
    cfg["republish_title_template"] = st.sidebar.text_input(
        "Template titre republication",
        value=cfg.get("republish_title_template", "Souvenir : {title}"),
    )

    if st.sidebar.button("💾 Enregistrer config", use_container_width=True):
        _save_config(cfg)
        st.sidebar.success(f"Sauvegarde -> {CONFIG_PATH.name}")
    return cfg


def _render_one_click(cfg: dict) -> None:
    """Section principale : un seul bouton pour tout faire."""
    st.subheader("🎬 Scenario complet — un seul clic")

    c1, c2, c3 = st.columns([2, 2, 3])
    limit = c1.number_input("Nb max de clips a extraire", 1, 50,
                             value=int(st.session_state.get("one_click_limit", 10)))
    st.session_state["one_click_limit"] = limit

    auto_upload = c2.checkbox("Uploader automatiquement",
                              value=bool(cfg.get("auto_upload", False)))
    privacy = c3.selectbox("Privacy uploads",
                           ["unlisted", "private", "public"],
                           index=["unlisted", "private", "public"].index(
                               cfg.get("default_upload_privacy", "unlisted")),
                           disabled=not auto_upload,
                           help="Unlisted = accessible par lien, non liste publiquement. "
                                "Recommande : unlisted pour relire avant de passer en public.")

    if auto_upload and privacy == "public":
        st.warning("⚠ Tu as coche 'public'. Les clips seront visibles par tout le monde "
                   "des la fin de l'upload. Passe en 'unlisted' si tu veux relire d'abord.")

    if st.button("🚀 Lancer le scenario complet", type="primary", use_container_width=True):
        # on sauvegarde la config avant au cas ou l'user a ajuste les sliders
        cfg["auto_upload"] = auto_upload
        cfg["default_upload_privacy"] = privacy
        _save_config(cfg)

        args = ["--limit", str(limit)]
        if auto_upload:
            args += ["--upload", "--upload-privacy", privacy]
        cmd = _pipeline_cmd(args)

        with st.status("Execution du pipeline...", expanded=True) as status:
            st.code(" ".join(cmd), language="bash")
            log = st.empty()
            rc = _run_live(cmd, log)
            if rc == 0:
                status.update(label="✅ Scenario termine", state="complete")
                st.toast("Pipeline termine avec succes", icon="✅")
            else:
                status.update(label=f"❌ Echec (code {rc})", state="error")


def _render_step_tabs() -> None:
    st.subheader("🔧 Etapes detaillees")
    t1, t2, t3, t4, t5 = st.tabs([
        "1. Candidats", "2. Retention", "3. Pics", "4. Extraction", "5. Upload",
    ])

    with t1:
        st.caption("Liste les videos eligibles (moto France par defaut).")
        only = st.text_input("--only <video_id> (optionnel)", key="cand_only")
        limit = st.number_input("--limit", 0, 200, 0, key="cand_limit")
        if st.button("▶ Lister candidats", key="btn_cand"):
            args = []
            if limit > 0:
                args += ["--limit", str(limit)]
            cmd = _single_step_cmd("list_candidates.py", args)
            log = st.empty()
            _run_live(cmd, log)

        cand = _read_json(DATA_DIR / "candidates.json")
        if cand:
            st.write(f"**{cand.get('count', 0)} candidats** "
                     f"(derniere MAJ : {cand.get('updated_at','?')[:19]})")
            rows = [{"video_id": v["video_id"],
                     "vues": v["views"],
                     "duree_min": round(v["duration_s"] / 60, 1),
                     "publiee": v.get("published", ""),
                     "titre": v["title"][:70]}
                    for v in cand.get("videos", [])]
            if rows:
                st.dataframe(rows, use_container_width=True, height=400)

    with t2:
        st.caption("Recupere la courbe de retention (YouTube Analytics API).")
        only = st.text_input("--only <video_id> (optionnel)", key="fetch_only")
        force = st.checkbox("Ignorer le cache (--force)", key="fetch_force")
        if st.button("▶ Fetch retention", key="btn_fetch"):
            args = []
            if only:
                args += ["--only", only.strip()]
            if force:
                args += ["--force"]
            cmd = _single_step_cmd("fetch_retention.py", args)
            log = st.empty()
            _run_live(cmd, log)

        curves_dir = DATA_DIR / "curves"
        curves = sorted(curves_dir.glob("*.json")) if curves_dir.exists() else []
        st.write(f"**{len(curves)} courbes** en cache dans `{curves_dir}`")

    with t3:
        st.caption("Analyse les courbes et genere data/retention/plan.json.")
        debug = st.checkbox("Debug (affiche les zones)", key="peaks_debug")
        if st.button("▶ Detecter les pics", key="btn_peaks"):
            args = ["--debug"] if debug else []
            cmd = _single_step_cmd("detect_peaks.py", args)
            log = st.empty()
            _run_live(cmd, log)

        plan = _read_json(DATA_DIR / "plan.json")
        if plan:
            st.write(f"**{plan.get('clip_count', 0)} clips planifies**")
            rows = [{"video_id": c["video_id"],
                     "start": c["start_ts"], "end": c["end_ts"],
                     "duree_s": c["duration_clip_s"],
                     "score": round(c["score"], 3),
                     "methode": c["method"],
                     "titre": c["title"][:50]}
                    for c in plan.get("clips", [])]
            st.dataframe(rows, use_container_width=True, height=300)

            # Mini visualisation : courbe du premier clip
            if rows:
                first = plan["clips"][0]
                curve = _read_json(DATA_DIR / "curves" / f"{first['video_id']}.json")
                if curve and curve.get("rows"):
                    values = [r[1] for r in curve["rows"]]
                    st.line_chart(values, height=200)
                    st.caption(f"Courbe de retention pour `{first['video_id']}` — "
                               f"{first['title'][:60]}")

    with t4:
        st.caption("Telecharge en 4K les fenetres de plan.json (yt-dlp + ffmpeg).")
        limit = st.number_input("--limit", 0, 50, 0, key="extract_limit")
        dry = st.checkbox("Dry run (n'ecrit rien)", key="extract_dry")
        if st.button("▶ Extraire les clips", key="btn_extract", type="primary"):
            args = []
            if limit > 0:
                args += ["--limit", str(limit)]
            if dry:
                args += ["--dry"]
            cmd = _single_step_cmd("extract_clips.py", args)
            log = st.empty()
            _run_live(cmd, log)

    with t5:
        st.caption("Uploade les clips vers YouTube (unlisted par defaut).")
        privacy = st.selectbox("Privacy", ["unlisted", "private", "public"], key="up_privacy")
        limit = st.number_input("--limit", 0, 20, 0, key="up_limit")
        dry = st.checkbox("Dry run", key="up_dry")
        if st.button("▶ Uploader les clips pendants", key="btn_upload"):
            args = ["--all", "--privacy", privacy]
            if limit > 0:
                args += ["--limit", str(limit)]
            if dry:
                args += ["--dry"]
            cmd = _single_step_cmd("upload_clip.py", args)
            log = st.empty()
            _run_live(cmd, log)


def _render_clips_gallery() -> None:
    st.subheader("📦 Clips produits")
    if not CLIPS_DIR.exists():
        st.info(f"Aucun clip encore. Dossier : `{CLIPS_DIR}`")
        return

    sidecars = sorted(CLIPS_DIR.rglob("*.republish.json"))
    if not sidecars:
        st.info("Aucun clip produit. Lance l'extraction.")
        return

    st.write(f"**{len(sidecars)} clip(s)** dans `{CLIPS_DIR}`")
    for sc in sidecars[:20]:
        data = _read_json(sc) or {}
        mp4 = sc.with_suffix(".mp4")
        if not mp4.exists():
            continue
        with st.expander(f"🎥 {mp4.name}  —  "
                         f"{data.get('start_ts','?')} → {data.get('end_ts','?')}  "
                         f"({data.get('duration_s', 0):.0f}s)"):
            c1, c2 = st.columns([3, 2])
            with c1:
                try:
                    st.video(str(mp4))
                except Exception as exc:
                    st.warning(f"Preview indisponible : {exc}")
            with c2:
                st.markdown(f"**Source** : [{data.get('source_video_id','')}]"
                            f"({data.get('source_url','')})")
                st.markdown(f"**Score** : {data.get('score','?')}  \n"
                            f"**Methode** : `{data.get('method','?')}`")
                st.text_input("Titre suggere",
                              value=data.get("suggested_title", ""),
                              key=f"title_{sc.stem}")
                st.text_area("Description suggeree",
                             value=data.get("suggested_description", ""),
                             height=150, key=f"desc_{sc.stem}")
                uploads = data.get("uploads") or []
                if uploads:
                    last = uploads[-1]
                    st.success(f"Deja uploade : [{last.get('video_id')}]"
                               f"({last.get('url','')}) ({last.get('privacy')})")
                else:
                    c_up1, c_up2 = st.columns(2)
                    if c_up1.button("⬆ Upload unlisted", key=f"up_u_{sc.stem}"):
                        cmd = _single_step_cmd("upload_clip.py",
                                               [str(sc), "--privacy", "unlisted"])
                        log = st.empty()
                        _run_live(cmd, log)
                        st.rerun()
                    if c_up2.button("🌐 Upload public", key=f"up_p_{sc.stem}"):
                        cmd = _single_step_cmd("upload_clip.py",
                                               [str(sc), "--privacy", "public"])
                        log = st.empty()
                        _run_live(cmd, log)
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════
# Point d'entree (a importer depuis app.py)
# ══════════════════════════════════════════════════════════════════════
def page_retention_extractor() -> None:
    st.title("🎯 Retention Extractor")
    st.caption("Extrait les meilleurs passages des videos longues via YouTube Analytics, "
               "les decoupe en 4K et prepare la republication. "
               "Cas d'usage panne moto : republier sans tourner.")

    env = _check_env()
    _render_status_banner(env)

    if not (env["pipeline_dir"] and env["run_pipeline"] and env["token"]):
        st.stop()

    cfg = _load_config()
    cfg = _render_config_editor(cfg)

    st.divider()
    _render_one_click(cfg)

    st.divider()
    with st.expander("🔧 Etapes detaillees (relance granulaire)", expanded=False):
        _render_step_tabs()

    st.divider()
    _render_clips_gallery()


if __name__ == "__main__":
    # Mode standalone : streamlit run page_retention_extractor.py
    page_retention_extractor()
