"""
LCDMH – Envoi email rapport SEO
=================================
Envoie un email résumé avec lien vers le rapport publié sur lcdmh.com.
Utilisé par GitHub Actions après génération du rapport.

Variables d'environnement requises :
  GMAIL_USER         : yvesbali@gmail.com
  GMAIL_APP_PASSWORD : mot de passe d'application Gmail (16 caractères)
  REPORT_URL         : URL du rapport sur lcdmh.com
"""

import os
import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
GMAIL_USER     = os.getenv("GMAIL_USER", "yvesbali@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
REPORT_URL     = os.getenv("REPORT_URL", "https://yvesbali.github.io/seo/seo-report.html")
RECIPIENT      = "yvesbali@gmail.com"

DIR        = Path(__file__).parent
STATS_FILE = DIR / "seo_stats.json"

def load_summary() -> dict:
    """Extrait un résumé des stats depuis seo_stats.json."""
    if not STATS_FILE.exists():
        return {}

    stats  = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    total  = len(stats)
    with_2 = sum(1 for d in stats.values() if len(d.get("snapshots", [])) >= 2)

    # Compter les progressions
    up   = 0
    down = 0
    best = {"title": "—", "delta": 0, "id": ""}
    warn_list = []

    for vid_id, data in stats.items():
        snaps = data.get("snapshots", [])
        if len(snaps) < 2:
            continue
        v0 = snaps[0].get("views_30d", 0)
        v1 = snaps[-1].get("views_30d", 0)
        delta = v1 - v0
        if delta > 0:
            up += 1
            if delta > best["delta"]:
                best = {"id": vid_id, "delta": delta, "views": v1}
        elif delta < -50:
            down += 1
            warn_list.append({"id": vid_id, "delta": delta})

    return {
        "total":   total,
        "with_2":  with_2,
        "up":      up,
        "down":    down,
        "best":    best,
        "warns":   warn_list[:3],
        "date":    datetime.now().strftime("%d/%m/%Y"),
    }

def build_email(summary: dict) -> tuple:
    """Construit le sujet et le corps de l'email."""
    date  = summary.get("date", datetime.now().strftime("%d/%m/%Y"))
    total = summary.get("total", 0)
    up    = summary.get("up", 0)
    down  = summary.get("down", 0)
    best  = summary.get("best", {})
    warns = summary.get("warns", [])

    subject = f"🏍️ LCDMH – Rapport SEO mensuel {date}"

    # Corps texte
    txt = f"""
LCDMH – Rapport SEO mensuel
============================
Date : {date}

RÉSUMÉ
------
• Vidéos suivies     : {total}
• Vues en hausse ↑  : {up}
• Vues en baisse ↓  : {down}

MEILLEURE PROGRESSION
---------------------
"""
    if best.get("id"):
        txt += f"• https://youtu.be/{best['id']}\n"
        txt += f"  +{best['delta']} vues vs mois précédent\n"
    else:
        txt += "• Pas encore de données comparatives (J+30 nécessaire)\n"

    if warns:
        txt += "\nVIDÉOS À SURVEILLER\n-------------------\n"
        for w in warns:
            txt += f"• https://youtu.be/{w['id']}  ({w['delta']:+d} vues)\n"

    txt += f"""
RAPPORT COMPLET
---------------
{REPORT_URL}

---
LCDMH – La Chaîne Du Motard Heureux
lcdmh.com · @LCDMH
"""

    # Corps HTML
    warns_html = ""
    if warns:
        warns_html = "<h3 style='color:#e74c3c'>⚠️ Vidéos à surveiller</h3><ul>"
        for w in warns:
            warns_html += f"<li><a href='https://youtu.be/{w['id']}'>youtu.be/{w['id']}</a> — {w['delta']:+d} vues</li>"
        warns_html += "</ul>"

    best_html = ""
    if best.get("id"):
        best_html = f"""
        <div style='background:#d4edda;border-radius:8px;padding:15px;margin:10px 0'>
            <b>🏆 Meilleure progression</b><br>
            <a href='https://youtu.be/{best["id"]}'>youtu.be/{best["id"]}</a><br>
            <span style='color:#27ae60;font-size:18px'>+{best["delta"]} vues</span> vs mois précédent
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f4f0">

<div style="background:#1a2b4a;padding:25px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#e67e22;margin:0;font-size:24px">🏍️ LCDMH</h1>
    <p style="color:#fff;margin:5px 0 0;font-size:14px">Rapport SEO mensuel — {date}</p>
</div>

<div style="background:white;padding:25px;border-radius:0 0 12px 12px;box-shadow:0 2px 8px rgba(0,0,0,0.1)">

    <div style="display:flex;gap:15px;margin-bottom:20px">
        <div style="flex:1;background:#f8f9fa;border-radius:8px;padding:15px;text-align:center">
            <div style="font-size:28px;font-weight:bold;color:#e67e22">{total}</div>
            <div style="font-size:12px;color:#666">Vidéos suivies</div>
        </div>
        <div style="flex:1;background:#d4edda;border-radius:8px;padding:15px;text-align:center">
            <div style="font-size:28px;font-weight:bold;color:#27ae60">{up} ↑</div>
            <div style="font-size:12px;color:#666">Vues en hausse</div>
        </div>
        <div style="flex:1;background:#fdecea;border-radius:8px;padding:15px;text-align:center">
            <div style="font-size:28px;font-weight:bold;color:#e74c3c">{down} ↓</div>
            <div style="font-size:12px;color:#666">Vues en baisse</div>
        </div>
    </div>

    {best_html}
    {warns_html}

    <div style="text-align:center;margin:25px 0">
        <a href="{REPORT_URL}"
           style="background:#e67e22;color:white;padding:14px 30px;border-radius:8px;
                  text-decoration:none;font-weight:bold;font-size:16px;display:inline-block">
            📊 Voir le rapport complet
        </a>
    </div>

    <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
    <p style="font-size:12px;color:#aaa;text-align:center">
        LCDMH – La Chaîne Du Motard Heureux<br>
        <a href="https://lcdmh.com" style="color:#e67e22">lcdmh.com</a> ·
        <a href="https://youtube.com/@LCDMH" style="color:#e67e22">@LCDMH</a>
    </p>
</div>
</body>
</html>"""

    return subject, txt, html


def send_email(subject: str, txt: str, html: str):
    """Envoie l'email via Gmail SMTP."""
    if not GMAIL_PASSWORD:
        print("GMAIL_APP_PASSWORD non défini — email non envoyé")
        print("Rapport disponible sur :", REPORT_URL)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT

    msg.attach(MIMEText(txt,  "plain", "utf-8"))
    msg.attach(MIMEText(html, "html",  "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
        print(f"✓ Email envoyé → {RECIPIENT}")
        return True
    except Exception as e:
        print(f"✗ Erreur envoi email : {e}")
        return False


if __name__ == "__main__":
    print("LCDMH – Envoi rapport SEO par email")
    print(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print()

    summary = load_summary()
    subject, txt, html = build_email(summary)

    print(f"Sujet : {subject}")
    print(f"Rapport : {REPORT_URL}")
    print()

    send_email(subject, txt, html)
