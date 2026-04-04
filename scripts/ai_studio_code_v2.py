# -*- coding: utf-8 -*-
"""Template maître LCDMH pour :
- le HTML imprimable du roadbook prévisionnel ;
- la page publique du road trip ;
- la sous-page "Journal de bord du voyageur".

Le style est volontairement figé ; seules les données injectées varient.
"""
from __future__ import annotations

import base64
import html
import mimetypes
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PRIMARY = "#1a2b56"
ACCENT = "#f97316"
BG_LIGHT = "#f8fafc"
TEXT = "#334155"
BORDER = "#e2e8f0"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def slugify(text: str) -> str:
    import re
    text = (text or "").strip().lower()
    text = text.replace("&", " et ")
    accents = {
        "à": "a", "â": "a", "ä": "a", "á": "a",
        "ç": "c",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "î": "i", "ï": "i", "ì": "i", "í": "i",
        "ô": "o", "ö": "o", "ò": "o", "ó": "o",
        "ù": "u", "û": "u", "ü": "u", "ú": "u",
        "œ": "oe",
    }
    for src, dst in accents.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "roadtrip"


def file_to_data_uri(path: Optional[str | Path]) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _infer_stay_counts(days_data: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"camping": 0, "bivouac": 0, "hotel": 0, "bnb": 0, "autre": 0}
    for day in days_data:
        end_stage = day.get("end_stage")
        desc = getattr(end_stage, "description", "") if end_stage else ""
        lower = str(desc or "").lower()
        if any(k in lower for k in ["camping", "campsite", "wigwam", "kamp", "campeggio", "campieren", "bergcamp", "camp ", "camp-", "eco river camp", "caravan"]):
            counts["camping"] += 1
        elif "bivouac" in lower:
            counts["bivouac"] += 1
        elif any(k in lower for k in ["b&b", "bed and breakfast", "room and breakfast", "breakfast", "chambre d'hote", "chambre d hote", "gite"]):
            counts["bnb"] += 1
        elif any(k in lower for k in ["hotel", "hôtel", "guest house", "guesthouse", "gasthof", "ibis", "pension", "auberge"]):
            counts["hotel"] += 1
        else:
            counts["autre"] += 1
    return counts


def _estimate_budget(days_data: List[Dict[str, Any]], stays: Dict[str, int], total_fuel: float) -> Dict[str, Any]:
    """Estime le budget previsionnel complet du road trip.
    
    Prix moyens par nuit :
    - Camping : 15 EUR
    - Bivouac : 0 EUR (gratuit)
    - Hotel : 70 EUR
    - B&B : 55 EUR
    - Autre/non precise : 30 EUR (moyenne prudente)
    
    Alimentation : 50 EUR/jour
    """
    total_days = len(days_data)
    
    # Hebergements
    price_camping = 15
    price_bivouac = 0
    price_hotel = 70
    price_bnb = 55
    price_autre = 30
    
    cost_camping = stays.get("camping", 0) * price_camping
    cost_bivouac = stays.get("bivouac", 0) * price_bivouac
    cost_hotel = stays.get("hotel", 0) * price_hotel
    cost_bnb = stays.get("bnb", 0) * price_bnb
    cost_autre = stays.get("autre", 0) * price_autre
    total_hebergement = cost_camping + cost_bivouac + cost_hotel + cost_bnb + cost_autre
    
    # Alimentation
    daily_food = 50
    total_food = total_days * daily_food
    
    # Total
    total_budget = int(round(total_fuel)) + total_hebergement + total_food
    
    return {
        "fuel": int(round(total_fuel)),
        "hebergement": total_hebergement,
        "food": total_food,
        "daily_food": daily_food,
        "total": total_budget,
        "detail_camping": f"{stays.get('camping', 0)} nuits x {price_camping} EUR = {cost_camping} EUR",
        "detail_hotel": f"{stays.get('hotel', 0)} nuits x {price_hotel} EUR = {cost_hotel} EUR",
        "detail_bnb": f"{stays.get('bnb', 0)} nuits x {price_bnb} EUR = {cost_bnb} EUR",
        "detail_bivouac": f"{stays.get('bivouac', 0)} nuits x {price_bivouac} EUR = {cost_bivouac} EUR",
        "detail_autre": f"{stays.get('autre', 0)} nuits x {price_autre} EUR = {cost_autre} EUR",
    }


def _build_route_rows(days_data: List[Dict[str, Any]]) -> str:
    rows =[]
    for d in days_data:
        start = getattr(d.get("start_stage"), "description", "") or "Départ"
        end = getattr(d.get("end_stage"), "description", "") or "Arrivée"
        if d.get("end_symbol") == "⚑":
            night = "Fin"
        else:
            lower = end.lower()
            if any(k in lower for k in ["camping", "campsite", "wigwam"]):
                night = "Camping"
            elif "bivouac" in lower:
                night = "Bivouac"
            elif "b&b" in lower:
                night = "B&B"
            elif any(k in lower for k in ["hotel", "hôtel", "guest house"]):
                night = "Hôtel"
            else:
                night = "À préciser"
        rows.append(
            f"<tr>"
            f"<td class='day-num'>J{int(d.get('day_num', 0)):02d}</td>"
            f"<td>{esc(d.get('day_date') or '')}</td>"
            f"<td>{esc(start)}</td>"
            f"<td>{esc(end)}</td>"
            f"<td>{esc(d.get('km_total', 0))} km</td>"
            f"<td>{esc(d.get('route_time', ''))}</td>"
            f"<td>{esc(night)}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def render_pdf_html(trip_meta: Dict[str, Any], days_data: List[Dict[str, Any]], qr_path: Optional[str | Path] = None) -> str:
    title = trip_meta.get("trip_title") or "Roadbook"
    zone = trip_meta.get("roadbook_zone") or title
    subtitle = trip_meta.get("subtitle") or "Roadbook prévisionnel"
    traveler = trip_meta.get("traveler_name") or "Yves Vella"
    vehicle = trip_meta.get("vehicle_label") or "Honda NT1100"
    intro = trip_meta.get("journey_text") or ""
    total_km = sum(int(d.get("km_total", 0) or 0) for d in days_data)
    total_fuel = round(sum(float(d.get("fuel_cost_eur", 0) or 0.0) for d in days_data), 2)
    total_days = len(days_data)
    first_date = days_data[0].get("day_date") if days_data else ""
    last_date = days_data[-1].get("day_date") if days_data else ""
    stays = _infer_stay_counts(days_data)
    budget = _estimate_budget(days_data, stays, total_fuel)
    qr_src = file_to_data_uri(qr_path)

    # ═══ DÉTECTION AUTOMATIQUE DU PAYS PRINCIPAL ═══
    _countries_found = {}
    for d in days_data:
        for item in d.get("timeline", []):
            c = item.get("country", "")
            if c:
                _countries_found[c] = _countries_found.get(c, 0) + 1
    # Fallback : chercher dans le titre du roadtrip
    _zone = (trip_meta.get("roadbook_zone", "") or trip_meta.get("trip_title", "")).lower()
    # Normaliser les accents pour la recherche
    import unicodedata as _ud_ai
    _zone_noaccent = _ud_ai.normalize("NFKD", _zone).encode("ascii", "ignore").decode("ascii")
    if not _countries_found:
        _kw_map = {
            "Slovénie": ["sloveni", "bled", "ljubljana", "piran", "triglav"],
            "Italie": ["itali", "dolomi", "toscane", "stelvio", "sardai"],
            "Autriche": ["autrich", "austria", "tyrol", "grossglockner", "salzbourg"],
            "Norvège": ["norveg", "norway", "lofoten", "nordkapp"],
            "Croatie": ["croati", "dubrovnik", "split", "plitvice"],
            "Royaume-Uni": ["ecosse", "scotland", "angleterre", "england", "wales", "uk"],
            "Irlande": ["irlande", "ireland"],
            "France": ["france", "alpes", "bretagne", "corse", "provence"],
            "Suisse": ["suisse", "switzerland", "schweiz"],
            "Allemagne": ["allemagne", "germany", "schwarzwald", "bayern"],
            "Espagne": ["espagne", "spain", "andalou"],
            "Portugal": ["portugal", "algarve"],
            "Grèce": ["grece", "greece", "crete"],
            "Roumanie": ["roumanie", "romania", "transfagar"],
        }
        for country, kws in _kw_map.items():
            if any(k in _zone for k in kws) or any(k in _zone_noaccent for k in kws):
                _countries_found[country] = 1
                break

    _main_country = max(_countries_found, key=_countries_found.get) if _countries_found else "Europe"

    # ═══ INFOS PAR PAYS ═══
    _COUNTRY_INFO = {
        "Royaume-Uni": {
            "docs": ["Passeport ou CNI valide (post-Brexit).", "Carte grise, permis, assurance et assistance.", "Copies numériques des papiers conseillées.", "CEAM recommandée.", "Assurance voyage conseillée pour le UK."],
            "money": ["Royaume-Uni : Livre Sterling (£) — £1 ≈ €1.17", "Règle simple : prix en £ + 20% = prix en €", "Irlande : Euro (€).", "Carte bancaire acceptée partout."],
            "route": ["Conduite à gauche au Royaume-Uni et Irlande.", "Vitesses UK : 30 mph ville, 60 mph route, 70 mph autoroute.", "Ronds-points : sens horaire.", "Surveiller météo, vent et ferries.", "Cartes hors-ligne conseillées."],
            "phone": ["Indicatif UK : +44 | Irlande : +353 | France : +33", "Urgences UK : 999", "Urgences Irlande : 112 ou 999", "Ambassade FR Londres : +44 20 7073 1000", "Ambassade FR Dublin : +353 1 277 5000"],
        },
        "Slovénie": {
            "docs": ["Carte d'identité ou passeport valide (UE/Schengen).", "Carte grise, permis, assurance.", "Copies numériques conseillées.", "CEAM recommandée.", "Vignette autoroutière e-vignette obligatoire."],
            "money": ["Monnaie : Euro (€).", "Carburant : ~1.50-1.70 €/L.", "Repas restaurant : 10-20 €.", "Carte bancaire acceptée presque partout."],
            "route": ["Conduite à droite.", "Vitesses : 50 km/h ville, 90 km/h route, 130 km/h autoroute.", "E-vignette obligatoire (moto : ~15€/semaine).", "Feux de croisement 24h/24 obligatoires.", "Taux alcool max : 0.5 g/L."],
            "phone": ["Indicatif : +386 | France : +33", "Urgences : 112", "Ambassade FR Ljubljana : +386 1 479 04 00"],
        },
        "Italie": {
            "docs": ["Carte d'identité ou passeport valide (UE/Schengen).", "Carte grise, permis, assurance.", "Gilet jaune obligatoire à bord.", "CEAM recommandée."],
            "money": ["Monnaie : Euro (€).", "Carburant : ~1.70-1.90 €/L.", "Repas trattoria : 12-25 €.", "Carte bancaire largement acceptée."],
            "route": ["Conduite à droite.", "Vitesses : 50 km/h ville, 90 km/h route, 130 km/h autoroute.", "Péages autoroute (Telepass ou tickets).", "ZTL dans les centres-villes — attention aux amendes.", "Taux alcool max : 0.5 g/L."],
            "phone": ["Indicatif : +39 | France : +33", "Urgences : 112", "Ambassade FR Rome : +39 06 686 011"],
        },
        "Autriche": {
            "docs": ["Carte d'identité ou passeport valide (UE/Schengen).", "Carte grise, permis, assurance.", "Gilet jaune obligatoire.", "CEAM recommandée."],
            "money": ["Monnaie : Euro (€).", "Carburant : ~1.50-1.70 €/L.", "Repas Gasthaus : 12-20 €.", "Carte bancaire acceptée partout."],
            "route": ["Conduite à droite.", "Vitesses : 50 km/h ville, 100 km/h route, 130 km/h autoroute.", "Vignette autoroute obligatoire (moto ~10€/10 jours).", "Cols alpins — certains payants (Grossglockner ~28€ moto).", "Taux alcool max : 0.5 g/L."],
            "phone": ["Indicatif : +43 | France : +33", "Urgences : 112", "Ambassade FR Vienne : +43 1 502 750"],
        },
        "Norvège": {
            "docs": ["Carte d'identité ou passeport valide (EEE/Schengen).", "Carte grise, permis, assurance.", "Hors UE mais espace Schengen.", "CEAM recommandée."],
            "money": ["Monnaie : Couronne (NOK) — 1€ ≈ 11 NOK.", "Carburant : ~18-20 NOK/L (~1.70€).", "Repas : 150-300 NOK (15-30€). Pays cher.", "Carte bancaire indispensable."],
            "route": ["Conduite à droite.", "Vitesses : 50 km/h ville, 80 km/h route, 100-110 km/h autoroute.", "Ferries fréquents — réserver en été.", "Péages automatiques AutoPASS.", "Routes étroites en montagne."],
            "phone": ["Indicatif : +47 | France : +33", "Urgences : 112 ou 113 (ambulance)", "Ambassade FR Oslo : +47 23 28 46 00"],
        },
        "Croatie": {
            "docs": ["Carte d'identité ou passeport valide (UE/Schengen 2023).", "Carte grise, permis, assurance.", "CEAM recommandée."],
            "money": ["Monnaie : Euro (€) depuis 2023.", "Carburant : ~1.45-1.60 €/L.", "Repas konoba : 10-20 €.", "Carte bancaire largement acceptée."],
            "route": ["Conduite à droite.", "Vitesses : 50 km/h ville, 90 km/h route, 130 km/h autoroute.", "Péages autoroute.", "Feux de croisement obligatoires oct-mars.", "Taux alcool max : 0.5 g/L."],
            "phone": ["Indicatif : +385 | France : +33", "Urgences : 112", "Ambassade FR Zagreb : +385 1 489 36 00"],
        },
        "France": {
            "docs": ["Carte d'identité valide.", "Carte grise, permis, assurance.", "Gilet jaune obligatoire.", "Éthylotest conseillé."],
            "money": ["Monnaie : Euro (€).", "Carburant : ~1.70-1.90 €/L.", "Repas : 12-25 €.", "Carte bancaire partout."],
            "route": ["Conduite à droite.", "Vitesses : 50 km/h ville, 80 km/h route, 130 km/h autoroute.", "Péages autoroute.", "Radars fixes fréquents.", "Taux alcool max : 0.5 g/L."],
            "phone": ["Urgences : 112 ou 15 (SAMU) / 17 (Police) / 18 (Pompiers)"],
        },
        "Suisse": {
            "docs": ["Carte d'identité ou passeport valide.", "Carte grise, permis, assurance.", "CEAM recommandée.", "Vignette autoroute obligatoire (40 CHF/an)."],
            "money": ["Monnaie : Franc suisse (CHF) — 1€ ≈ 0.95 CHF.", "Carburant : ~1.80-2.00 CHF/L.", "Repas : 20-40 CHF. Pays cher.", "Carte bancaire acceptée partout."],
            "route": ["Conduite à droite.", "Vitesses : 50 km/h ville, 80 km/h route, 120 km/h autoroute.", "Vignette 40 CHF/an obligatoire.", "Cols alpins — certains fermés en hiver.", "Taux alcool max : 0.5 g/L."],
            "phone": ["Indicatif : +41 | France : +33", "Urgences : 112 ou 117 (police) / 144 (ambulance)", "Ambassade FR Berne : +41 31 359 21 11"],
        },
    }

    _info = _COUNTRY_INFO.get(_main_country, {
        "docs": ["Carte d'identité ou passeport valide.", "Carte grise, permis, assurance.", "Copies numériques conseillées.", "CEAM recommandée."],
        "money": ["Vérifier la monnaie locale.", "Carte bancaire conseillée.", f"Pays : {_main_country}."],
        "route": ["Conduite à droite (vérifier selon le pays).", "Respecter les limitations de vitesse locales.", "Cartes hors-ligne conseillées."],
        "phone": ["Urgences Europe : 112", "Indicatif France : +33"],
    })

    docs = trip_meta.get("docs_list") or _info["docs"]
    money = trip_meta.get("money_list") or _info["money"]
    route = trip_meta.get("route_list") or _info["route"]
    gear = trip_meta.get("gear_list") or[
        "Combinaison pluie complète.",
        "Batteries caméra / drone chargées.",
        "Petite marge carburant et imprévus.",
    ]
    phone = trip_meta.get("phone_list") or _info["phone"]

    def lis(items: Iterable[str]) -> str:
        return "".join(f"<li>{esc(x)}</li>" for x in items)

    return f"""<!DOCTYPE html>
<html lang='fr'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>{esc(title)} - PDF</title>
<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'>
<style>
:root {{ --primary:{PRIMARY}; --accent:{ACCENT}; --bg-light:{BG_LIGHT}; --white:#fff; --text:{TEXT}; --border:{BORDER}; }}
body {{ font-family:'Segoe UI',system-ui,sans-serif; margin:0; padding:0; background:#64748b; color:var(--text); line-height:1.4; }}
.page {{ width:210mm; min-height:297mm; margin:20px auto; background:#fff; padding:20mm; box-shadow:0 15px 35px rgba(0,0,0,.35); box-sizing:border-box; position:relative; page-break-after:always; }}
header {{ background:var(--primary); color:white; padding:15px 25px; margin:-20mm -20mm 30px -20mm; display:flex; justify-content:space-between; align-items:center; box-shadow:0 4px 10px rgba(0,0,0,.15); }}
.hero {{ text-align:center; margin-bottom:30px; }}
.hero h1 {{ color:var(--primary); font-size:3.3rem; margin:5px 0; text-transform:uppercase; letter-spacing:3px; }}
.hero .meta {{ color:#64748b; font-size:1.1rem; font-weight:bold; }}
.stats-grid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:15px; margin-bottom:25px; }}
.tile {{ border:1px solid var(--border); border-radius:12px; padding:15px; text-align:center; background:#fdfdfd; box-shadow:0 5px 12px rgba(0,0,0,.08); }}
.tile i {{ font-size:1.8rem; color:var(--accent); margin-bottom:10px; display:block; }}
.tile-val {{ font-size:1.5rem; font-weight:bold; color:var(--primary); display:block; }}
.tile-label {{ font-size:.8rem; color:#64748b; text-transform:uppercase; font-weight:bold; }}
.stay-tile {{ border:1px solid var(--border); border-radius:12px; padding:25px; margin-bottom:30px; display:flex; justify-content:space-around; background:#fdfdfd; box-shadow:0 5px 12px rgba(0,0,0,.08); }}
.stay-item {{ text-align:center; }}
.stay-item i {{ color:var(--accent); font-size:1.5rem; display:block; margin-bottom:8px; }}
.stay-item span {{ font-weight:bold; font-size:1rem; color:var(--primary); }}
.journey-box {{ border:1px solid var(--border); background:#f8fafc; padding:25px; border-radius:15px; box-shadow:0 6px 15px rgba(0,0,0,.08); }}
.journey-text {{ font-size:1rem; color:#475569; text-align:justify; columns:2; column-gap:40px; }}
.journey-box h2 {{ color:var(--primary); margin-top:0; font-size:1.5rem; border-bottom:2px solid var(--accent); padding-bottom:10px; }}
.admin-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
.admin-card {{ border-left:5px solid var(--accent); background:#fffaf5; padding:20px; border-radius:0 12px 12px 0; box-shadow:0 5px 12px rgba(0,0,0,.08); }}
.admin-card h3 {{ margin:0 0 10px 0; font-size:1.1rem; color:var(--primary); text-transform:uppercase; }}
.admin-card ul {{ margin:0; padding-left:18px; }}
.expert-card {{ border:1px solid var(--border); padding:15px; border-radius:12px; background:#fdfdfd; box-shadow:0 5px 12px rgba(0,0,0,.08); }}
.expert-card h3 {{ margin:0 0 10px 0; color:var(--primary); font-size:1rem; border-bottom:1px solid var(--accent); padding-bottom:5px; }}
.qr-box {{ background:var(--primary); color:white; padding:20px; border-radius:15px; display:flex; align-items:center; justify-content:space-between; margin:20px 0; box-shadow:0 8px 20px rgba(0,0,0,.2); gap:20px; }}
.qr-box img {{ background:white; padding:8px; border-radius:10px; width:110px; height:110px; object-fit:contain; }}
.route-table {{ width:100%; border-collapse:collapse; font-size:.8rem; margin-top:15px; box-shadow:0 5px 15px rgba(0,0,0,.05); }}
.route-table th {{ background:var(--primary); color:white; text-align:left; padding:8px; }}
.route-table td {{ padding:8px; border-bottom:1px solid #eee; vertical-align:top; }}
.day-num {{ color:var(--accent); font-weight:bold; }}
footer {{ display:none !important; }}

/* === CORRECTIF POUR L'IMPRESSION PDF (weasyprint) === */
@page {{
    size: A4;
    margin: 15mm 15mm 25mm 15mm;
    @bottom-left {{
        content: "Roadbook Moto - LCDMH";
        font-size: 8pt;
        color: #94a3b8;
    }}
    @bottom-right {{
        content: "Page " counter(page);
        font-size: 8pt;
        color: #94a3b8;
    }}
}}

@media print {{ 
    * {{
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }}
    body {{ 
        background: #fff !important; 
        margin: 0 !important;
        padding: 0 !important;
    }} 
    .page {{ 
        margin: 0 !important; 
        min-height: auto !important;
        border: none !important; 
        page-break-after: always !important; 
        box-shadow: none !important;
        padding: 0 !important;
        width: 100% !important;
    }}
    .route-table {{ page-break-inside: auto !important; }}
    .route-table tr {{ page-break-inside: avoid !important; }}
    .expert-card {{ page-break-inside: avoid !important; }}
    .info-section {{ page-break-inside: avoid !important; }}
    .section-title {{ page-break-after: avoid !important; }}
    h2, h3 {{ page-break-after: avoid !important; }}
}}
/* ======================================= */

</style>
</head>
<body>
<div class='page'>
  <header>
    <div style='font-weight:bold;'>LCDMH - ROADBOOK MOTO {esc(trip_meta.get('trip_year') or '')}</div>
    <div style='background:var(--accent); padding:4px 12px; border-radius:4px; font-weight:bold; font-size:.8rem;'>PRÉVISIONNEL</div>
  </header>
  <div class='hero'>
    <p style='text-transform:uppercase; letter-spacing:2px; color:#64748b; font-weight:bold;'>{esc(subtitle)}</p>
    <h1>{esc(zone)}</h1>
    <p class='meta'>Du {esc(first_date)} au {esc(last_date)} • {esc(vehicle)} • Solo</p>
  </div>
  <div class='stats-grid'>
    <div class='tile'><i class='fa-solid fa-road'></i><span class='tile-val'>{total_km:,} km</span><span class='tile-label'>Distance</span></div>
    <div class='tile'><i class='fa-solid fa-wallet'></i><span class='tile-val'>~{budget["total"]} €</span><span class='tile-label'>Budget total</span></div>
    <div class='tile'><i class='fa-solid fa-file-lines'></i><span class='tile-val'>{total_days}</span><span class='tile-label'>Jours calculés</span></div>
    <div class='tile'><i class='fa-solid fa-calendar-days'></i><span class='tile-val'>{esc(first_date)} → {esc(last_date)}</span><span class='tile-label'>Période</span></div>
  </div>
  <div class='stay-tile'>
    <div class='stay-item'><i class='fa-solid fa-tents'></i><span>{stays['camping']} Campings</span></div>
    <div class='stay-item'><i class='fa-solid fa-mountain'></i><span>{stays['bivouac']} Bivouacs</span></div>
    <div class='stay-item'><i class='fa-solid fa-hotel'></i><span>{stays['hotel'] + stays['bnb']} Hôtels / B&B</span></div>
  </div>
  <div class='expert-card' style='margin-bottom:20px;'>
    <h3><i class='fa-solid fa-coins'></i> Budget Prévisionnel</h3>
    <table style='width:100%; font-size:.9rem; border-collapse:collapse; margin-top:10px;'>
      <tr style='border-bottom:1px solid #eee;'><td style='padding:6px 0;'><i class='fa-solid fa-gas-pump' style='color:var(--accent);width:20px;'></i> Carburant</td><td style='text-align:right; font-weight:bold;'>~{budget["fuel"]} €</td></tr>
      <tr style='border-bottom:1px solid #eee;'><td style='padding:6px 0;'><i class='fa-solid fa-bed' style='color:var(--accent);width:20px;'></i> Hébergements</td><td style='text-align:right; font-weight:bold;'>{budget["hebergement"]} €</td></tr>
      <tr style='font-size:.8rem; color:#666;'><td style='padding:2px 0 2px 24px;'>{budget["detail_camping"]}</td><td></td></tr>
      <tr style='font-size:.8rem; color:#666;'><td style='padding:2px 0 2px 24px;'>{budget["detail_hotel"]}</td><td></td></tr>
      <tr style='font-size:.8rem; color:#666;'><td style='padding:2px 0 2px 24px;'>{budget["detail_bnb"]}</td><td></td></tr>
      <tr style='font-size:.8rem; color:#666;'><td style='padding:2px 0 6px 24px;'>{budget["detail_bivouac"]}</td><td></td></tr>
      <tr style='border-bottom:1px solid #eee;'><td style='padding:6px 0;'><i class='fa-solid fa-utensils' style='color:var(--accent);width:20px;'></i> Alimentation ({budget["daily_food"]} €/jour x {total_days} jours)</td><td style='text-align:right; font-weight:bold;'>{budget["food"]} €</td></tr>
      <tr style='background:#f0f9ff; font-weight:bold; font-size:1.1rem;'><td style='padding:10px 0; color:var(--primary);'>TOTAL ESTIMÉ</td><td style='text-align:right; color:var(--accent); font-size:1.2rem;'>~{budget["total"]} €</td></tr>
    </table>
  </div>
  <div class='journey-box'>
    <h2><i class='fa-solid fa-map-location-dot'></i> L'Esprit du Parcours</h2>
    <div class='journey-text'>{esc(intro)}</div>
  </div>
  <footer><span>Roadbook Moto - LCDMH</span><span>Page 1</span></footer>
</div>
<div class='page'>
  <h2 style='color:var(--primary); border-bottom:3px solid var(--accent); padding-bottom:10px;'>Informations Essentielles</h2>
  <div class='admin-grid' style='margin-top:30px;'>
    <div class='admin-card'><h3>Documents</h3><ul>{lis(docs)}</ul></div>
    <div class='admin-card'><h3>Monnaies & Conversion</h3><ul>{lis(money)}</ul></div>
    <div class='admin-card'><h3>Sur la route</h3><ul>{lis(route)}</ul></div>
    <div class='admin-card'><h3>Téléphone & Urgences</h3><ul>{lis(phone)}</ul></div>
  </div>
  <div style='display:grid; grid-template-columns:1fr 1fr; gap:15px; margin-top:20px;'>
    <div class='expert-card'><h3>Résumé</h3><ul style='padding-left:15px; font-size:.85rem; margin-top:10px;'><li>Départ : {esc(first_date)}</li><li>Retour : {esc(last_date)}</li><li>Zone : {esc(zone)}</li></ul></div>
    <div class='expert-card'><h3>Équipement</h3><ul style='padding-left:15px; font-size:.85rem; margin-top:10px;'>{lis(gear)}</ul></div>
  </div>
  <div class='expert-card' style='margin-top:15px;'><h3>Rituel du matin</h3><ul style='padding-left:15px; font-size:.85rem; margin-top:10px;'><li>Pression pneus, niveau huile, météo.</li><li>Batteries caméras / drone et cartes mémoire.</li><li>Horaires ferry / shuttle revérifiés.</li></ul></div>
  <footer><span>Roadbook Moto - LCDMH</span><span>Page 2</span></footer>
</div>
<div class='page'>
  <h2 style='color:var(--primary); border-bottom:3px solid var(--accent); padding-bottom:10px;'>Le Parcours</h2>
  <div class='qr-box'>
    <div style='width:70%;'>
      <h3 style='margin:0; color:var(--accent); font-size:1.3rem;'>Trace GPS Digitale</h3>
      <p style='font-size:.9rem; margin-top:5px;'>Scanner ce code pour importer l'intégralité du parcours dans Kurviger.</p>
    </div>
    {f"<img src='{qr_src}' alt='QR Code'>" if qr_src else ""}
  </div>
  <table class='route-table'>
    <thead><tr><th>Jour</th><th>Date</th><th>Départ</th><th>Arrivée</th><th>Distance</th><th>Durée</th><th>Nuit</th></tr></thead>
    <tbody>{_build_route_rows(days_data)}</tbody>
  </table>
  <footer><span>Roadbook Moto - LCDMH</span><span>Page 3+</span></footer>
</div>
</body></html>"""


def _hero_image_style(hero_rel_or_uri: str) -> str:
    return f"background-image:url('{hero_rel_or_uri}');" if hero_rel_or_uri else "background:linear-gradient(135deg,#163251,#244b73);"


def render_roadtrip_main_page(context: Dict[str, Any]) -> str:
    title = context.get("title") or "Road trip"
    page_title = context.get("page_title") or title
    hero_rel = context.get("hero_src") or ""
    qr_rel = context.get("qr_src") or ""
    immersion_text = context.get("immersion_text") or ""
    kurviger_href = context.get("kurviger_href") or context.get("kurviger_href_local") or "#"
    pdf_href = context.get("pdf_href") or context.get("pdf_href_local") or "#"
    html_href = context.get("html_href") or context.get("html_href_local") or "#"
    journal_href = context.get("journal_href") or context.get("journal_href_local") or "#"
    home_href = context.get("home_href") or context.get("home_href_local") or "../index.html"
    roadtrips_href = context.get("roadtrips_href") or context.get("roadtrips_href_local") or "../roadtrips.html"
    subtitle = context.get("subtitle") or "Départ d’Annecy, Highlands, Île de Skye, bascule vers l’Irlande, Wild Atlantic Way, puis retour par le Pays de Galles."
    badge_secondary = context.get("badge_secondary") or "🧭 Préparation road trip"
    traveler_name = context.get("traveler_name") or "Yves – LCDMH"
    vehicle = context.get("vehicle_label") or "Honda NT1100"
    meta_place = context.get("meta_place") or "Départ Annecy"
    meta_zone = context.get("meta_zone") or title
    kpis = context.get("kpis") or[
        (str(context.get("trip_year") or "2026"), "Départ prévu"),
        (str(context.get("total_days") or "30 jours"), "Objectif voyage"),
        ("Shuttle", "Franchissement Manche"),
        ("Journal", "Suivi quotidien"),
    ]
    shorts = context.get("shorts") or[]
    if len(shorts) < 3:
        defaults =[
            {"title": "Short de présentation 1", "url": "https://www.youtube.com/watch?v=VrjDNkzVAZk", "thumb": "https://img.youtube.com/vi/VrjDNkzVAZk/hqdefault.jpg", "text": "Première vignette de présentation pour introduire le projet, l’état d’esprit du voyage et les premières grandes lignes du parcours."},
            {"title": "Short de présentation 2", "url": "https://www.youtube.com/watch?v=wSXGgTatQKw", "thumb": "https://img.youtube.com/vi/wSXGgTatQKw/hqdefault.jpg", "text": "Deuxième vignette en appui pour donner du relief au départ, à la préparation et à la promesse visuelle du road trip."},
            {"title": "Short de présentation 3", "url": "https://www.youtube.com/watch?v=xgi99z8MjAI", "thumb": "https://img.youtube.com/vi/xgi99z8MjAI/hqdefault.jpg", "text": "Troisième vignette de lancement, destinée à préparer la bascule vers le journal quotidien et les premières entrées terrain."},
        ]
        shorts = (shorts + defaults)[:3]
    short_cards =[]
    for idx, short in enumerate(shorts, 1):
        short_cards.append(
            f"<article class='journal-card'>"
            f"<img src='{esc(short.get('thumb',''))}' alt='Entrée {idx}'>"
            f"<div class='journal-body'><div class='journal-meta'>Entrée {idx}</div>"
            f"<h3>{esc(short.get('title',''))}</h3>"
            f"<p>{esc(short.get('text',''))}</p>"
            f"<div class='journal-actions'><a class='btn btn-dark' href='{esc(short.get('url','#'))}' target='_blank' rel='noopener'>Voir le short</a></div>"
            f"</div></article>"
        )
    kpi_html = "".join(f"<div class='kpi'><strong>{esc(v)}</strong><span>{esc(l)}</span></div>" for v,l in kpis)
    qr_box = (
        f"<img src='{esc(qr_rel)}' alt='QR code ressources voyage'>" if qr_rel else ""
    )

    return f"""<!DOCTYPE html>
<html lang='fr'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>{esc(page_title)} | LCDMH</title>
<meta name='description' content='{esc(page_title)} : road trip moto, ressources du voyage, shorts de présentation et accès rapide au journal quotidien.'>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}:root{{--orange:#e67e22;--orange-dark:#d35400;--vert:#2e7d32;--vert-dark:#1b5e20;--noir:#1a1a1a;--bg:#f7f7f5;--card:#fff;--border:#e5e5e5;--muted:#6f7782;--hero1:#163251;--hero2:#244b73;}}
body{{font-family:Arial,Helvetica,sans-serif;background:var(--bg);color:var(--noir);line-height:1.7}}a{{text-decoration:none;color:inherit}}img{{max-width:100%;display:block}}
.topbar{{background:var(--orange);color:#fff;text-align:center;padding:12px 16px;font-weight:700}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 24px}}
.hero{{position:relative;overflow:hidden;color:#fff;min-height:660px;background:linear-gradient(135deg,var(--hero1),var(--hero2))}}
.hero::before{{content:"";position:absolute;inset:0;opacity:.42;{_hero_image_style(hero_rel)}background-size:cover;background-position:center center;filter:saturate(1.02) contrast(1.02)}}
.hero::after{{content:"";position:absolute;inset:0;background:linear-gradient(180deg, rgba(10,27,44,.35) 0%, rgba(13,34,57,.55) 40%, rgba(16,40,66,.88) 100%)}}
.hero-inner{{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:34px 24px 72px}}
.breadcrumb{{font-size:.82rem;color:rgba(255,255,255,.82);margin-bottom:18px;display:flex;flex-wrap:wrap;gap:.45rem;align-items:center}}.breadcrumb a{{color:rgba(255,255,255,.88)}}.breadcrumb .sep{{opacity:.55}}
.hero-badges{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}}.badge{{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:10px 16px;font-size:.78rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase}}.badge.orange{{background:var(--orange);color:#fff}}.badge.green{{background:var(--vert);color:#fff}}
h1{{font-size:clamp(2.8rem,6vw,5rem);line-height:1.02;margin:0 0 14px;max-width:900px}}.hero-subtitle{{max-width:860px;font-size:clamp(1.05rem,2vw,1.42rem);color:#edf5ff;line-height:1.5}}
.hero-meta{{display:flex;gap:1rem 1.5rem;flex-wrap:wrap;margin-top:22px;color:#dce9f8;font-size:.95rem}}.hero-kpis{{display:flex;gap:1.4rem 2.2rem;flex-wrap:wrap;margin-top:30px;padding-top:22px;border-top:1px solid rgba(255,255,255,.15)}}.kpi strong{{display:block;font-size:clamp(1.6rem,3vw,2.3rem);line-height:1;color:#fff}}.kpi span{{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:rgba(255,255,255,.72)}}
.section{{padding:32px 0}}.card{{background:#fff;border:1px solid var(--border);border-radius:24px;padding:26px;box-shadow:0 10px 28px rgba(18,42,74,.05)}}.section-kicker{{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--orange);margin-bottom:10px}}.section-title{{font-size:clamp(1.6rem,3vw,2.2rem);margin-bottom:10px;color:#163251}}.section-text{{color:#425a74}}
.resources{{background:linear-gradient(180deg,#fff9f2 0%,#fff 100%);border-color:#ffd0a6;margin-top:-34px;position:relative;z-index:2}}
.resources-grid{{display:grid;grid-template-columns:1.45fr .9fr;gap:20px;align-items:stretch}}.resources-left{{display:grid;gap:20px}}.resource-panel{{background:#fff;border:1px solid #f1d4ba;border-radius:20px;padding:20px}}.resource-panel h3{{font-size:1.15rem;color:#163251;margin-bottom:8px}}.resource-panel p{{color:#425a74}}
.btn-row{{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}}.btn{{display:inline-block;padding:14px 20px;border-radius:999px;font-weight:700}}.btn-primary{{background:var(--orange);color:#fff}}.btn-dark{{background:#243c5a;color:#fff}}.btn-light{{background:#edf5ff;border:1px solid #cfe0f5;color:#163251}}
.note{{font-size:.9rem;color:#5f6d7c;margin-top:14px}}.qr-box{{display:flex;flex-direction:column;justify-content:center;text-align:center;background:#fff;border:2px dashed var(--orange);border-radius:22px;padding:20px;min-height:100%}}.qr-box img{{max-width:190px;margin:10px auto 0;border-radius:12px;background:#fff;padding:10px}}
.intro-copy p{{color:#425a74;font-size:1rem;line-height:1.8}}
.journal-preview{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.journal-card{{background:#fff;border:1px solid var(--border);border-radius:20px;overflow:hidden}}.journal-card img{{aspect-ratio:16/9;object-fit:cover;width:100%}}.journal-body{{padding:16px}}.journal-meta{{font-size:.75rem;font-weight:700;color:var(--orange);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}}.journal-body h3{{font-size:1.05rem;color:#163251;margin-bottom:6px}}.journal-body p{{font-size:.92rem;color:#536579;line-height:1.6}}.journal-actions{{margin-top:14px;display:flex;gap:10px;flex-wrap:wrap}}
.follow-box{{margin-top:26px;background:#fff8f2;border:1px solid #f1d4ba;border-radius:22px;padding:22px;display:flex;justify-content:space-between;gap:20px;align-items:center;flex-wrap:wrap}}.follow-box h3{{font-size:1.35rem;color:#163251;margin-bottom:6px}}.follow-box p{{color:#536579;max-width:740px}}
footer{{padding:26px 0 46px;color:#6b7785;font-size:.88rem}}
@media (max-width:900px){{.resources-grid,.journal-preview{{grid-template-columns:1fr}} .hero{{min-height:auto}} .hero-inner{{padding-top:28px;padding-bottom:56px}} .resources{{margin-top:20px}} }}
</style></head>
<body>
<div class='topbar'>Road trip en préparation — itinéraire prévisionnel susceptible d'évoluer</div>
<section class='hero'><div class='hero-inner'>
<nav class='breadcrumb' aria-label='Fil d\'Ariane principal'><a href='{esc(home_href)}'>Accueil</a><span class='sep'>›</span><a href='{esc(roadtrips_href)}'>Road Trips</a><span class='sep'>›</span><span>{esc(title)}</span></nav>
<div class='hero-badges'><span class='badge orange'>🏍️ Road trip moto — série / expédition</span><span class='badge green'>{esc(badge_secondary)}</span></div>
<h1>{esc(title)}</h1>
<p class='hero-subtitle'>{esc(subtitle)}</p>
<div class='hero-meta'><span>✍️ {esc(traveler_name)}</span><span>🏍️ {esc(vehicle)}</span><span>📍 {esc(meta_place)}</span><span>🗺️ {esc(meta_zone)}</span></div>
<div class='hero-kpis'>{kpi_html}</div>
</div></section>
<main class='wrap'>
<section class='section'><div class='card resources'><div class='section-kicker'>🧳 Ressources du voyage</div>
<div class='resources-grid'>
<div class='resources-left'><div class='resource-panel' style='height:100%'><h3>Préparer et télécharger</h3><p>Retrouve ici les ressources utiles du voyage : trace Kurviger, roadbook PDF, version HTML modifiable et accès rapide au journal de bord.</p>
<div class='btn-row'><a class='btn btn-primary' href='{esc(kurviger_href)}' download>Télécharger la trace Kurviger</a><a class='btn btn-dark' href='{esc(pdf_href)}' download>Roadbook PDF</a><a class='btn btn-light' href='{esc(html_href)}' target='_blank' rel='noopener'>Roadbook HTML</a></div>
<p class='note'>La trace Kurviger et le roadbook PDF correspondent à la base du road trip prévu. Selon la météo, l’état des routes, les imprévus, la fatigue ou les opportunités du terrain, l’itinéraire réel pourra évoluer.</p></div></div>
<aside class='qr-box'><div class='section-kicker' style='margin-bottom:6px'>📱 Scan rapide</div><strong style='color:#163251'>QR code ressources</strong>{qr_box}<div class='note'>Téléchargement direct depuis le téléphone</div></aside>
<div class='resource-panel' style='grid-column:1 / -1'><h3>Immersion du voyage</h3><div class='intro-copy'>{''.join(f'<p>{esc(p)}</p>' for p in[x.strip() for x in str(immersion_text).splitlines() if x.strip()])}</div></div>
</div></div></section>
<section class='section' id='journal-preview' style='padding-top:0'><div class='card'><div class='section-kicker'>Journal de bord du voyageur</div><h2 class='section-title'>Aperçu des entrées déjà présentes</h2><p class='section-text' style='margin-bottom:18px'>Trois shorts de présentation sont visibles ici comme aperçu rapide. Ils serviront à annoncer le voyage, poser l’univers et orienter vers le journal complet.</p>
<div class='journal-preview'>{''.join(short_cards)}</div>
<div class='follow-box'><div><h3>Suivre l’aventure au jour le jour</h3><p>Le journal complet regroupera les entrées quotidiennes, les étapes du terrain, les shorts remontés et les publications qui viendront enrichir la page principale au fil du voyage.</p></div><a class='btn btn-primary' href='{esc(journal_href)}'>Ouvrir le journal complet</a></div>
</div></section><footer><p>Page générée automatiquement depuis le modèle maître LCDMH.</p></footer></main></body></html>"""



def render_journal_page(context: Dict[str, Any]) -> str:
    title = context.get("title") or "Journal de bord du voyageur"
    page_title = context.get("page_title") or f"{title} - Journal"
    main_href = context.get("main_href") or context.get("main_href_local") or "#"
    intro = context.get("intro") or "Cette page accueillera les shorts et les notes du terrain au fil des publications quotidiennes."
    shorts = context.get("shorts") or []

    cards =[]
    for idx, short in enumerate(shorts, 1):
        date_label = short.get("date_label") or f"Entrée {idx}"
        cards.append(
            f"<article class='journal-row'>"
            f"<div class='journal-thumb'><img src='{esc(short.get('thumb',''))}' alt='Entrée {idx}'></div>"
            f"<div class='journal-content'>"
            f"<div class='journal-meta'>{esc(date_label)}</div>"
            f"<h3>{esc(short.get('title',''))}</h3>"
            f"<p>{esc(short.get('text',''))}</p>"
            f"<div class='journal-actions'><a class='btn btn-dark' href='{esc(short.get('url','#'))}' target='_blank' rel='noopener'>Voir la vidéo</a></div>"
            f"</div></article>"
        )

    if not cards:
        cards.append(
            "<div class='empty-state'><h3>Aucune entrée pour le moment</h3>"
            "<p>Le journal sera alimenté au fil des publications YouTube.</p></div>"
        )

    return f"""<!DOCTYPE html>
<html lang='fr'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>{esc(page_title)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,Helvetica,sans-serif;background:#f7f7f5;color:#1a1a1a;line-height:1.7}}
a{{text-decoration:none;color:inherit}} img{{max-width:100%;display:block}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 24px}}
.topbar{{background:#e67e22;color:#fff;text-align:center;padding:12px 16px;font-weight:700}}
.hero{{background:linear-gradient(135deg,#163251,#244b73);color:#fff;padding:42px 0 48px}}
.hero h1{{font-size:clamp(2.2rem,5vw,3.4rem);margin:18px 0 10px;line-height:1.1}}
.hero p{{max-width:860px;opacity:.94}}
.btn{{display:inline-block;padding:14px 20px;border-radius:999px;font-weight:700}}
.btn-primary{{background:#e67e22;color:#fff}}
.btn-dark{{background:#243c5a;color:#fff}}
.section{{padding:32px 0}}
.card{{background:#fff;border:1px solid #e5e5e5;border-radius:24px;padding:26px;box-shadow:0 10px 28px rgba(18,42,74,.05)}}
.section-kicker{{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#e67e22;margin-bottom:10px}}
.section-title{{font-size:clamp(1.7rem,3vw,2.2rem);margin-bottom:10px;color:#163251;line-height:1.2}}
.section-intro{{color:#536579;margin-bottom:18px}}
.journal-list{{display:flex;flex-direction:column;gap:18px}}
.journal-row{{display:grid;grid-template-columns:320px 1fr;gap:18px;align-items:stretch;background:#fff;border:1px solid #e5e5e5;border-radius:22px;overflow:hidden}}
.journal-thumb{{background:#dfe9f7;min-height:180px}}
.journal-thumb img{{width:100%;height:100%;object-fit:cover}}
.journal-content{{padding:18px 20px}}
.journal-meta{{font-size:.75rem;font-weight:700;color:#e67e22;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}}
.journal-content h3{{font-size:1.2rem;color:#163251;margin-bottom:8px;line-height:1.3}}
.journal-content p{{font-size:.96rem;color:#536579;line-height:1.65}}
.journal-actions{{margin-top:14px}}
.empty-state{{border:1px dashed #cbd5e1;border-radius:20px;padding:24px;color:#475569;background:#fbfdff}}
.empty-state h3{{margin-bottom:8px;color:#163251}}
@media (max-width:900px){{
  .journal-row{{grid-template-columns:1fr}}
  .hero h1{{font-size:2.1rem}}
}}
</style>
</head>
<body>
<div class='topbar'>Journal du voyageur — page de travail</div>
<section class='hero'>
  <div class='wrap'>
    <a class='btn btn-primary' href='{esc(main_href)}'>← Retour à la page principale</a>
    <h1>{esc(title)}</h1>
    <p>{esc(intro)}</p>
  </div>
</section>
<main class='wrap'>
  <section class='section'>
    <div class='card'>
      <div class='section-kicker'>Au fil des jours</div>
      <h2 class='section-title'>Entrées du journal</h2>
      <p class='section-intro'>Les shorts et vidéos du voyage s'afficheront ici les uns sous les autres, avec leur titre et leur texte d'accompagnement.</p>
      <div class='journal-list'>{''.join(cards)}</div>
    </div>
  </section>
</main>
</body>
</html>"""


def find_browser_for_pdf() -> Optional[Path]:
    candidates =[
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            return p
    return shutil.which("google-chrome") and Path(shutil.which("google-chrome")) or None


def generate_pdf_from_html(html_path: str | Path, pdf_path: str | Path) -> tuple[bool, str]:
    """Convertit le HTML imprimable en PDF via weasyprint.
    Rendu identique au HTML — pas de problème de marges ni de coupures.
    """
    html_path = Path(html_path)
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from weasyprint import HTML
        HTML(filename=str(html_path.resolve())).write_pdf(str(pdf_path))
        if not pdf_path.exists():
            return False, "weasyprint n'a pas créé le PDF."
        return True, str(pdf_path)
    except ImportError:
        # Fallback navigateur si weasyprint pas installé
        browser = find_browser_for_pdf()
        if browser is None:
            return False, "weasyprint non installé et Chrome/Edge introuvable. Installez : pip install weasyprint"
        try:
            cmd = [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                f"--print-to-pdf={pdf_path}",
                html_path.resolve().as_uri(),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Erreur navigateur")[:1000]
            if not pdf_path.exists():
                return False, "Le navigateur n'a pas créé le PDF."
            return True, str(pdf_path)
        except Exception as exc:
            return False, str(exc)
    except Exception as exc:
        return False, f"weasyprint erreur : {exc}"