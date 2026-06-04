"""
NexaCare — Aplicación de triaje médico con IA
Flujo: HOME → TRIAJE ACTIVO → RESULTADO
TFG · SMR · 2025-2026
"""
import html as _html_mod
import io
import base64
import os
import re
import uuid
import streamlit as st
import streamlit.components.v1 as components

from datetime import datetime

from logica_triaje import (
    calcular_nivel_triaje, obtener_preguntas,
    puntuacion_maxima as pts_max, SINTOMAS,
)
import plotly.graph_objects as go
from database import (
    init_db, guardar_consulta, obtener_consultas, obtener_stats,
    guardar_feedback, obtener_tendencia_sintomas, obtener_stats_feedback,
)
from ai_service import (
    generar_informe_triaje, clasificar_sintoma,
    responder_pregunta, tiene_ia, tiene_ia_real,
)
from pdf_report import generar_pdf, generar_pdf_admin
from hospital_finder import geocodificar, buscar_centros, formatear_distancia
import folium
from streamlit_folium import st_folium
try:
    from streamlit_js_eval import get_geolocation as _get_geolocation
    _GEOLOC_OK = True
except ImportError:
    _GEOLOC_OK = False
from email_service import enviar_informe

# ── Configuración ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NexaCare · Triaje Médico",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def _get_pin() -> str:
    if p := os.environ.get("NEXACARE_PIN"):
        return p
    try:
        return st.secrets.get("NEXACARE_PIN", "6825")
    except Exception:
        return "6825"

PIN_ADMIN = _get_pin()
NEXACARE_URL = os.environ.get("NEXACARE_URL", "https://nexacaretfg.streamlit.app").rstrip("/")

init_db()

LANDING_HTML_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "nexacare_landing_demo.html"
)

# ══════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=DM+Mono:wght@400;500&display=swap');

:root {
  --bg:     #071426;
  --surf:   #131f30;
  --raised: #172236;
  --hover:  #1c2a42;
  --bdr:    #1e3050;
  --bdr-s:  #162540;
  --acc:    #3d8ef8;
  --acc-g:  rgba(61,142,248,0.15);
  --acc-s:  rgba(61,142,248,0.07);
  --txt:    #e2eaf6;
  --txt2:   #7a95b8;
  --txt3:   #3d5470;
  --red:    #e84040;   --red-s:    rgba(232,64,64,0.08);
  --orange: #e87228;   --orange-s: rgba(232,114,40,0.08);
  --gold:   #d4a020;   --gold-s:   rgba(212,160,32,0.08);
  --green:  #28b86e;   --green-s:  rgba(40,184,110,0.08);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; font-family: 'DM Sans', sans-serif; }
html, body, .stApp { background: var(--bg) !important; color: var(--txt) !important; }
#MainMenu, footer, header, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"] { visibility: hidden !important; display: none !important; }
[data-testid='stSidebar'], [data-testid='stSidebarNav'],
[data-testid='collapsedControl'] { display: none !important; }

@keyframes pulse-rojo {
  0%   { box-shadow: 0 0 0 0 rgba(232,64,64,.7); }
  70%  { box-shadow: 0 0 0 22px rgba(232,64,64,0); }
  100% { box-shadow: 0 0 0 0 rgba(232,64,64,0); }
}
.nx-hero-rojo { animation: popIn .4s cubic-bezier(.22,.68,0,1.2) both, pulse-rojo 1.8s ease-out .5s infinite !important; }
.block-container { padding: 6px 32px 16px 32px !important; max-width: 1400px !important; }

/* ── Streamlit inputs ── */
div.stTextInput > div > div > input {
  background: var(--bg) !important; border: 1px solid var(--bdr) !important;
  border-radius: 8px !important; color: var(--txt) !important;
  font-family: 'DM Sans', sans-serif !important; font-size: 1rem !important;
  padding: 10px 14px !important; transition: border-color .2s, box-shadow .2s !important;
}
div.stTextInput > div > div > input:focus {
  border-color: var(--acc) !important; box-shadow: 0 0 0 3px var(--acc-g) !important;
}
/* ── Selectbox mejorado ── */
div.stSelectbox > div > div {
  background: var(--surf) !important;
  border: 1.5px solid var(--bdr) !important;
  border-radius: 12px !important;
  color: var(--txt) !important;
  padding: 2px 4px !important;
  transition: border-color .18s, box-shadow .18s !important;
  font-size: .88rem !important;
}
div.stSelectbox > div > div:hover {
  border-color: rgba(61,142,248,.45) !important;
  box-shadow: 0 0 0 3px rgba(61,142,248,.08) !important;
}
div.stSelectbox > div > div:focus-within {
  border-color: var(--acc) !important;
  box-shadow: 0 0 0 3px var(--acc-g) !important;
}
/* Flecha del select */
div.stSelectbox svg { color: var(--acc) !important; }
/* Menú desplegable */
div[data-baseweb="select"] ul {
  background: var(--raised) !important;
  border: 1px solid var(--bdr) !important;
  border-radius: 12px !important;
  overflow: hidden !important;
}
div[data-baseweb="select"] li {
  color: var(--txt2) !important;
  font-size: .86rem !important;
  border-radius: 8px !important;
  margin: 2px 4px !important;
  transition: background .12s !important;
}
div[data-baseweb="select"] li:hover,
div[data-baseweb="select"] li[aria-selected="true"] {
  background: rgba(61,142,248,.12) !important;
  color: var(--acc) !important;
}
div.stTextInput label, div.stSelectbox label {
  color: var(--txt3) !important; font-size: 0.67em !important;
  font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: 0.08em !important;
}

/* ── Botones Streamlit ── */
div.stButton > button {
  background: var(--surf) !important; color: var(--txt2) !important;
  border: 1px solid var(--bdr) !important; border-radius: 10px !important;
  font-family: 'DM Sans', sans-serif !important; font-size: 0.95em !important;
  font-weight: 600 !important; padding: 11px 16px !important; width: 100% !important;
  transition: all .18s ease !important; min-height: 44px !important;
  white-space: normal !important; line-height: 1.3 !important;
}
div.stButton > button:hover {
  background: var(--hover) !important; border-color: var(--acc) !important;
  color: var(--acc) !important; transform: translateY(-1px) !important;
  box-shadow: 0 4px 16px rgba(61,142,248,0.12) !important;
}
div.stDownloadButton > button {
  background: var(--acc) !important; color: #fff !important;
  border: none !important; border-radius: 10px !important;
  font-weight: 700 !important; font-size: 0.9em !important;
}
div.stDownloadButton > button:hover { background: #2d7be0 !important; }
div.stSpinner > div { border-top-color: var(--acc) !important; }
div.stSuccess { background: var(--green-s) !important; border-color: rgba(40,184,110,.3) !important; color: #5dd898 !important; }
div.stWarning { background: var(--gold-s) !important; border-color: rgba(212,160,32,.3) !important; }
div.stInfo    { background: var(--acc-s) !important; border-color: rgba(61,142,248,.3) !important; color: var(--acc) !important; }

/* ══ COMPONENTES NEXACARE ══ */

/* Header */
/* ══ HEADER ══ */
@keyframes hdrShimmer {
  0%   { background-position: -400% center; }
  100% { background-position:  400% center; }
}
@keyframes hdrGlow {
  0%,100% { opacity: .5; transform: translateX(-50%) scaleX(1);   }
  50%      { opacity: 1;  transform: translateX(-50%) scaleX(1.4); }
}
@keyframes crossPulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(61,142,248,0); }
  50%      { box-shadow: 0 0 0 5px rgba(61,142,248,.18); }
}
@keyframes badgePop {
  0%   { opacity:0; transform:translateY(-6px) scale(.92); }
  100% { opacity:1; transform:translateY(0)    scale(1);   }
}
@keyframes btn112Pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(232,64,64,0); }
  60%      { box-shadow: 0 0 0 6px rgba(232,64,64,.12); }
}

.nx-hdr {
  background: linear-gradient(135deg, #0e1a2e 0%, #122040 50%, #0e1a2e 100%);
  border: 1px solid rgba(61,142,248,.16);
  border-radius: 14px;
  padding: 10px 24px;
  margin-bottom: 10px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 16px;
  position: relative;
  overflow: hidden;
  animation: badgePop .4s ease both;
  box-shadow: 0 4px 32px rgba(0,0,0,.35), inset 0 1px 0 rgba(61,142,248,.08);
}
/* Línea superior animada */
.nx-hdr::before {
  content: '';
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 60%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(61,142,248,.7), rgba(40,184,110,.4), rgba(61,142,248,.7), transparent);
  background-size: 200% 100%;
  animation: hdrShimmer 4s linear infinite, hdrGlow 3s ease-in-out infinite;
}
/* Brillo sutil de fondo */
.nx-hdr::after {
  content: '';
  position: absolute; top: -60px; left: 50%; transform: translateX(-50%);
  width: 300px; height: 120px;
  background: radial-gradient(ellipse, rgba(61,142,248,.07) 0%, transparent 70%);
  pointer-events: none;
}

.nx-logo {
  font-size: 2.1em; font-weight: 800; letter-spacing: -1.2px;
  line-height: 1; white-space: nowrap;
  background: linear-gradient(135deg, #e2eaf6 30%, #7ab4f8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.nx-logo span {
  background: linear-gradient(135deg, #3d8ef8, #60aaff);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.nx-cross {
  display: inline-block; width: 22px; height: 22px;
  background: linear-gradient(135deg, #3d8ef8, #60aaff);
  border-radius: 5px; position: relative;
  margin-right: 9px; vertical-align: middle; margin-bottom: 3px;
  animation: crossPulse 3s ease-in-out infinite;
  flex-shrink: 0;
}
.nx-cross::before, .nx-cross::after {
  content: ''; position: absolute; background: #fff; border-radius: 2px;
}
.nx-cross::before { width: 12px; height: 3px; top: 9.5px; left: 5px; }
.nx-cross::after  { width: 3px; height: 12px; top: 5px; left: 9.5px; }

.nx-hdr-sub {
  font-size: 0.71em; color: var(--txt3); margin-top: 3px;
  letter-spacing: .01em;
}
.nx-hdr-center { text-align: center; }

/* Badge central animado */
.nx-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: linear-gradient(100deg, rgba(61,142,248,.1), rgba(40,184,110,.07), rgba(61,142,248,.1));
  background-size: 200% 100%;
  border: 1px solid rgba(61,142,248,.22);
  color: var(--acc); border-radius: 99px; padding: 5px 14px;
  font-size: 0.74em; font-weight: 600; white-space: nowrap;
  animation: badgePop .5s ease .1s both, hdrShimmer 5s linear 1s infinite;
}
/* Punto pulsante antes del badge */
.nx-badge::before {
  content: '';
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 0 0 rgba(40,184,110,.5);
  animation: crossPulse 2s ease-in-out infinite;
  flex-shrink: 0;
}

.nx-hdr-right { display: flex; justify-content: flex-end; }
.nx-btn-112 {
  display: inline-flex; align-items: center; gap: 8px;
  background: linear-gradient(135deg, #2a0808, #3a0e0e);
  border: 1px solid rgba(232,64,64,.35); color: #ff8080;
  border-radius: 11px; padding: 10px 20px;
  font-size: 0.82em; font-weight: 800;
  font-family: 'DM Sans', sans-serif; letter-spacing: .5px;
  text-transform: uppercase; text-decoration: none; white-space: nowrap;
  transition: all .22s ease;
  animation: badgePop .5s ease .2s both, btn112Pulse 2.5s ease-in-out 1s infinite;
  box-shadow: 0 2px 16px rgba(232,64,64,.15);
}
.nx-btn-112:hover {
  background: linear-gradient(135deg, #3a1010, #4a1515);
  border-color: rgba(232,64,64,.6);
  color: #ffaaaa;
  transform: translateY(-1px);
  box-shadow: 0 4px 20px rgba(232,64,64,.25);
}

/* Sección título con acento */
.nx-sec {
  font-size: 0.67em; font-weight: 700; color: var(--txt3);
  text-transform: uppercase; letter-spacing: .12em;
  margin: 0 0 10px; padding-bottom: 7px; border-bottom: 1px solid var(--bdr-s);
  display: flex; align-items: center; gap: 7px;
}
.nx-sec::before {
  content: ''; width: 3px; height: 11px; background: var(--acc);
  border-radius: 2px; display: inline-block; flex-shrink: 0;
}

/* Cards / panels */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 14px !important;
}
.nx-card-hdr {
  background: var(--surf);
  font-size: 0.7em; font-weight: 700; color: var(--acc);
  text-transform: uppercase; letter-spacing: .1em;
  padding: 16px 20px 13px 20px;
  margin: -1px -1px 0 -1px;
  border-bottom: 1px solid var(--bdr-s);
  border-radius: 14px 14px 0 0;
  display: flex; align-items: center; gap: 6px;
}

/* Lupa alineada con el input */
div.stButton > button[title="Analizar síntomas"] {
  height: 38px !important; min-height: 38px !important;
  background: var(--acc) !important; color: #fff !important;
  border: none !important; border-radius: 8px !important;
  font-size: 1.1em !important; padding: 0 !important;
  box-shadow: 0 2px 12px rgba(61,142,248,.3) !important;
}

/* Admin */
.nx-metric { background: var(--surf); border: 1px solid var(--bdr); border-radius: 12px; padding: 14px 16px; }
.nx-metric-l { font-size: 0.65em; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 7px; }
.nx-metric-v { font-size: 1.6em; font-weight: 700; color: var(--txt); line-height: 1; margin-bottom: 3px; }
.nx-metric-s { font-size: 0.68em; color: var(--txt3); }

.nx-nb-row { display: flex; align-items: center; gap: 10px; margin-bottom: 9px; }
.nx-nb-lbl { font-size: 0.8em; color: var(--txt2); min-width: 145px; display: flex; align-items: center; gap: 6px; }
.nx-nb-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; display: inline-block; }
.nx-nb-trk { flex: 1; background: var(--bg); border-radius: 99px; height: 4px; overflow: hidden; }
.nx-nb-f   { height: 4px; border-radius: 99px; }
.nx-nb-n   { font-size: 0.78em; font-weight: 700; color: var(--txt); min-width: 24px; text-align: right; }

.nx-th-row { display: grid; grid-template-columns: 82px 1.5fr 72px 72px 98px; gap: 8px; padding: 8px 14px; background: var(--raised); border-radius: 8px 8px 0 0; border: 1px solid var(--bdr); border-bottom: none; }
.nx-th { font-size: 0.63em; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .05em; }
.nx-tr { display: grid; grid-template-columns: 82px 1.5fr 72px 72px 98px; gap: 8px; padding: 9px 14px; align-items: center; border: 1px solid var(--bdr-s); border-top: none; transition: background .15s; }
.nx-tr:last-child { border-radius: 0 0 8px 8px; }
.nx-tr:hover { background: var(--raised); }
.nx-td { font-size: 0.81em; color: var(--txt2); }
.nx-ts { font-size: 0.71em; color: var(--txt3); font-family: 'DM Mono', monospace; }
.nx-badge { display: inline-block; padding: 3px 9px; border-radius: 99px; font-size: 0.71em; font-weight: 700; }
.bv { background: var(--green-s); color: var(--green); border: 1px solid rgba(40,184,110,.22); }
.ba { background: var(--gold-s);  color: var(--gold);  border: 1px solid rgba(212,160,32,.22); }
.bn { background: var(--orange-s);color: var(--orange);border: 1px solid rgba(232,114,40,.22); }
.br { background: var(--red-s);   color: var(--red);   border: 1px solid rgba(232,64,64,.22); }

/* Pregunta */
.nx-prog {
  background: var(--surf); border: 1px solid var(--bdr); border-radius: 11px;
  padding: 12px 18px; display: flex; align-items: center; gap: 14px; margin-bottom: 14px;
}
.nx-prog-lbl { font-size: 0.82em; color: var(--txt2); font-weight: 500; flex: 1; }
.nx-prog-pct { font-size: 0.88em; font-weight: 700; color: var(--acc); min-width: 38px; text-align: right; }
.nx-bar { flex: 1; background: var(--bg); border-radius: 99px; height: 4px; overflow: hidden; }
.nx-bar-f { height: 4px; border-radius: 99px; background: linear-gradient(90deg, #2d70e0, var(--acc)); }

.nx-q {
  background: var(--surf); border: 1px solid var(--bdr); border-top: 2px solid var(--acc);
  border-radius: 14px; padding: 22px 26px 20px; margin-bottom: 14px;
}
.nx-q-tag {
  font-size: 0.67em; font-weight: 700; color: var(--acc);
  text-transform: uppercase; letter-spacing: .12em; margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}
.nx-q-dot {
  width: 5px; height: 5px; border-radius: 50%; background: var(--acc);
  box-shadow: 0 0 7px var(--acc); display: inline-block;
}
.nx-q-txt { font-size: 1.12em; font-weight: 600; color: var(--txt); line-height: 1.45; }

.nx-risk {
  background: var(--bg); border-radius: 8px; padding: 7px 13px; margin: 14px 0 16px;
  display: flex; align-items: center; gap: 10px;
}
.nx-risk-lbl { font-size: 0.68em; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .06em; flex-shrink: 0; }
.nx-risk-bar { flex: 1; background: #0c1420; border-radius: 99px; height: 3px; overflow: hidden; }
.nx-risk-f   { height: 3px; border-radius: 99px; }
.nx-risk-pct { font-size: 0.78em; font-weight: 700; min-width: 34px; text-align: right; }

.nx-nivel {
  border-radius: 14px; padding: 20px 22px;
  display: flex; align-items: center; gap: 16px;
  border: 1px solid transparent; margin-bottom: 12px;
}
.nx-nivel-e { font-size: 2.4em; flex-shrink: 0; }
.nx-nivel-t { font-size: 1.42em; font-weight: 700; letter-spacing: -.4px; line-height: 1.1; }
.nx-nivel-s { font-size: 0.77em; margin-top: 3px; opacity: .55; }

.nx-stats3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.nx-stat { background: var(--surf); border: 1px solid var(--bdr); border-radius: 10px; padding: 11px 10px; text-align: center; }
.nx-stat-l { font-size: 0.63em; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .07em; margin-bottom: 4px; }
.nx-stat-v { font-size: 0.96em; font-weight: 700; color: var(--txt); }

.nx-gauge { background: var(--surf); border: 1px solid var(--bdr); border-radius: 11px; padding: 13px 18px; margin-bottom: 12px; }
.nx-gauge-t { font-size: 0.67em; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
.nx-gauge-bg { background: var(--bg); border-radius: 99px; height: 6px; overflow: hidden; }
.nx-gauge-f  { height: 6px; border-radius: 99px; }
.nx-gauge-lbls { display: flex; justify-content: space-between; font-size: 0.65em; color: var(--txt3); margin-top: 5px; }

.nx-ai {
  background: linear-gradient(135deg,#0d1a2e,#0e2040);
  border: 1px solid rgba(61,142,248,.18); border-left: 2px solid var(--acc);
  border-radius: 12px; padding: 14px 18px; margin-bottom: 12px;
  font-size: 0.87em; color: #a0c0e8; line-height: 1.78;
}
.nx-ai-hdr { display: flex; align-items: center; gap: 7px; margin-bottom: 9px; }
.nx-ai-dot {
  width: 5px; height: 5px; border-radius: 50%; background: var(--acc);
  box-shadow: 0 0 7px var(--acc); animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.25;} }
.nx-ai-t { font-size: 0.69em; font-weight: 700; color: var(--acc); text-transform: uppercase; letter-spacing: .1em; }

.nx-reco { background: var(--surf); border: 1px solid var(--bdr); border-radius: 11px; padding: 13px 16px; font-size: 0.87em; color: var(--txt2); line-height: 1.65; margin-bottom: 12px; }
.nx-step { background: var(--surf); border-left: 2px solid var(--acc); border-radius: 0 9px 9px 0; padding: 8px 14px; font-size: 0.85em; color: var(--txt2); margin-bottom: 5px; }
.nx-resp-si { background: var(--green-s); border-left: 2px solid var(--green); border-radius: 0 7px 7px 0; padding: 7px 12px; margin-bottom: 4px; font-size: 0.83em; color: #5dd898; }
.nx-resp-no { background: var(--surf); border-left: 2px solid var(--bdr); border-radius: 0 7px 7px 0; padding: 7px 12px; margin-bottom: 4px; font-size: 0.83em; color: var(--txt3); }
.nx-aviso { background: var(--gold-s); border: 1px solid rgba(212,160,32,.2); border-radius: 9px; padding: 10px 14px; font-size: 0.81em; color: #a07830; text-align: center; }
.nx-aviso strong { color: var(--gold); }

.nx-chat-bot  { background: var(--surf); border: 1px solid var(--bdr); border-radius: 4px 13px 13px 13px; padding: 8px 14px; font-size: 0.86em; color: var(--txt2); display: inline-block; max-width: 84%; margin-bottom: 6px; }
.nx-chat-user { background: #1a2e58; border-radius: 13px 4px 13px 13px; padding: 8px 14px; font-size: 0.86em; color: #a8c4ff; font-weight: 600; float: right; display: inline-block; max-width: 84%; margin-bottom: 6px; }
.nx-chat-wrap { overflow: hidden; margin-bottom: 2px; }

.nx-hosp {
  background: var(--surf); border: 1px solid var(--bdr); border-radius: 12px;
  padding: 4px 16px; margin-bottom: 12px;
}
.nx-hosp-row {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 0; border-bottom: 1px solid var(--bdr-s);
}
.nx-hosp-row:last-child { border-bottom: none; }

.nx-emerg {
  background: var(--surf);
  border: 1px solid var(--bdr);
  border-radius: 14px;
  padding: 6px 4px;
  overflow: hidden;
}
.nx-emerg-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 16px;
  border-radius: 10px;
  margin: 2px 4px;
  transition: background .16s ease;
  position: relative;
}
.nx-emerg-row:hover { background: rgba(61,142,248,.06); }
.nx-emerg-row::after {
  content: '';
  position: absolute; bottom: 0; left: 16px; right: 16px; height: 1px;
  background: var(--bdr-s);
}
.nx-emerg-row:last-child::after { display: none; }
.nx-emerg-n {
  font-size: 0.84em; color: var(--txt2);
  display: flex; align-items: center; gap: 6px;
}
.nx-emerg-num {
  font-size: 1.08em; font-weight: 900; letter-spacing: 2px;
  text-decoration: none; font-family: 'DM Mono', monospace;
  padding: 4px 12px; border-radius: 8px;
  background: rgba(0,0,0,.2);
  transition: all .16s ease;
}
.nx-emerg-num:hover { filter: brightness(1.25); transform: scale(1.06); }

/* ══ PIN SCREEN ══ */
.nx-pin-wrap { max-width: 400px; margin: 36px auto; }

.nx-pin-card {
  background: linear-gradient(160deg, #0d1e38 0%, #111d30 100%);
  border: 1px solid rgba(61,142,248,.22);
  border-radius: 24px;
  padding: 40px 36px 32px;
  text-align: center;
  position: relative;
  overflow: hidden;
  box-shadow: 0 8px 48px rgba(0,0,0,.45), 0 0 0 1px rgba(61,142,248,.08);
}
.nx-pin-card::before {
  content:''; position:absolute; top:0; left:0; right:0; height:2px;
  background: linear-gradient(90deg, transparent, rgba(61,142,248,.7), rgba(40,184,110,.5), transparent);
}

/* Anillo animado alrededor del icono */
.nx-pin-ring {
  width: 96px; height: 96px;
  border-radius: 50%;
  background: rgba(61,142,248,.08);
  border: 2px solid rgba(61,142,248,.18);
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 18px;
  position: relative;
  animation: pinRingPulse 3s ease-in-out infinite;
  transition: all .4s cubic-bezier(.22,.68,0,1.2);
}
.nx-pin-ring::after {
  content:''; position:absolute; inset:-6px;
  border-radius:50%;
  border: 1px solid rgba(61,142,248,.1);
  animation: pinRingOuter 3s ease-in-out infinite .4s;
}
@keyframes pinRingPulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(61,142,248,.15); }
  50%      { box-shadow: 0 0 0 10px rgba(61,142,248,.0); }
}
@keyframes pinRingOuter {
  0%,100% { opacity:.4; transform:scale(1);   }
  50%      { opacity:.1; transform:scale(1.08); }
}
/* Estado correcto: anillo verde + bounce */
.nx-pin-ring.ok {
  background: rgba(40,184,110,.12);
  border-color: rgba(40,184,110,.4);
  animation: pinOk .5s cubic-bezier(.22,.68,0,1.4) both;
}
@keyframes pinOk {
  0%   { transform: scale(.85); opacity:.5; }
  60%  { transform: scale(1.12); }
  100% { transform: scale(1); opacity:1; }
}
/* Estado error: anillo rojo + shake */
.nx-pin-ring.err {
  background: rgba(232,64,64,.1);
  border-color: rgba(232,64,64,.35);
  animation: pinShake .45s ease both;
}
@keyframes pinShake {
  0%,100% { transform:translateX(0); }
  20%      { transform:translateX(-7px); }
  40%      { transform:translateX(7px); }
  60%      { transform:translateX(-5px); }
  80%      { transform:translateX(4px); }
}

.nx-pin-ico { font-size: 2.6rem; line-height:1; transition: all .35s ease; }
.nx-pin-t   { font-size: 1.15rem; font-weight: 800; color: var(--txt); margin-bottom: 5px; letter-spacing: -.3px; }
.nx-pin-s   { font-size: 0.82rem; color: var(--txt3); line-height: 1.5; }

/* Dots indicador PIN */
.nx-pin-dots {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; margin: 22px 0 8px;
}
.nx-pin-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: rgba(61,142,248,.15);
  border: 1.5px solid rgba(61,142,248,.25);
  transition: all .2s ease;
}
.nx-pin-dot.filled {
  background: var(--acc);
  border-color: var(--acc);
  box-shadow: 0 0 8px rgba(61,142,248,.5);
  transform: scale(1.1);
}
.nx-pin-dot.err-dot {
  background: #e84040;
  border-color: #e84040;
  box-shadow: 0 0 8px rgba(232,64,64,.5);
}

.nx-err {
  background: rgba(232,64,64,.08);
  border: 1px solid rgba(232,64,64,.25);
  border-radius: 10px; padding: 11px 16px;
  color: #ff7070; font-size: 0.82rem;
  margin-top: 12px; text-align: center;
  display: flex; align-items: center; justify-content: center; gap: 7px;
  animation: fadeInUp .25s ease both;
}

/* ══ MICRO-ANIMACIONES GLOBALES ══ */
@keyframes pageIn { from{opacity:0;transform:translateY(12px);} to{opacity:1;transform:translateY(0);} }
.block-container { animation: pageIn .32s cubic-bezier(.22,.68,0,1.2) both; }
@keyframes barFill { from{width:0 !important;} to{} }
@keyframes floatEmoji { 0%,100%{transform:translateY(0) scale(1);} 50%{transform:translateY(-10px) scale(1.06);} }
@keyframes heroPulse { 0%,100%{box-shadow:0 0 0 0 rgba(255,255,255,.06);} 50%{box-shadow:0 0 40px 8px rgba(255,255,255,.04);} }
@keyframes slideInRight { from{opacity:0;transform:translateX(20px);} to{opacity:1;transform:translateX(0);} }
@keyframes slideInLeft  { from{opacity:0;transform:translateX(-20px);} to{opacity:1;transform:translateX(0);} }
@keyframes popIn { from{opacity:0;transform:scale(.88);} to{opacity:1;transform:scale(1);} }
@keyframes nxRingPulse1 { 0%{box-shadow:0 0 0 0 var(--nx-ring-clr,.5);} 70%{box-shadow:0 0 0 22px rgba(0,0,0,0);} 100%{box-shadow:0 0 0 0 rgba(0,0,0,0);} }
@keyframes nxRingPulse2 { 0%{box-shadow:0 0 0 0 var(--nx-ring-clr,.3);} 70%{box-shadow:0 0 0 18px rgba(0,0,0,0);} 100%{box-shadow:0 0 0 0 rgba(0,0,0,0);} }
@keyframes nxShimmer    { 0%{background-position:-200% center;} 100%{background-position:200% center;} }

/* ══ TRIAJE — Botones Sí / No ══ */
[data-testid^="stButton-si_"] > button {
  background: rgba(40,184,110,.11) !important;
  border: 1.5px solid rgba(40,184,110,.38) !important;
  color: #28b86e !important; font-size: 1.08rem !important;
  min-height: 60px !important; font-weight: 800 !important;
  letter-spacing: .02em !important; border-radius: 14px !important;
  transition: all .2s cubic-bezier(.22,.68,0,1.2) !important;
}
[data-testid^="stButton-si_"] > button:hover {
  background: rgba(40,184,110,.22) !important;
  border-color: rgba(40,184,110,.65) !important;
  transform: translateY(-3px) scale(1.02) !important;
  box-shadow: 0 10px 28px rgba(40,184,110,.22) !important;
  color: #5de8a0 !important;
}
[data-testid^="stButton-no_"] > button {
  background: rgba(232,64,64,.08) !important;
  border: 1.5px solid rgba(232,64,64,.28) !important;
  color: #e84040 !important; font-size: 1.08rem !important;
  min-height: 60px !important; font-weight: 800 !important;
  letter-spacing: .02em !important; border-radius: 14px !important;
  transition: all .2s cubic-bezier(.22,.68,0,1.2) !important;
}
[data-testid^="stButton-no_"] > button:hover {
  background: rgba(232,64,64,.16) !important;
  border-color: rgba(232,64,64,.55) !important;
  transform: translateY(-3px) scale(1.02) !important;
  box-shadow: 0 10px 28px rgba(232,64,64,.18) !important;
  color: #ff7070 !important;
}

/* ══ CHAT — Chip buttons ══ */
[data-testid^="stButton-chip"] > button {
  background: rgba(61,142,248,.07) !important;
  border: 1px solid rgba(61,142,248,.25) !important;
  color: #5a9ef8 !important;
  border-radius: 99px !important;
  font-size: .76rem !important;
  font-weight: 700 !important;
  height: 34px !important;
  padding: 0 8px !important;
  transition: all .15s ease !important;
}
[data-testid^="stButton-chip"] > button:hover {
  background: rgba(61,142,248,.16) !important;
  border-color: rgba(61,142,248,.45) !important;
  color: #8ab8ff !important;
  transform: translateY(-1px) !important;
}

/* ══ CHAT — Send button ══ */
[data-testid="stButton-chat_send"] > button {
  background: linear-gradient(135deg,#1a4a9e,#1e5bcc) !important;
  border: 1px solid rgba(61,142,248,.4) !important;
  color: #fff !important;
  border-radius: 10px !important;
  font-size: 1rem !important;
  height: 42px !important;
  transition: all .15s ease !important;
}
[data-testid="stButton-chat_send"] > button:hover {
  background: linear-gradient(135deg,#2055bb,#2a6ae0) !important;
  transform: translateY(-1px) !important;
}

/* ══ TRIAJE — Pregunta ══ */
.tx-wrap {
  background: linear-gradient(135deg,#0d1e38,#0f244a);
  border: 1px solid rgba(61,142,248,.22);
  border-top: 3px solid var(--acc);
  border-radius: 18px; padding: 0; margin-bottom: 14px;
  overflow: hidden;
  animation: popIn .35s cubic-bezier(.22,.68,0,1.2) both;
}
.tx-hdr {
  background: rgba(61,142,248,.06);
  padding: 14px 22px;
  border-bottom: 1px solid rgba(61,142,248,.12);
  display: flex; align-items: center; gap: 12px;
}
.tx-num {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--acc); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: .92rem; font-weight: 800; flex-shrink: 0;
  box-shadow: 0 0 14px rgba(61,142,248,.45);
}
.tx-tag { font-size: .72rem; font-weight: 700; color: var(--acc); text-transform: uppercase; letter-spacing: .1em; }
.tx-counter { margin-left: auto; font-size: .78rem; color: var(--txt3); font-weight: 600; }
.tx-body { padding: 22px 24px 24px; }
.tx-txt { font-size: 1.2rem; font-weight: 600; color: var(--txt); line-height: 1.5; }

/* ══ RESULTADO — Hero urgencia ══ */
.rx-hero {
  border-radius: 20px; padding: 30px 26px 26px;
  margin-bottom: 16px; text-align: center;
  position: relative; overflow: hidden;
  animation: popIn .4s cubic-bezier(.22,.68,0,1.2) both;
}
.rx-hero::after {
  content:''; position:absolute; inset:0;
  animation: heroPulse 3.5s ease-in-out infinite;
  pointer-events: none;
}
.rx-emoji { font-size: 4.2rem; display: block; margin-bottom: 10px;
  animation: floatEmoji 4s ease-in-out 1s infinite; }
.rx-level { font-size: 2.2rem; font-weight: 900; letter-spacing: 4px;
  text-transform: uppercase; line-height: 1; margin-bottom: 6px; }
.rx-sub { font-size: .88rem; opacity: .65; margin-bottom: 14px; }
.rx-pct {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(0,0,0,.25); border: 1px solid rgba(255,255,255,.15);
  border-radius: 99px; padding: 6px 20px;
  font-size: .88rem; font-weight: 700;
}

/* Barra gravedad animada */
.rx-bar-wrap { background: var(--surf); border: 1px solid var(--bdr); border-radius: 14px; padding: 16px 20px; margin-bottom: 14px; }
.rx-bar-title { font-size: .67rem; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px; display: flex; justify-content: space-between; }
.rx-bar-track {
  height: 10px; border-radius: 99px;
  background: linear-gradient(90deg,#28b86e 0%,#d4a020 30%,#e87228 60%,#e84040 100%);
  position: relative; margin-bottom: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,.3);
}
.rx-bar-marker {
  position: absolute; top: -4px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #fff; border: 3px solid currentColor;
  transform: translateX(-50%);
  box-shadow: 0 0 12px currentColor, 0 2px 6px rgba(0,0,0,.4);
  transition: left 1s cubic-bezier(.22,.68,0,1.2);
}
.rx-bar-lbls { display: flex; justify-content: space-between; font-size: .66rem; color: var(--txt3); margin-top: 4px; }

/* Stats mejoradas */
.rx-stats { display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; margin-bottom: 14px; }
.rx-stat {
  background: var(--surf); border: 1px solid var(--bdr); border-radius: 12px;
  padding: 14px 10px 12px; text-align: center;
  animation: pageIn .4s ease both;
  min-height: 64px;
}
.rx-stat:nth-child(1){animation-delay:.1s;}
.rx-stat:nth-child(2){animation-delay:.2s;}
.rx-stat:nth-child(3){animation-delay:.3s;}
.rx-stat-l { font-size: .63rem; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .07em; margin-bottom: 5px; }
.rx-stat-v { font-size: 1rem; font-weight: 700; color: var(--txt); }

/* ══ STEPS — Qué hacer ══ */
.rx-step {
  display: flex; gap: 12px; align-items: flex-start;
  background: var(--surf); border: 1px solid var(--bdr);
  border-radius: 12px; padding: 13px 16px; margin-bottom: 8px;
  animation: slideInRight .4s ease both;
}
.rx-step-n {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: .82rem; font-weight: 800; color: #fff;
  background: var(--acc); box-shadow: 0 0 10px rgba(61,142,248,.35);
}
.rx-step-txt { font-size: .88rem; color: var(--txt2); line-height: 1.55; padding-top: 3px; }

/* ══ CHAT rediseño ══ */
.nx-chat-container {
  background: var(--bg); border: 1px solid var(--bdr);
  border-radius: 14px; padding: 14px 12px;
  max-height: 300px; overflow-y: auto; margin-bottom: 10px;
  scrollbar-width: thin; scrollbar-color: var(--bdr) transparent;
}
.nx-msg { display: flex; gap: 9px; margin-bottom: 10px; align-items: flex-end; }
.nx-msg.u { flex-direction: row-reverse; }
.nx-av {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: .85rem;
}
.nx-av.bot { background: rgba(61,142,248,.12); border: 1px solid rgba(61,142,248,.22); }
.nx-av.usr { background: rgba(40,184,110,.10); border: 1px solid rgba(40,184,110,.2); }
.nx-bubble {
  max-width: 82%; padding: 10px 14px; font-size: .87rem; line-height: 1.6;
  animation: slideInLeft .25s ease both;
}
.nx-msg.u .nx-bubble { animation-name: slideInRight; }
.nx-bubble.bot {
  background: var(--surf); border: 1px solid var(--bdr);
  border-radius: 4px 14px 14px 14px; color: var(--txt2);
}
.nx-bubble.usr {
  background: linear-gradient(135deg,rgba(30,70,180,.3),rgba(40,90,200,.2));
  border: 1px solid rgba(61,142,248,.25);
  border-radius: 14px 4px 14px 14px; color: #b8d4ff;
}
.nx-chat-empty {
  text-align: center; padding: 20px; color: var(--txt3); font-size: .85rem;
}

/* ══ HOSPITALES rediseño ══ */
.nx-hosp-card {
  background: var(--surf); border: 1px solid var(--bdr); border-radius: 13px;
  padding: 13px 16px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 12px;
  transition: border-color .18s, transform .18s, box-shadow .18s;
  animation: slideInRight .3s ease both;
}
.nx-hosp-card:hover {
  border-color: rgba(61,142,248,.38); transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,.2);
}
.nx-hosp-ico-wrap {
  width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 1.35rem;
  background: rgba(61,142,248,.07); border: 1px solid rgba(61,142,248,.14);
}
.nx-hosp-info { flex: 1; min-width: 0; }
.nx-hosp-name { font-size: .9rem; font-weight: 700; color: var(--txt); margin-bottom: 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nx-hosp-type { font-size: .73rem; color: var(--txt3); }
.nx-hosp-badges { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0; }
.nx-dist-badge {
  display: inline-flex; align-items: center; gap: 4px;
  background: rgba(61,142,248,.1); border: 1px solid rgba(61,142,248,.2);
  color: var(--acc); border-radius: 8px; padding: 3px 9px;
  font-size: .72rem; font-weight: 700;
}
.nx-urg-badge {
  background: var(--red-s); border: 1px solid rgba(232,64,64,.25);
  color: var(--red); border-radius: 6px; padding: 2px 7px;
  font-size: .68rem; font-weight: 700;
}
.nx-rec-badge {
  background: var(--orange-s); border: 1px solid rgba(232,114,40,.25);
  color: var(--orange); border-radius: 6px; padding: 2px 7px;
  font-size: .68rem; font-weight: 700;
}

/* ══ LIVE STATS BAR ══ */
.hm-statsbar {
  display: grid; grid-template-columns: repeat(3,1fr); gap: 12px;
  margin: 18px 0 14px;
}
.hm-statcard {
  background: linear-gradient(135deg,#131f30,#162740);
  border: 1px solid var(--bdr); border-radius: 14px;
  padding: 16px 18px; text-align: center; position: relative; overflow: hidden;
  transition: transform .2s, border-color .2s;
}
.hm-statcard:hover { transform: translateY(-2px); border-color: rgba(61,142,248,.38); }
.hm-statcard::before {
  content:''; position:absolute; top:0; left:0; right:0; height:2px;
  background: linear-gradient(90deg,transparent,rgba(61,142,248,.5),transparent);
}
.hm-statcard-icon { font-size:1.6rem; margin-bottom:6px; }
.hm-statcard-val  { font-size:1.4rem; font-weight:900; color:var(--txt); letter-spacing:-0.5px; margin-bottom:3px; }
.hm-statcard-lbl  { font-size:.65rem; font-weight:700; color:var(--txt3); text-transform:uppercase; letter-spacing:.1em; }

/* ══ CÓMO FUNCIONA — 3 pasos ══ */
.hm-how { margin: 4px 0 18px; }
.hm-how-title {
  font-size:.68rem; font-weight:700; color:var(--txt3);
  text-transform:uppercase; letter-spacing:.12em;
  display:flex; align-items:center; gap:7px;
  margin-bottom:12px; padding-bottom:7px; border-bottom:1px solid var(--bdr-s);
}
.hm-how-title::before {
  content:''; width:3px; height:11px; background:var(--acc);
  border-radius:2px; display:inline-block;
}
.hm-how-steps {
  display:grid; grid-template-columns:1fr auto 1fr auto 1fr; gap:0; align-items:center;
}
.hm-how-step {
  background:linear-gradient(135deg,#131f30,#162740);
  border:1px solid var(--bdr); border-radius:14px;
  padding:18px 14px; text-align:center;
}
.hm-how-num {
  width:28px; height:28px; border-radius:50%;
  background:var(--acc); color:#fff;
  display:flex; align-items:center; justify-content:center;
  font-size:.82rem; font-weight:800; margin:0 auto 8px;
  box-shadow:0 0 12px rgba(61,142,248,.4);
}
.hm-how-icon  { font-size:1.5rem; margin-bottom:6px; }
.hm-how-stitle { font-size:.82rem; font-weight:700; color:var(--txt); margin-bottom:4px; }
.hm-how-sdesc  { font-size:.72rem; color:var(--txt3); line-height:1.5; }
.hm-how-arrow  { font-size:1.2rem; color:var(--txt3); padding:0 6px; text-align:center; }

/* ══ FEEDBACK ══ */
.nx-fb-row {
  display:flex; align-items:center; gap:10px;
  padding:12px 0 4px;
}
.nx-fb-lbl {
  font-size:.75rem; font-weight:700; color:var(--txt3);
  text-transform:uppercase; letter-spacing:.08em;
}
.nx-fb-ok {
  display:flex; align-items:center; gap:8px;
  background:rgba(40,184,110,.08); border:1px solid rgba(40,184,110,.22);
  border-radius:10px; padding:10px 18px;
  font-size:.84rem; font-weight:700; color:#28b86e;
  animation:popIn .4s cubic-bezier(.22,.68,0,1.2) both;
}

/* ══ STAT card 4 columnas ══ */
.rx-stat-4 {
  display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:10px;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TRADUCCIONES  (ES / EN)
# ══════════════════════════════════════════════════════════════════════════════
_TR = {
    # ── Header ──
    "hdr_sub":        {"es": "Sistema de Triaje Médico con IA · TFG SMR 2025-2026",
                       "en": "AI Medical Triage System · Final Degree Project 2025-2026"},
    "hdr_badge":      {"es": "⚕️ Triaje · IA · Proyecto TFG SMR",
                       "en": "⚕️ Triage · AI · Final Degree Project"},
    "hdr_112":        {"es": "🚨 Emergencia → 112",    "en": "🚨 Emergency → 112"},
    # ── Botones globales ──
    "btn_start":      {"es": "🩺  Iniciar triaje ahora","en": "🩺  Start triage now"},
    "btn_nueva":      {"es": "↩ Nueva consulta",       "en": "↩ New consultation"},
    "btn_pdf":        {"es": "📄 Descargar PDF",        "en": "📄 Download PDF"},
    "btn_admin":      {"es": "🔐 Acceso personal sanitario","en": "🔐 Medical staff access"},
    "btn_salir":      {"es": "↩ Salir",                "en": "↩ Exit"},
    "btn_si":         {"es": "✅  Sí, lo tengo",        "en": "✅  Yes, I have it"},
    "btn_no":         {"es": "❌  No, no lo tengo",     "en": "❌  No, I don't"},
    "btn_buscar":     {"es": "Buscar",                 "en": "Search"},
    "btn_mi_ubicac":  {"es": "📍",                     "en": "📍"},
    "btn_confirmar":  {"es": "✅ Confirmar y comenzar", "en": "✅ Confirm and start"},
    "btn_cambiar":    {"es": "❌ Cambiar",              "en": "❌ Change"},
    # ── Home ──
    "hm_datos_title": {"es": "Datos del paciente",     "en": "Patient data"},
    "hm_datos_sub":   {"es": "Opcional — mejora la precisión del informe",
                       "en": "Optional — improves report accuracy"},
    "hm_edad":        {"es": "Edad",                   "en": "Age"},
    "hm_sexo":        {"es": "Sexo",                   "en": "Sex"},
    "hm_alt":         {"es": "Altura (cm)",            "en": "Height (cm)"},
    "hm_pes":         {"es": "Peso (kg)",               "en": "Weight (kg)"},
    "hm_email":       {"es": "📧 Email — recibirás el informe PDF",
                       "en": "📧 Email — you'll receive the PDF report"},
    "hm_desc_lbl":    {"es": "🧠 O describe tus síntomas con palabras",
                       "en": "🧠 Or describe your symptoms in words"},
    "hm_desc_ph":     {"es": "Ej: me duele la cabeza y tengo fiebre…",
                       "en": "E.g.: I have a headache and fever…"},
    "hm_sym_title":   {"es": "Selecciona tu síntoma principal",
                       "en": "Select your main symptom"},
    "hm_sym_sub":     {"es": "Toca el que mejor describa cómo te sientes ahora mismo",
                       "en": "Tap the one that best describes how you feel right now"},
    "hm_hero_title":  {"es": "¿Cómo te encuentras hoy?",
                       "en": "How are you feeling today?"},
    "hm_hero_sub":    {"es": "Selecciona o describe tu síntoma principal — el triaje toma menos de 2 minutos y genera un informe médico completo con IA.",
                       "en": "Select or describe your main symptom — triage takes less than 2 minutes and generates a full AI medical report."},
    "hm_cap_time":    {"es": "⚡ Resultado en < 2 min", "en": "⚡ Result in < 2 min"},
    "hm_cap_pdf":     {"es": "📄 Informe PDF adjunto",  "en": "📄 PDF report attached"},
    "hm_ia_on":       {"es": "🤖 IA Groq/Claude activa","en": "🤖 Groq/Claude AI active"},
    "hm_ia_off":      {"es": "📊 Modo análisis básico", "en": "📊 Basic analysis mode"},
    # ── Resultado ──
    "rx_sintoma":     {"es": "Síntoma",                "en": "Symptom"},
    "rx_punt":        {"es": "Puntuación",             "en": "Score"},
    "rx_grav":        {"es": "Gravedad",               "en": "Severity"},
    "rx_urg":         {"es": "Nivel de urgencia",      "en": "Urgency level"},
    "rx_idx_grav":    {"es": "índice de gravedad",     "en": "severity index"},
    "rx_leve":        {"es": "Leve",                   "en": "Mild"},
    "rx_mod":         {"es": "Moderado",               "en": "Moderate"},
    "rx_urg2":        {"es": "Urgente",                "en": "Urgent"},
    "rx_emerg":       {"es": "Emergencia",             "en": "Emergency"},
    "rx_ai_title":    {"es": "NexaCare IA · Análisis personalizado",
                       "en": "NexaCare AI · Personalised analysis"},
    "rx_reco":        {"es": "📌 Recomendación",       "en": "📌 Recommendation"},
    "rx_resp_exp":    {"es": "📋 Ver resumen de respuestas",
                       "en": "📋 View answer summary"},
    "rx_tab1":        {"es": "📋 Qué hacer",           "en": "📋 What to do"},
    "rx_tab2":        {"es": "🏥 Hospitales y emergencias",
                       "en": "🏥 Hospitals & emergencies"},
    "rx_tab3":        {"es": "💬 Consulta IA",         "en": "💬 AI Chat"},
    "rx_centros":     {"es": "Centros sanitarios cercanos",
                       "en": "Nearby healthcare centres"},
    "rx_telef":       {"es": "Teléfonos de emergencia","en": "Emergency numbers"},
    "rx_chat_hint":   {"es": "¿Puedo tomar ibuprofeno? ¿Cuándo ir a urgencias?…",
                       "en": "Can I take ibuprofen? When should I go to A&E?…"},
    "rx_chat_lbl":    {"es": "Haz cualquier pregunta sobre tus síntomas",
                       "en": "Ask anything about your symptoms"},
    "rx_chat_empty":  {"es": "Escribe tu pregunta abajo para consultar a NexaCare IA",
                       "en": "Type your question below to consult NexaCare AI"},
    "rx_chat_send":   {"es": "Enviar",                 "en": "Send"},
    "rx_ub_ph":       {"es": "Ej: Calle Mayor 10, Madrid",
                       "en": "E.g.: 10 Main Street, London"},
    "rx_buscar_spin": {"es": "Buscando centros…",      "en": "Searching centres…"},
    "rx_no_loc":      {"es": "📍 <strong>No se pudo localizar.</strong> Incluye ciudad.",
                       "en": "📍 <strong>Could not locate.</strong> Please include a city."},
    "rx_sin_centros": {"es": "Sin centros públicos en 6 km.",
                       "en": "No public centres within 6 km."},
    "rx_responde":    {"es": "NexaCare responde basándose en tu síntoma:",
                       "en": "NexaCare answers based on your symptom:"},
    "rx_chip1":       {"es": "¿Puedo tomar ibuprofeno?","en": "Can I take ibuprofen?"},
    "rx_chip2":       {"es": "¿Cuándo ir a urgencias?","en": "When to go to A&E?"},
    "rx_chip3":       {"es": "¿Cuánto tiempo de reposo?","en": "How long to rest?"},
    "rx_spin_ia":     {"es": "🤖 NexaCare IA pensando…","en": "🤖 NexaCare AI thinking…"},
    "rx_spin_demo":   {"es": "Consultando…",            "en": "Consulting…"},
    "rx_spin_inf":    {"es": "🤖 NexaCare IA generando tu informe personalizado…",
                       "en": "🤖 NexaCare AI generating your personalised report…"},
    "rx_spin_calc":   {"es": "📊 Calculando resultado…","en": "📊 Calculating result…"},
    "rx_ia_activa":   {"es": "🟢 IA activa",            "en": "🟢 AI active"},
    "rx_ia_demo":     {"es": "🔵 Demo",                 "en": "🔵 Demo"},
    "rx_emerg1":      {"es": "🚨 Emergencias generales","en": "🚨 General emergencies"},
    "rx_emerg2":      {"es": "🏥 Urgencias sanitarias", "en": "🏥 Medical emergencies"},
    "rx_emerg3":      {"es": "👮 Policía Nacional",     "en": "👮 Police"},
    "rx_emerg4":      {"es": "🚒 Bomberos",             "en": "🚒 Fire brigade"},
    "rx_emerg5":      {"es": "☎️ Atención psicológica", "en": "☎️ Mental health support"},
    "hm_no_sym":      {"es": "🔍 <strong>No identifiqué el síntoma.</strong> Selecciónalo en la lista de la derecha.",
                       "en": "🔍 <strong>Could not identify the symptom.</strong> Please select it from the list on the right."},
    "hm_ia_spin":     {"es": "🤖 NexaCare IA identificando síntoma…",
                       "en": "🤖 NexaCare AI identifying symptom…"},
    "hm_ana_spin":    {"es": "🔍 Analizando síntomas…", "en": "🔍 Analysing symptoms…"},
    "rx_email_ok":    {"es": "Informe enviado por email correctamente",
                       "en": "Report sent by email successfully"},
    "rx_aviso":       {"es": "⚠️ <strong>Aviso:</strong> NexaCare es un proyecto académico TFG de SMR. No sustituye la valoración médica. Ante cualquier duda llama al <strong>112</strong>.",
                       "en": "⚠️ <strong>Notice:</strong> NexaCare is an academic TFG project. It does not replace professional medical assessment. If in doubt, call <strong>112</strong>."},
    # ── Triaje ──
    "tx_tag":         {"es": "NexaCare · Evaluación de síntomas",
                       "en": "NexaCare · Symptom assessment"},
    "tx_prog":        {"es": "Progreso del triaje",    "en": "Triage progress"},
    "tx_riesgo":      {"es": "Riesgo acumulado",       "en": "Accumulated risk"},
    "tx_eval":        {"es": "Evaluación en curso",    "en": "Assessment in progress"},
    "tx_pregunta":    {"es": "Pregunta",               "en": "Question"},
    # ── Admin ──
    "adm_exit":       {"es": "← Salir del panel",     "en": "← Exit panel"},
    "adm_title":      {"es": "Panel de Administración · NexaCare",
                       "en": "Administration Panel · NexaCare"},
    "adm_sub":        {"es": "Acceso restringido · Personal sanitario autorizado · Datos en tiempo real",
                       "en": "Restricted access · Authorised medical staff · Real-time data"},
    "adm_badge_op":   {"es": "Sistema operativo",     "en": "System operational"},
    "adm_badge_cons": {"es": "consultas registradas", "en": "consultations registered"},
    "adm_export":     {"es": "📄 Exportar informe administrativo completo (PDF)",
                       "en": "📄 Export full administrative report (PDF)"},
    "adm_spin":       {"es": "Preparando informe PDF…","en": "Preparing PDF report…"},
    # ── Home selectbox options ──
    "hm_sx_masc":     {"es": "Masculino",             "en": "Male"},
    "hm_sx_fem":      {"es": "Femenino",              "en": "Female"},
    # ── Landing chips ──
    "ld_leve":        {"es": "Verde — Leve",           "en": "Green — Mild"},
    "ld_mod":         {"es": "Amarillo — Moderado",    "en": "Yellow — Moderate"},
    "ld_urg":         {"es": "Naranja — Urgente",      "en": "Orange — Urgent"},
    "ld_emerg":       {"es": "Rojo — Emergencia",      "en": "Red — Emergency"},
}

def t(key: str) -> str:
    """Devuelve el texto en español."""
    return _TR.get(key, {}).get("es", key)


_DEF = {
    "_from_landing": False,
    "idioma":           "es",
    "pantalla":         "landing",
    "admin_ok":         False,
    "pin_intentos":     0,
    "edad_grupo":       None,
    "sexo":             None,
    "altura_cm":        "",
    "peso_kg":          "",
    "email_paciente":   "",
    "texto_libre":      "",
    "sintoma_sugerido": None,
    "sintoma":          None,
    "puntuacion":       0,
    "pregunta_idx":     0,
    "respuestas":       [],
    "inicio_triaje":    None,
    "consulta_guardada": False,
    "informe_ai":       None,
    "token_informe":    None,
    "webhook_enviado":  False,
    "chat_qa":          [],
    "chat_chip_pending": None,
    "centros":          None,
    "coords_busq":      None,
    "pedir_geoloc":     False,
    "ubicacion_busq":   "",
}
for k, v in _DEF.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Query param para hacer funcional el botón del HTML
try:
    go_param = st.query_params.get("go")
except Exception:
    go_param = None

if go_param == "home":
    st.session_state.pantalla = "home"
    st.session_state["_from_landing"] = True
    try:
        st.query_params.clear()
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────
def ir(pantalla: str):
    st.session_state.pantalla = pantalla
    st.rerun()


def reset_triaje():
    campos = ["sintoma","puntuacion","pregunta_idx","respuestas","inicio_triaje",
              "consulta_guardada","informe_ai","token_informe","webhook_enviado",
              "chat_qa","chat_chip_pending","centros","ubicacion_busq","sintoma_sugerido","texto_libre",
              "pedir_geoloc","coords_busq"]
    for k in campos:
        st.session_state[k] = _DEF[k]


def iniciar_triaje(nombre: str):
    reset_triaje()
    st.session_state.sintoma       = nombre
    st.session_state.puntuacion    = 0
    st.session_state.pregunta_idx  = 0
    st.session_state.respuestas    = []
    st.session_state.inicio_triaje = datetime.now()
    ir("triaje")


def ncolor(color: str) -> dict:
    return {
        "red":    {"bg":"#1a0808","bdr":"rgba(232,64,64,.3)","txt":"var(--red)","rgb":"232,64,64"},
        "orange": {"bg":"#1a1008","bdr":"rgba(232,114,40,.3)","txt":"var(--orange)","rgb":"232,114,40"},
        "gold":   {"bg":"#161200","bdr":"rgba(212,160,32,.3)","txt":"var(--gold)","rgb":"212,160,32"},
        "green":  {"bg":"#081a10","bdr":"rgba(40,184,110,.3)","txt":"var(--green)","rgb":"40,184,110"},
    }.get(color, {"bg":"var(--surf)","bdr":"var(--bdr)","txt":"var(--txt)","rgb":"61,142,248"})


def badge_cls(nivel: str) -> str:
    if "VERDE"    in nivel: return "bv"
    if "AMARILLO" in nivel: return "ba"
    if "NARANJA"  in nivel: return "bn"
    return "br"


def badge_key(nivel: str) -> str:
    if "VERDE"    in nivel: return "VERDE"
    if "AMARILLO" in nivel: return "AMARILLO"
    if "NARANJA"  in nivel: return "NARANJA"
    return "ROJO"


# ══════════════════════════════════════════════════════════════════════════════
# HEADER — visible en todas las pantallas EXCEPTO landing
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pantalla != "landing":

    st.markdown(f"""
    <div class="nx-hdr">
      <div>
        <div class="nx-logo"><span class="nx-cross"></span>Nexa<span>Care</span></div>
        <div class="nx-hdr-sub">{t('hdr_sub')}</div>
      </div>
      <div class="nx-hdr-center">
        <div class="nx-badge">{t('hdr_badge')}</div>
      </div>
      <div class="nx-hdr-right">
        <a class="nx-btn-112" href="tel:112">{t('hdr_112')}</a>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA: LANDING
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pantalla == "landing":
    # CSS: contenedor full-width sin padding para landing
    st.markdown("""
<style>
.block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stMain"] > div { padding-top: 0 !important; }
[data-testid="stVerticalBlock"] { gap: 0 !important; }
iframe { border: none !important; display: block !important; }
/* Botón CTA landing */
@keyframes nxPulse {
  0%   { box-shadow: 0 8px 32px rgba(61,142,248,.6), 0 0 0 0 rgba(61,142,248,.35); }
  70%  { box-shadow: 0 8px 32px rgba(61,142,248,.4), 0 0 0 18px rgba(61,142,248,0); }
  100% { box-shadow: 0 8px 32px rgba(61,142,248,.6), 0 0 0 0 rgba(61,142,248,0); }
}
#nx-landing-cta button,
#nx-landing-cta button:focus,
#nx-landing-cta [data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #1557c0 0%, #2d7ef0 40%, #5aaeff 100%) !important;
  color: #fff !important;
  border: 1px solid rgba(120,190,255,.25) !important;
  border-radius: 50px !important;
  min-height: 56px !important;
  padding: 0 44px !important;
  font-size: 1.08rem !important;
  font-weight: 800 !important;
  letter-spacing: .06em !important;
  text-transform: uppercase !important;
  animation: nxPulse 2.2s ease-in-out infinite !important;
  transition: transform .18s, filter .18s !important;
  outline: none !important;
  position: relative !important;
}
#nx-landing-cta button:hover,
#nx-landing-cta [data-testid="baseButton-primary"]:hover {
  transform: translateY(-3px) scale(1.04) !important;
  filter: brightness(1.15) !important;
  animation: none !important;
  box-shadow: 0 20px 56px rgba(61,142,248,.75) !important;
}
</style>""", unsafe_allow_html=True)

    _LANDING_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700;800;900&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{font-family:'DM Sans',-apple-system,sans-serif;background:#060f1e;color:#e2eaf6;
  height:100%;width:100%;overflow:hidden;}
body::before{content:'';position:fixed;inset:0;pointer-events:none;
  background:radial-gradient(ellipse 80% 60% at 20% 10%,rgba(37,90,210,.18) 0%,transparent 65%),
    radial-gradient(ellipse 60% 50% at 80% 80%,rgba(40,184,110,.10) 0%,transparent 60%);z-index:0;}
body::after{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:linear-gradient(rgba(61,142,248,.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(61,142,248,.04) 1px,transparent 1px);
  background-size:48px 48px;
  mask-image:radial-gradient(ellipse 80% 80% at 50% 50%,black 30%,transparent 100%);}
.root{position:relative;z-index:10;display:grid;grid-template-columns:1fr 1fr;
  height:100vh;width:100%;overflow:hidden;}
.left{display:flex;flex-direction:column;justify-content:center;
  padding:28px 36px 20px 48px;min-width:0;overflow:hidden;}
.right{display:flex;flex-direction:column;justify-content:center;
  padding:24px 48px 20px 32px;gap:12px;min-width:0;overflow:hidden;position:relative;}
.right::before{content:'';position:absolute;left:0;top:10%;bottom:10%;width:1px;
  background:linear-gradient(to bottom,transparent,rgba(61,142,248,.25),transparent);}
.badge{display:inline-flex;align-items:center;gap:8px;width:fit-content;
  background:rgba(61,142,248,.08);border:1px solid rgba(61,142,248,.28);
  color:#5ba8ff;padding:5px 14px;border-radius:999px;
  font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  margin-bottom:18px;animation:up .5s cubic-bezier(.22,.68,0,1.2) both .05s;}
.bdot{width:6px;height:6px;border-radius:50%;background:#3d8ef8;
  box-shadow:0 0 8px #3d8ef8;animation:glow 2s ease-in-out infinite;}
.logo{font-size:clamp(2.8rem,4.4vw,4.2rem);font-weight:900;letter-spacing:-2px;
  line-height:.95;margin-bottom:16px;white-space:nowrap;
  animation:up .7s cubic-bezier(.22,.68,0,1.2) both .12s;}
.logo-nexa{color:#e2eaf6;}
.logo-care{background:linear-gradient(135deg,#5ba8ff,#3d8ef8,#7fc3ff);
  background-size:200%;-webkit-background-clip:text;background-clip:text;color:transparent;
  animation:shine 3.5s linear infinite;}
.logo-cross{color:#3d8ef8;font-weight:900;margin-right:2px;
  text-shadow:0 0 18px rgba(61,142,248,.9),0 0 40px rgba(61,142,248,.4);
  display:inline;}
.sub{font-size:1.15rem;font-weight:600;color:#a8c8e8;line-height:1.5;max-width:480px;
  margin-bottom:10px;animation:up .6s cubic-bezier(.22,.68,0,1.2) both .20s;}
.desc{font-size:.92rem;color:#4a6888;line-height:1.7;max-width:480px;
  margin-bottom:24px;animation:up .6s cubic-bezier(.22,.68,0,1.2) both .28s;}
.steps{display:flex;flex-direction:column;gap:9px;
  animation:up .6s cubic-bezier(.22,.68,0,1.2) both .34s;}
.step{display:flex;align-items:center;gap:12px;}
.step-n{width:26px;height:26px;border-radius:50%;flex-shrink:0;
  background:rgba(61,142,248,.12);border:1px solid rgba(61,142,248,.3);
  color:#3d8ef8;font-size:.75rem;font-weight:800;
  display:flex;align-items:center;justify-content:center;}
.step-t{font-size:.95rem;color:#7a9ab8;}
.step-t strong{color:#c8dff2;font-weight:700;}
.foot{font-size:.7rem;color:#2e4a66;margin-top:16px;
  animation:up .4s ease both .7s;}
/* DERECHA */
.monitor{background:rgba(6,15,30,.9);border:1px solid rgba(61,142,248,.2);
  border-radius:14px;padding:14px 18px;
  animation:up .6s cubic-bezier(.22,.68,0,1.2) both .4s;position:relative;overflow:hidden;}
.monitor::before{content:'● REC';position:absolute;top:10px;right:12px;
  font-size:.62rem;font-weight:700;color:#e84040;letter-spacing:.08em;
  animation:recBlink 1.4s ease-in-out infinite;}
.mon-title{font-size:.62rem;font-weight:700;color:#3d5470;
  text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px;}
canvas#ekg{display:block;width:100%;height:48px;}
.niveles{display:flex;flex-direction:column;gap:7px;
  animation:up .6s cubic-bezier(.22,.68,0,1.2) both .5s;}
.nivel-row{background:rgba(6,15,30,.8);border:1px solid rgba(61,142,248,.1);
  border-radius:10px;padding:10px 14px;display:flex;align-items:center;gap:12px;}
.nivel-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;animation:glow 2s ease-in-out infinite;}
.nivel-info{flex:1;}
.nivel-name{font-size:.82rem;font-weight:700;margin-bottom:3px;}
.nivel-bar-track{height:4px;background:rgba(255,255,255,.06);border-radius:99px;overflow:hidden;}
.nivel-bar-fill{height:100%;border-radius:99px;width:0;transition:width 1.4s cubic-bezier(.22,.68,0,1.2);}
.nivel-pct{font-size:.75rem;font-weight:800;flex-shrink:0;min-width:32px;text-align:right;}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;
  animation:up .6s cubic-bezier(.22,.68,0,1.2) both .62s;}
.stat{background:rgba(6,15,30,.8);border:1px solid rgba(61,142,248,.12);
  border-radius:10px;padding:10px 12px;text-align:center;}
.stat-v{font-size:1.4rem;font-weight:900;color:#e2eaf6;line-height:1;}
.stat-l{font-size:.58rem;font-weight:700;color:#3d5470;text-transform:uppercase;
  letter-spacing:.1em;margin-top:3px;}
.aviso{display:flex;align-items:center;gap:8px;
  background:rgba(212,160,32,.05);border:1px solid rgba(212,160,32,.18);
  color:#9a7828;padding:7px 12px;border-radius:9px;
  font-size:.72rem;line-height:1.4;animation:up .4s ease both .72s;}
@keyframes up{from{opacity:0;transform:translateY(18px);}to{opacity:1;transform:translateY(0);}}
@keyframes shine{0%{background-position:0% center;}100%{background-position:200% center;}}
@keyframes glow{0%,100%{box-shadow:0 0 5px currentColor;}50%{box-shadow:0 0 14px currentColor,0 0 28px currentColor;}}
@keyframes recBlink{0%,100%{opacity:1;}50%{opacity:.25;}}
</style>
</head>
<body>
<div class="root">
  <div class="left">
    <div class="badge"><span class="bdot"></span>Sistema de Triaje Médico con IA · TFG SMR 2025–2026</div>
    <div class="logo">
      <span class="logo-nexa"><span class="logo-cross">+</span>Nexa</span><span class="logo-care">Care</span>
    </div>
    <p class="sub">Tu asistente de triaje médico personal, impulsado por Inteligencia Artificial</p>
    <p class="desc">Evalúa tus síntomas en menos de 2 minutos. Obtén tu nivel de urgencia, análisis clínico con IA y un informe PDF — sin registro, gratis.</p>
    <div class="steps">
      <div class="step"><div class="step-n">1</div><div class="step-t"><strong>Selecciona</strong> tu síntoma principal</div></div>
      <div class="step"><div class="step-n">2</div><div class="step-t"><strong>Responde</strong> 7 preguntas rápidas</div></div>
      <div class="step"><div class="step-n">3</div><div class="step-t"><strong>Recibe</strong> tu nivel de urgencia + informe IA</div></div>
    </div>
    <div class="foot">NexaCare · TFG SMR 2025–2026 · Pablo Esteban · Herramienta orientativa, no diagnóstico médico</div>
  </div>
  <div class="right">
    <div class="monitor">
      <div class="mon-title">Monitor de signos · NexaCare Live</div>
      <canvas id="ekg" height="48"></canvas>
    </div>
    <div class="niveles">
      <div class="nivel-row">
        <div class="nivel-dot" style="background:#28b86e;color:#28b86e;"></div>
        <div class="nivel-info"><div class="nivel-name" style="color:#28b86e;">VERDE — Leve</div>
          <div class="nivel-bar-track"><div class="nivel-bar-fill" id="b1" style="background:#28b86e;"></div></div></div>
        <div class="nivel-pct" style="color:#28b86e;">15%</div>
      </div>
      <div class="nivel-row">
        <div class="nivel-dot" style="background:#d4a020;color:#d4a020;"></div>
        <div class="nivel-info"><div class="nivel-name" style="color:#d4a020;">AMARILLO — Moderado</div>
          <div class="nivel-bar-track"><div class="nivel-bar-fill" id="b2" style="background:#d4a020;"></div></div></div>
        <div class="nivel-pct" style="color:#d4a020;">45%</div>
      </div>
      <div class="nivel-row">
        <div class="nivel-dot" style="background:#e87228;color:#e87228;"></div>
        <div class="nivel-info"><div class="nivel-name" style="color:#e87228;">NARANJA — Urgente</div>
          <div class="nivel-bar-track"><div class="nivel-bar-fill" id="b3" style="background:#e87228;"></div></div></div>
        <div class="nivel-pct" style="color:#e87228;">70%</div>
      </div>
      <div class="nivel-row">
        <div class="nivel-dot" style="background:#e84040;color:#e84040;animation:glow 1s ease-in-out infinite;"></div>
        <div class="nivel-info"><div class="nivel-name" style="color:#e84040;">ROJO — Emergencia</div>
          <div class="nivel-bar-track"><div class="nivel-bar-fill" id="b4" style="background:#e84040;"></div></div></div>
        <div class="nivel-pct" style="color:#e84040;">95%</div>
      </div>
    </div>
    <div class="stats">
      <div class="stat"><div class="stat-v">⚡</div><div class="stat-l">&lt; 2 min resultado</div></div>
      <div class="stat"><div class="stat-v">🤖</div><div class="stat-l">IA Groq + Claude</div></div>
      <div class="stat"><div class="stat-v">📄</div><div class="stat-l">Informe PDF</div></div>
    </div>
    <div class="aviso">⚠️ Herramienta orientativa — No sustituye la valoración médica profesional</div>
  </div>
</div>
<script>
setTimeout(function(){
  document.getElementById('b1').style.width='15%';
  document.getElementById('b2').style.width='45%';
  document.getElementById('b3').style.width='70%';
  document.getElementById('b4').style.width='95%';
},600);
(function(){
  var cv=document.getElementById('ekg');if(!cv)return;
  cv.width=cv.parentElement.offsetWidth||480;cv.height=48;
  var ctx=cv.getContext('2d'),W=cv.width,H=cv.height,pts=[],speed=2.2,t=0;
  function ekgY(v){var c=v%120;
    if(c<20)return H/2+Math.sin(c/20*Math.PI)*4;
    if(c<30)return H/2-20;if(c<36)return H/2+13;
    if(c<42)return H/2-16;if(c<50)return H/2+5;
    if(c<65)return H/2+Math.sin((c-65)/15*Math.PI)*5;
    return H/2+Math.sin(c/20*Math.PI)*2;}
  function draw(){
    ctx.clearRect(0,0,W,H);
    ctx.strokeStyle='rgba(61,142,248,.08)';ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(0,H/2);ctx.lineTo(W,H/2);ctx.stroke();
    pts.push({y:ekgY(t)});if(pts.length>Math.floor(W/speed)+2)pts.shift();t+=speed;
    ctx.lineWidth=2;
    var g=ctx.createLinearGradient(0,0,W,0);
    g.addColorStop(0,'rgba(61,142,248,0)');g.addColorStop(0.6,'rgba(61,142,248,.8)');
    g.addColorStop(0.85,'rgba(40,184,110,.9)');g.addColorStop(1,'rgba(61,142,248,.2)');
    ctx.strokeStyle=g;ctx.shadowColor='#3d8ef8';ctx.shadowBlur=7;
    ctx.beginPath();
    for(var i=0;i<pts.length;i++){if(i===0)ctx.moveTo(i*speed,pts[i].y);else ctx.lineTo(i*speed,pts[i].y);}
    ctx.stroke();
    var l=pts[pts.length-1];
    if(l){ctx.beginPath();ctx.arc(pts.length*speed,l.y,3,0,Math.PI*2);
      ctx.fillStyle='#7fc3ff';ctx.shadowBlur=12;ctx.shadowColor='#3d8ef8';ctx.fill();}
    requestAnimationFrame(draw);}
  draw();
})();
</script>
</body>
</html>"""

    components.html(_LANDING_HTML, height=740, scrolling=False)

    # Botón CTA — centrado
    st.markdown('<div id="nx-landing-cta" style="display:flex;justify-content:center;margin-top:-4px;background:#060f1e;padding:0;">', unsafe_allow_html=True)
    _, _col_btn, _ = st.columns([2, 3, 2])
    with _col_btn:
        if st.button("🩺  INICIAR TRIAJE AHORA", use_container_width=True,
                     type="primary", key="btn_landing_start"):
            st.session_state["_from_landing"] = True
            ir("home")
    st.markdown('</div>', unsafe_allow_html=True)

    # Estilizar el botón directamente por JS — busca por texto, aplica inline style
    components.html("""<script>
(function(){
  var doc = window.parent.document;

  // Añadir keyframes una sola vez
  if (!doc.getElementById('nx-pulse-kf')) {
    var kf = doc.createElement('style');
    kf.id = 'nx-pulse-kf';
    kf.textContent = '@keyframes nxCtaPulse{0%{box-shadow:0 0 0 0 rgba(61,142,248,.65),0 8px 30px rgba(61,142,248,.4)}65%{box-shadow:0 0 0 20px rgba(61,142,248,0),0 8px 30px rgba(61,142,248,.4)}100%{box-shadow:0 0 0 0 rgba(61,142,248,0),0 8px 30px rgba(61,142,248,.4)}}';
    doc.head.appendChild(kf);
  }

  function applyStyle() {
    var btns = doc.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {
      var b = btns[i];
      if (b.textContent.trim().toUpperCase().includes('INICIAR TRIAJE')) {
        b.style.setProperty('background', 'linear-gradient(135deg,#2563d4 0%,#3d8ef8 48%,#68b8ff 100%)', 'important');
        b.style.setProperty('border', 'none', 'important');
        b.style.setProperty('border-radius', '50px', 'important');
        b.style.setProperty('color', '#fff', 'important');
        b.style.setProperty('font-weight', '900', 'important');
        b.style.setProperty('font-size', '1.02rem', 'important');
        b.style.setProperty('letter-spacing', '.1em', 'important');
        b.style.setProperty('min-height', '54px', 'important');
        b.style.setProperty('animation', 'nxCtaPulse 2.2s ease-out infinite', 'important');
        b.style.setProperty('transition', 'transform .15s,filter .15s', 'important');
        b.style.setProperty('cursor', 'pointer', 'important');
        b.setAttribute('data-nx-styled','1');
        b.onmouseenter = function(){ this.style.setProperty('transform','translateY(-4px) scale(1.05)','important'); this.style.setProperty('filter','brightness(1.2)','important'); this.style.setProperty('animation','none','important'); };
        b.onmouseleave = function(){ this.style.setProperty('transform','none','important'); this.style.setProperty('filter','none','important'); this.style.setProperty('animation','nxCtaPulse 2.2s ease-out infinite','important'); };
        return true;
      }
    }
    return false;
  }

  // Reintentar hasta encontrar el botón
  var tries = 0;
  function retry() {
    if (!applyStyle() && tries++ < 20) setTimeout(retry, 200);
  }
  retry();
})();
</script>""", height=0)

    # ── bloque landing terminado ──


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA: PIN
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pantalla == "pin":
    _, col, _ = st.columns([1, 2, 1])
    with col:
        _pin_err   = st.session_state.get("pin_intentos", 0) > 0
        _pin_ok    = st.session_state.get("admin_ok", False)
        _ring_cls  = "ok" if _pin_ok else ("err" if _pin_err else "")
        _ico       = "🔓" if _pin_ok else ("🔐" if not _pin_err else "🔒")

        pin_v = st.session_state.get("_pin_input", "")
        _n_filled = min(len(pin_v), 4)
        _dots_html = "".join(
            f'<div class="nx-pin-dot {"err-dot" if _pin_err else "filled" if i < _n_filled else ""}"></div>'
            for i in range(4)
        )

        st.markdown(f"""
        <div class="nx-pin-card">
          <div class="nx-pin-ring {_ring_cls}">
            <div class="nx-pin-ico">{_ico}</div>
          </div>
          <div class="nx-pin-t">Acceso personal sanitario</div>
          <div class="nx-pin-s">Introduce el PIN de 4 dígitos para acceder al<br>panel de administración</div>
          <div class="nx-pin-dots">{_dots_html}</div>
        </div>""", unsafe_allow_html=True)

        _bloqueado = st.session_state.get("pin_intentos", 0) >= 5
        if _bloqueado:
            st.markdown('<div class="nx-err">🔒 Acceso bloqueado por demasiados intentos. Vuelve al inicio para reiniciar.</div>', unsafe_allow_html=True)
        else:
            pin_v = st.text_input(
                "PIN", type="password", placeholder="• • • •",
                label_visibility="collapsed", key="_pin_input",
            )
            if st.button("🔓  Acceder al panel", use_container_width=True, type="primary"):
                if pin_v == PIN_ADMIN:
                    st.session_state.admin_ok = True
                    st.session_state.pin_intentos = 0
                    ir("dashboard")
                else:
                    st.session_state.pin_intentos += 1
                    n = st.session_state.pin_intentos
                    restantes = max(0, 5 - n)
                    msg = f"PIN incorrecto · {f'{restantes} intento(s) restante(s)' if restantes > 0 else 'Acceso bloqueado.'}"
                    st.markdown(f'<div class="nx-err">🔒 {msg}</div>', unsafe_allow_html=True)
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        if st.button("← Volver al inicio", use_container_width=True):
            st.session_state.pin_intentos = 0
            ir("home")


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA: DASHBOARD ADMIN
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pantalla == "dashboard" and not st.session_state.admin_ok:
    ir("pin")

elif st.session_state.pantalla == "dashboard" and st.session_state.admin_ok:

    stats    = obtener_stats()
    total    = stats["total"]
    niv_raw  = stats.get("niveles_raw", {})
    sint_map = stats.get("sintomas", {})

    niveles = {"VERDE": 0, "AMARILLO": 0, "NARANJA": 0, "ROJO": 0}
    for ns, cnt in niv_raw.items():
        for k in niveles:
            if k in ns:
                niveles[k] += cnt
                break

    sint_top = max(sint_map, key=sint_map.get) if sint_map else "—"
    pct_rojo = int(niveles["ROJO"] / total * 100) if total else 0

    # ── CSS exclusivo del dashboard ───────────────────────────────────────────
    st.markdown("""
    <style>
    .adm-hero {
      background: linear-gradient(135deg, #0d1e38 0%, #0f2850 60%, #0d1e38 100%);
      border: 1px solid var(--bdr); border-radius: 18px;
      padding: 22px 28px; margin-bottom: 18px;
      display: flex; align-items: center; gap: 20px;
      position: relative; overflow: hidden;
    }
    .adm-hero::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, transparent, var(--acc), #28b86e, var(--acc), transparent);
    }
    .adm-hero-icon { font-size: 2.6rem; flex-shrink: 0; filter: drop-shadow(0 0 10px rgba(61,142,248,.5)); }
    .adm-hero-body { flex: 1; }
    .adm-hero-title { font-size: 1.4rem; font-weight: 800; color: var(--txt); letter-spacing: -.4px; margin-bottom: 4px; }
    .adm-hero-sub { font-size: .82rem; color: var(--txt2); }
    .adm-hero-badge {
      display: flex; flex-direction: column; gap: 6px; flex-shrink: 0;
    }
    .adm-badge-item {
      display: flex; align-items: center; gap: 7px;
      background: rgba(61,142,248,.07); border: 1px solid rgba(61,142,248,.14);
      border-radius: 9px; padding: 6px 13px; font-size: .78rem; color: var(--txt2);
      white-space: nowrap;
    }
    .adm-badge-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

    .adm-kpi {
      background: var(--surf); border: 1px solid var(--bdr); border-radius: 14px;
      padding: 0; overflow: hidden; position: relative;
    }
    .adm-kpi-top { height: 3px; width: 100%; }
    .adm-kpi-body { padding: 16px 18px 14px; }
    .adm-kpi-icon { font-size: 1.5rem; margin-bottom: 8px; display: block; }
    .adm-kpi-val { font-size: 2rem; font-weight: 900; line-height: 1; margin-bottom: 4px; }
    .adm-kpi-lbl { font-size: .62rem; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 3px; }
    .adm-kpi-sub { font-size: .72rem; color: var(--txt3); }

    .adm-panel {
      background: var(--surf); border: 1px solid var(--bdr); border-radius: 14px;
      padding: 18px 20px;
    }
    .adm-panel-title {
      font-size: .68rem; font-weight: 700; color: var(--txt3);
      text-transform: uppercase; letter-spacing: .12em;
      display: flex; align-items: center; gap: 7px;
      margin-bottom: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--bdr-s);
    }
    .adm-panel-title::before {
      content: ''; width: 3px; height: 11px; background: var(--acc);
      border-radius: 2px; display: inline-block; flex-shrink: 0;
    }

    .adm-bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .adm-bar-lbl { font-size: .8rem; color: var(--txt2); min-width: 155px; display: flex; align-items: center; gap: 7px; }
    .adm-bar-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .adm-bar-track { flex: 1; background: var(--bg); border-radius: 99px; height: 6px; overflow: hidden; }
    .adm-bar-fill  { height: 6px; border-radius: 99px; transition: width .6s ease; }
    .adm-bar-val   { font-size: .82rem; font-weight: 700; color: var(--txt); min-width: 28px; text-align: right; }

    .adm-table-hdr {
      display: grid; grid-template-columns: 88px 1fr 68px 58px 90px;
      gap: 6px; padding: 8px 14px;
      background: var(--raised); border-radius: 10px 10px 0 0;
      border: 1px solid var(--bdr); border-bottom: none;
    }
    .adm-table-row {
      display: grid; grid-template-columns: 88px 1fr 68px 58px 90px;
      gap: 6px; padding: 9px 14px; align-items: center;
      border: 1px solid var(--bdr-s); border-top: none;
      transition: background .15s;
    }
    .adm-table-row:last-child { border-radius: 0 0 10px 10px; }
    .adm-table-row:hover { background: var(--raised); }
    .adm-th { font-size: .61rem; font-weight: 700; color: var(--txt3); text-transform: uppercase; letter-spacing: .05em; }
    .adm-td { font-size: .8rem; color: var(--txt2); }
    .adm-ts { font-size: .71rem; color: var(--txt3); font-family: 'DM Mono', monospace; }
    </style>
    """, unsafe_allow_html=True)

    # ── Cabecera hero ─────────────────────────────────────────────────────────
    col_hdr, col_salir = st.columns([6, 1])
    with col_hdr:
        st.markdown(f"""
        <div class="adm-hero">
          <div class="adm-hero-icon">🏥</div>
          <div class="adm-hero-body">
            <div class="adm-hero-title">{t("adm_title")}</div>
            <div class="adm-hero-sub">{t("adm_sub")} · {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
          </div>
          <div class="adm-hero-badge">
            <div class="adm-badge-item"><span class="adm-badge-dot" style="background:var(--green);box-shadow:0 0 7px var(--green);"></span>{t("adm_badge_op")}</div>
            <div class="adm-badge-item"><span class="adm-badge-dot" style="background:var(--acc);box-shadow:0 0 7px var(--acc);"></span>{total} {t("adm_badge_cons")}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with col_salir:
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        if st.button(t("adm_exit"), use_container_width=True):
            st.session_state.admin_ok = False
            st.session_state.pop("_pdf_admin", None)
            ir("home")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    kpis = [
        (k1, "var(--acc)",    "#3d8ef8", "📊", "Total consultas",    str(total),            "histórico completo"),
        (k2, "var(--red)",    "#e84040", "🚨", "Emergencias rojo",   str(niveles["ROJO"]),  f"{pct_rojo}% del total"),
        (k3, "var(--orange)", "#e87228", "⚠️", "Urgentes naranja",   str(niveles["NARANJA"]),"atención prioritaria"),
        (k4, "var(--green)",  "#28b86e", "✅", "Casos leves",         str(niveles["VERDE"]), "atención diferida"),
    ]
    for col, css_col, hex_col, ico, lbl, val, sub in kpis:
        col.markdown(f"""
        <div class="adm-kpi">
          <div class="adm-kpi-top" style="background:{hex_col};"></div>
          <div class="adm-kpi-body">
            <span class="adm-kpi-icon">{ico}</span>
            <div class="adm-kpi-lbl">{lbl}</div>
            <div class="adm-kpi-val" style="color:{hex_col};">{val}</div>
            <div class="adm-kpi-sub">{sub}</div>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── Gráficos ──────────────────────────────────────────────────────────────
    ga, gb = st.columns(2, gap="medium")

    with ga:
        max_n = max(niveles.values()) or 1
        filas_niv = [
            ("🟢 Verde – Leve",          niveles["VERDE"],    "#28b86e"),
            ("🟡 Amarillo – Moderado",   niveles["AMARILLO"], "#d4a020"),
            ("🟠 Naranja – Urgente",     niveles["NARANJA"],  "#e87228"),
            ("🔴 Rojo – Emergencia",     niveles["ROJO"],     "#e84040"),
        ]
        filas_html = ""
        for nombre, val, col in filas_niv:
            pct = int(val / max_n * 100)
            pct_tot = int(val / total * 100) if total else 0
            filas_html += (
                f'<div class="adm-bar-row">'
                f'<div class="adm-bar-lbl"><span class="adm-bar-dot" style="background:{col};box-shadow:0 0 5px {col};"></span>{nombre}</div>'
                f'<div class="adm-bar-track"><div class="adm-bar-fill" style="background:{col};width:{pct}%;"></div></div>'
                f'<div class="adm-bar-val">{val} <span style="font-size:.68rem;color:var(--txt3);font-weight:400;">({pct_tot}%)</span></div>'
                f'</div>'
            )
        st.markdown(
            f'<div class="adm-panel"><div class="adm-panel-title">Distribución por nivel de urgencia</div>{filas_html}</div>',
            unsafe_allow_html=True)

    with gb:
        filas_sint = ""
        if sint_map:
            max_s = max(sint_map.values()) or 1
            colores_sint = ["#3d8ef8","#28b86e","#d4a020","#e87228","#e84040","#a855f7","#06b6d4","#f97316"]
            for i, (s, n) in enumerate(sorted(sint_map.items(), key=lambda x: -x[1])[:8]):
                pct = int(n / max_s * 100)
                col_s = colores_sint[i % len(colores_sint)]
                filas_sint += (
                    f'<div class="adm-bar-row">'
                    f'<div class="adm-bar-lbl"><span class="adm-bar-dot" style="background:{col_s};"></span>{s}</div>'
                    f'<div class="adm-bar-track"><div class="adm-bar-fill" style="background:{col_s};width:{pct}%;"></div></div>'
                    f'<div class="adm-bar-val">{n}</div>'
                    f'</div>'
                )
        else:
            filas_sint = '<p style="color:var(--txt3);font-size:.82rem;padding:8px 0;">Sin datos aún.</p>'
        st.markdown(
            f'<div class="adm-panel"><div class="adm-panel-title">Síntomas más consultados</div>{filas_sint}</div>',
            unsafe_allow_html=True)

    # ── Gráfico de tendencia (B) ──────────────────────────────────────────────
    _tendencia = obtener_tendencia_sintomas(dias=14)
    if _tendencia:
        # Agrupar por fecha (suma total de consultas por día, independiente del síntoma)
        _dias_total: dict[str, int] = {}
        _sint_dias: dict[str, dict[str, int]] = {}
        for _row in _tendencia:
            _f, _s, _n = _row["fecha"], _row["sintoma"], _row["count"]
            _dias_total[_f] = _dias_total.get(_f, 0) + _n
            _sint_dias.setdefault(_s, {})[_f] = _n

        _fechas_ord = sorted(_dias_total.keys())[-14:]  # últimos 14 días
        _total_por_dia = [_dias_total.get(_f, 0) for _f in _fechas_ord]

        # Top 5 síntomas para las barras apiladas
        _top_sint = sorted(sint_map.items(), key=lambda x: -x[1])[:5]
        _colores_t = ["#3d8ef8","#28b86e","#d4a020","#e87228","#e84040"]

        _fig = go.Figure()
        for (_sn, _), _col in zip(_top_sint, _colores_t):
            _vals = [_sint_dias.get(_sn, {}).get(_f, 0) for _f in _fechas_ord]
            _fig.add_trace(go.Bar(
                x=_fechas_ord, y=_vals, name=_sn,
                marker_color=_col, opacity=0.88,
            ))
        # Línea de total
        _fig.add_trace(go.Scatter(
            x=_fechas_ord, y=_total_por_dia, name="Total",
            mode="lines+markers",
            line=dict(color="#a0c8ff", width=2.5, dash="dot"),
            marker=dict(size=6, color="#a0c8ff"),
        ))
        _fig.update_layout(
            barmode="stack",
            title=dict(text="Tendencia de consultas (últimos 14 días)", font=dict(size=13, color="#a8c8e8")),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#7a95b8", size=11),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(gridcolor="rgba(255,255,255,.05)", tickfont=dict(size=9)),
            yaxis=dict(gridcolor="rgba(255,255,255,.07)", tickfont=dict(size=9)),
            height=280,
        )
        st.plotly_chart(_fig, use_container_width=True, config={"displayModeBar": False})

    # ── Feedback stats ─────────────────────────────────────────────────────────
    _fb_stats = obtener_stats_feedback()
    if _fb_stats:
        _fb_pos = _fb_stats.get("positivo", 0)
        _fb_neu = _fb_stats.get("neutral",  0)
        _fb_neg = _fb_stats.get("negativo", 0)
        _fb_tot = _fb_pos + _fb_neu + _fb_neg
        st.markdown(
            f'<div class="adm-panel" style="padding:14px 20px;">'
            f'<div class="adm-panel-title">Valoraciones de pacientes ({_fb_tot} total)</div>'
            f'<div style="display:flex;gap:18px;margin-top:8px;font-size:.85rem;">'
            f'<span>😊 Muy útil <strong style="color:#28b86e">{_fb_pos}</strong></span>'
            f'<span>😐 Útil <strong style="color:#d4a020">{_fb_neu}</strong></span>'
            f'<span>😞 No útil <strong style="color:#e84040">{_fb_neg}</strong></span>'
            f'</div></div>',
            unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # ── Tabla de consultas ────────────────────────────────────────────────────
    col_tbl_hdr, col_tbl_sel = st.columns([4, 1])
    with col_tbl_hdr:
        st.markdown(
            '<div class="adm-panel" style="padding:18px 20px 6px;"><div class="adm-panel-title">Últimas consultas registradas</div></div>',
            unsafe_allow_html=True)
    with col_tbl_sel:
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        _n_filas = st.selectbox("Mostrar", [15, 25, 50, 100], label_visibility="collapsed", key="adm_n_filas")
    consultas = obtener_consultas(limit=_n_filas)

    if consultas:
        st.markdown(
            '<div class="adm-table-hdr">'
            '<div class="adm-th">Fecha / Hora</div>'
            '<div class="adm-th">Síntoma</div>'
            '<div class="adm-th">Puntuación</div>'
            '<div class="adm-th">Gravedad</div>'
            '<div class="adm-th">Nivel</div>'
            '</div>',
            unsafe_allow_html=True)
        for i, c in enumerate(consultas):
            bc  = badge_cls(c["nivel"])
            nk  = badge_key(c["nivel"])
            bg  = "background:var(--raised);" if i % 2 == 0 else ""
            st.markdown(
                f'<div class="adm-table-row" style="{bg}">'
                f'<div class="adm-ts">{c["timestamp"]}</div>'
                f'<div class="adm-td">{c["sintoma"]}</div>'
                f'<div class="adm-td">{c["puntuacion"]} / {c["maximo"]}</div>'
                f'<div class="adm-td" style="font-weight:700;">{c["porcentaje"]}%</div>'
                f'<div class="adm-td"><span class="nx-badge {bc}">{nk}</span></div>'
                f'</div>',
                unsafe_allow_html=True)
    else:
        st.markdown('<p style="color:var(--txt3);font-size:.85em;padding:10px 20px 16px;">Sin consultas registradas aún.</p>', unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── Exportar PDF ──────────────────────────────────────────────────────────
    if consultas:
        col_pdf, col_sp = st.columns([3, 1])
        with col_sp:
            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Actualizar PDF", use_container_width=True, key="btn_adm_pdf_refresh"):
                st.session_state.pop("_pdf_admin", None)
                st.rerun()
        with col_pdf:
            if st.session_state.get("_pdf_admin") is None:
                with st.spinner(t("adm_spin")):
                    try:
                        st.session_state["_pdf_admin"] = generar_pdf_admin(
                            stats, obtener_consultas(limit=10000)
                        )
                    except Exception as _adm_e:
                        st.error(f"Error al generar PDF: {_adm_e}")
            if st.session_state.get("_pdf_admin"):
                st.download_button(
                    t("adm_export"),
                    data=st.session_state["_pdf_admin"],
                    file_name=f"nexacare_admin_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA: HOME
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pantalla == "home":

    # ── Animación de transición desde landing ─────────────────────────────────
    if st.session_state.get("_from_landing"):
        st.session_state["_from_landing"] = False
        st.markdown("""
        <div id="nx-enter" style="
            position:fixed;inset:0;z-index:99999;pointer-events:none;
            background:linear-gradient(135deg,#071426 0%,#0d1e38 100%);
            animation:nxEnterFade .65s cubic-bezier(.4,0,.2,1) .05s both;
        "></div>
        <style>
        @keyframes nxEnterFade {
            0%   { opacity:1; transform:scale(1);    }
            70%  { opacity:.3; transform:scale(1.02); }
            100% { opacity:0; transform:scale(1);    }
        }
        </style>
        """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    /* ── Contenedores home ── */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surf) !important;
        border: 1px solid var(--bdr) !important;
        border-radius: 16px !important;
        padding: 0 !important;
        overflow: hidden !important;
    }

    /* Hero banner home */
    .hm-hero {
      background: linear-gradient(135deg, #0d1e38 0%, #0f2244 50%, #0d1e38 100%);
      border: 1px solid var(--bdr);
      border-radius: 14px;
      padding: 14px 22px;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 20px;
      position: relative;
      overflow: hidden;
    }
    .hm-hero::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, var(--acc), rgba(40,184,110,.8), var(--acc), transparent);
    }
    .hm-hero::after {
      content: '';
      position: absolute;
      top: -60px; right: -60px;
      width: 200px; height: 200px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(61,142,248,.08), transparent 70%);
      pointer-events: none;
    }
    .hm-hero-icon {
      font-size: 2.8rem;
      line-height: 1;
      flex-shrink: 0;
      filter: drop-shadow(0 0 12px rgba(61,142,248,.4));
    }
    .hm-hero-body { flex: 1; }
    .hm-hero-title {
      font-size: 1.65rem;
      font-weight: 800;
      color: var(--txt);
      letter-spacing: -.5px;
      margin-bottom: 5px;
    }
    .hm-hero-sub { font-size: .9rem; color: var(--txt2); line-height: 1.5; }
    .hm-caps {
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex-shrink: 0;
    }
    .hm-cap {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(61,142,248,.07);
      border: 1px solid rgba(61,142,248,.16);
      border-radius: 10px;
      padding: 8px 14px;
      font-size: .8rem;
      color: var(--txt2);
      white-space: nowrap;
    }
    .hm-cap-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--acc);
      box-shadow: 0 0 8px var(--acc);
      flex-shrink: 0;
    }
    .hm-cap-dot.green { background: var(--green); box-shadow: 0 0 8px var(--green); }

    /* Card headers — datos paciente */
    .hm-card-hdr {
      background: linear-gradient(100deg, rgba(15,28,55,.95) 0%, rgba(20,38,72,.7) 100%);
      padding: 14px 20px 13px;
      border-bottom: 1px solid rgba(61,142,248,.14);
      border-radius: 12px 12px 0 0;
      display: flex;
      align-items: center;
      gap: 12px;
      position: relative;
      overflow: hidden;
    }
    .hm-card-hdr::after {
      content:''; position:absolute; bottom:0; left:0; right:0; height:1px;
      background: linear-gradient(90deg, var(--acc), rgba(40,184,110,.4), transparent);
    }
    .hm-card-hdr-icon {
      width: 38px; height: 38px;
      border-radius: 11px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.15rem;
      background: linear-gradient(135deg, rgba(61,142,248,.18), rgba(61,142,248,.06));
      border: 1px solid rgba(61,142,248,.28);
      flex-shrink: 0;
      box-shadow: 0 2px 10px rgba(61,142,248,.12);
    }
    .hm-card-hdr-title {
      font-size: .85rem;
      font-weight: 800;
      color: var(--txt);
      letter-spacing: -.01em;
    }
    .hm-card-hdr-sub {
      font-size: .68rem; color: var(--txt3); margin-top: 2px;
      display: flex; align-items: center; gap: 5px;
    }
    .hm-card-hdr-sub::before {
      content:''; display:inline-block; width:5px; height:5px;
      border-radius:50%; background:rgba(40,184,110,.6);
    }

    /* Form inside card */
    .hm-field-lbl {
      font-size: .64rem; font-weight: 700; color: var(--txt3);
      text-transform: uppercase; letter-spacing: .1em;
      margin-bottom: 3px; padding: 0 2px;
    }
    .hm-sep {
      height: 1px;
      background: linear-gradient(90deg, rgba(61,142,248,.2), transparent);
      margin: 14px 0 14px;
    }
    .hm-desc-lbl {
      font-size: .7rem; font-weight: 700; color: var(--acc);
      text-transform: uppercase; letter-spacing: .1em;
      display: flex; align-items: center; gap: 6px;
      margin-bottom: 6px;
    }

    /* Síntoma detectado */
    .hm-detect {
      background: rgba(61,142,248,.07);
      border: 1px solid rgba(61,142,248,.22);
      border-left: 3px solid var(--acc);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: .88rem;
      color: #a8c8ff;
      margin: 8px 0 4px;
    }

    /* Symptom buttons — tile style */
    [data-testid^="stButton-sym_"] > button {
      background: linear-gradient(135deg, #0f1e36 0%, #0c1a2e 100%) !important;
      border: 1px solid rgba(61,142,248,.16) !important;
      border-radius: 14px !important;
      min-height: 66px !important;
      font-size: .95rem !important;
      font-weight: 700 !important;
      color: var(--txt) !important;
      text-align: left !important;
      padding: 14px 42px 14px 16px !important;
      transition: all .22s cubic-bezier(.22,.68,0,1.2) !important;
      position: relative !important;
      overflow: hidden !important;
      letter-spacing: .01em !important;
    }
    /* Línea de acento inferior */
    [data-testid^="stButton-sym_"] > button::before {
      content: '';
      position: absolute;
      bottom: 0; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, transparent, rgba(61,142,248,.6), transparent);
      opacity: 0;
      transition: opacity .2s !important;
    }
    /* Flecha derecha */
    [data-testid^="stButton-sym_"] > button::after {
      content: '›';
      position: absolute;
      right: 14px; top: 50%;
      transform: translateY(-50%);
      font-size: 1.3rem;
      color: var(--txt3);
      transition: color .2s, transform .2s !important;
      font-weight: 400;
    }
    [data-testid^="stButton-sym_"] > button:hover {
      background: linear-gradient(135deg, #122040 0%, #0f1e38 100%) !important;
      border-color: rgba(61,142,248,.45) !important;
      transform: translateY(-3px) !important;
      box-shadow: 0 10px 28px rgba(0,0,0,.35), 0 0 0 1px rgba(61,142,248,.15) !important;
      color: #d0e8ff !important;
    }
    [data-testid^="stButton-sym_"] > button:hover::before { opacity: 1 !important; }
    [data-testid^="stButton-sym_"] > button:hover::after  {
      color: var(--acc) !important;
      transform: translateY(-50%) translateX(3px) !important;
    }

    /* Botón describir síntoma */
    [data-testid="stButton-🔍"] > button {
      background: var(--acc) !important;
      color: #fff !important;
      border: none !important;
      border-radius: 10px !important;
      font-size: 1.1em !important;
      box-shadow: 0 4px 16px rgba(61,142,248,.35) !important;
    }
    [data-testid="stButton-🔍"] > button:hover {
      background: #2d7be0 !important;
      transform: translateY(-1px) !important;
    }

    /* Sección síntomas header */
    .hm-sym-hdr {
      background: linear-gradient(90deg, rgba(19,31,48,1), rgba(14,24,44,.6));
      padding: 16px 22px 12px;
      border-bottom: 1px solid var(--bdr-s);
    }
    .hm-sym-title {
      font-size: .8rem; font-weight: 700; color: var(--txt);
      display: flex; align-items: center; gap: 9px; margin-bottom: 4px;
    }
    .hm-sym-icon {
      width: 30px; height: 30px; border-radius: 9px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1rem;
      background: rgba(61,142,248,.12); border: 1px solid rgba(61,142,248,.22);
    }
    .hm-sym-sub { font-size: .71rem; color: var(--txt3); padding-left: 39px; }
    .hm-sym-body { padding: 14px 16px; }

    /* ── Cajas simétricas: handled via JS below ── */

    /* Animaciones home */
    @keyframes hmUp {
      from { opacity:0; transform:translateY(18px); }
      to   { opacity:1; transform:translateY(0);    }
    }
    .hm-hero       { animation: hmUp .45s ease both .05s; }
    .hm-statsbar   { animation: hmUp .45s ease both .12s; }
    .hm-how        { animation: hmUp .45s ease both .20s; }

    /* Mejora tabs resultado */
    div[data-testid="stTabs"] > div:first-child {
      background: var(--surf) !important;
      border-radius: 12px 12px 0 0 !important;
      border: 1px solid var(--bdr) !important;
      border-bottom: none !important;
      padding: 4px 8px 0 !important;
    }
    div[data-testid="stTabs"] button[role="tab"] {
      border-radius: 8px 8px 0 0 !important;
      font-size: .77rem !important;
      font-weight: 700 !important;
      padding: 7px 12px !important;
      color: var(--txt3) !important;
      background: transparent !important;
      border: none !important;
      border-bottom: 2px solid transparent !important;
      transition: color .15s, border-color .15s, background .15s !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
      color: var(--acc) !important;
      border-bottom: 2px solid var(--acc) !important;
      background: rgba(61,142,248,.06) !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover:not([aria-selected="true"]) {
      color: var(--txt) !important;
      background: var(--hover) !important;
    }
    div[data-testid="stTabsContent"] {
      background: var(--surf) !important;
      border: 1px solid var(--bdr) !important;
      border-top: none !important;
      border-radius: 0 0 12px 12px !important;
      padding: 16px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Marca para JS que igualará las dos cajas
    st.markdown('<div id="hm-pair-start"></div>', unsafe_allow_html=True)

    col_izq, col_der = st.columns([1, 1], gap="large")

    with col_izq:
        with st.container(border=True):
            st.markdown(f"""
            <div class="hm-card-hdr">
              <div class="hm-card-hdr-icon">📋</div>
              <div>
                <div class="hm-card-hdr-title">{t('hm_datos_title')}</div>
                <div class="hm-card-hdr-sub">{t('hm_datos_sub')}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                edad_s = st.selectbox(t("hm_edad"), ["—","0–14","15–29","30–44","45–59","60–74","75+"], key="s_edad")
            with c2:
                sexo_s = st.selectbox(t("hm_sexo"), ["—", t("hm_sx_masc"), t("hm_sx_fem")], key="s_sexo")

            c3, c4 = st.columns(2)
            with c3:
                alt_v = st.text_input(t("hm_alt"), value=st.session_state.altura_cm, placeholder="Ej: 172", key="i_alt")
            with c4:
                pes_v = st.text_input(t("hm_pes"), value=st.session_state.peso_kg, placeholder="Ej: 70", key="i_pes")

            if edad_s != "—":           st.session_state.edad_grupo = edad_s + " años"
            if sexo_s != "—":           st.session_state.sexo       = sexo_s
            if alt_v.strip().isdigit():
                _alt = int(alt_v.strip())
                if 100 <= _alt <= 250:
                    st.session_state.altura_cm = alt_v.strip()
                elif alt_v.strip():
                    st.caption("⚠️ Altura debe estar entre 100 y 250 cm")
            if pes_v.strip().isdigit():
                _pes = int(pes_v.strip())
                if 20 <= _pes <= 300:
                    st.session_state.peso_kg = pes_v.strip()
                elif pes_v.strip():
                    st.caption("⚠️ Peso debe estar entre 20 y 300 kg")

            email_v = st.text_input(
                t("hm_email"),
                value=st.session_state.email_paciente,
                placeholder="tucorreo@ejemplo.com", key="i_email",
            )
            if email_v.strip() and re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$", email_v.strip()):
                st.session_state.email_paciente = email_v.strip()

            st.markdown('<div class="hm-sep"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="hm-desc-lbl">{t("hm_desc_lbl")}</div>', unsafe_allow_html=True)

            ct, cb = st.columns([6, 1], vertical_alignment="bottom")
            with ct:
                texto_v = st.text_input(
                    "Describe", value=st.session_state.texto_libre,
                    placeholder=t("hm_desc_ph"),
                    label_visibility="collapsed", key="i_texto",
                )
            with cb:
                if st.button("🔍", use_container_width=True, help="Analizar síntomas"):
                    if texto_v.strip():
                        st.session_state.texto_libre = texto_v
                        lbl_spin = t('hm_ia_spin') if tiene_ia_real() else t('hm_ana_spin')
                        with st.spinner(lbl_spin):
                            opciones = [s for s, _ in SINTOMAS]
                            sug, _ = clasificar_sintoma(texto_v, opciones)
                        st.session_state.sintoma_sugerido = sug if sug else None
                        if not sug:
                            st.markdown(f'<div class="nx-aviso">{t("hm_no_sym")}</div>', unsafe_allow_html=True)

            if st.session_state.sintoma_sugerido:
                sug = st.session_state.sintoma_sugerido
                badge = "🤖 IA" if tiene_ia_real() else "🔍 Reglas"
                st.markdown(
                    f'<div class="hm-detect"><strong style="color:#5baeff;">{badge}</strong> — Síntoma detectado: <strong>{sug}</strong></div>',
                    unsafe_allow_html=True
                )
                cok, cno = st.columns(2)
                if cok.button("✅ Confirmar y comenzar", use_container_width=True):
                    st.session_state.sintoma_sugerido = None
                    iniciar_triaje(sug)
                if cno.button("❌ Cambiar", use_container_width=True):
                    st.session_state.sintoma_sugerido = None
                    st.rerun()

    with col_der:
        with st.container(border=True):
            st.markdown(f"""
            <div class="hm-sym-hdr">
              <div class="hm-sym-title">
                <div class="hm-sym-icon">🩺</div>
                {t('hm_sym_title')}
              </div>
              <div class="hm-sym-sub">{t('hm_sym_sub')}</div>
            </div>
            <div class="hm-sym-body">
            """, unsafe_allow_html=True)

            for i in range(0, len(SINTOMAS), 2):
                cc1, cc2 = st.columns(2)
                n1, e1 = SINTOMAS[i]
                if cc1.button(f"{e1}  {n1}", use_container_width=True, key=f"sym_{i}"):
                    iniciar_triaje(n1)
                if i + 1 < len(SINTOMAS):
                    n2, e2 = SINTOMAS[i + 1]
                    if cc2.button(f"{e2}  {n2}", use_container_width=True, key=f"sym_{i+1}"):
                        iniciar_triaje(n2)

            st.markdown("</div>", unsafe_allow_html=True)

    # ── Igualar altura de las dos cajas via JS ───────────────────────────────
    components.html("""
    <script>
    function equalBoxes() {
      var marker = window.parent.document.getElementById('hm-pair-start');
      if (!marker) return;
      var el = marker;
      for (var i = 0; i < 6; i++) { el = el.parentElement; if (!el) return; }
      var block = el.querySelector('[data-testid="stHorizontalBlock"]');
      if (!block) return;
      var wrappers = block.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]');
      if (wrappers.length < 2) return;
      wrappers[0].style.minHeight = '';
      wrappers[1].style.minHeight = '';
      var h = Math.max(wrappers[0].offsetHeight, wrappers[1].offsetHeight);
      wrappers[0].style.minHeight = h + 'px';
      wrappers[1].style.minHeight = h + 'px';
    }
    setTimeout(equalBoxes, 80);
    setTimeout(equalBoxes, 300);
    setTimeout(equalBoxes, 700);

    // ── Animación D: cascade de botones de síntoma ───────────────────────────
    function cascadeSympBtns() {
      var btns = window.parent.document.querySelectorAll('[data-testid^="stButton-sym_"] button');
      if (!btns.length) return;
      btns.forEach(function(btn, i) {
        btn.style.opacity = '0';
        btn.style.transform = 'translateY(14px) scale(.97)';
        btn.style.transition = 'opacity .32s ease ' + (0.04 + i * 0.055) + 's, transform .32s cubic-bezier(.22,.68,0,1.2) ' + (0.04 + i * 0.055) + 's';
      });
      requestAnimationFrame(function() {
        btns.forEach(function(btn, i) {
          setTimeout(function() {
            btn.style.opacity = '1';
            btn.style.transform = 'translateY(0) scale(1)';
          }, 40 + i * 55);
        });
      });
    }
    setTimeout(cascadeSympBtns, 120);
    </script>
    """, height=0)

    # ── Acceso personal sanitario (centrado) ─────────────────────────────────
    st.markdown("""
    <style>
    .hm-admin-wrap {
      display: flex; justify-content: center; margin: 16px 0 4px;
    }
    .hm-admin-btn-wrap {
      display: flex; justify-content: center;
    }
    [data-testid="stButton-btn_admin"] > button {
      background: linear-gradient(135deg, rgba(10,20,40,.95), rgba(15,28,58,.9)) !important;
      border: 1px solid rgba(61,142,248,.25) !important;
      border-radius: 14px !important;
      color: var(--txt3) !important;
      font-size: .78rem !important;
      font-weight: 600 !important;
      padding: 10px 28px !important;
      letter-spacing: .03em !important;
      min-height: 0 !important;
      width: auto !important;
      transition: all .22s ease !important;
      box-shadow: 0 2px 16px rgba(0,0,0,.3) !important;
    }
    [data-testid="stButton-btn_admin"] > button:hover {
      border-color: rgba(61,142,248,.5) !important;
      color: var(--acc) !important;
      background: linear-gradient(135deg, rgba(15,30,60,.98), rgba(20,40,80,.95)) !important;
      box-shadow: 0 4px 24px rgba(61,142,248,.12), 0 0 0 1px rgba(61,142,248,.1) !important;
      transform: translateY(-1px) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    _, _col_adm, _ = st.columns([2, 1, 2])
    with _col_adm:
        if st.button("🔐  Área personal sanitario", key="btn_admin", use_container_width=True):
            ir("pin")

    # ── Banner informativo ────────────────────────────────────────────────────
    _stats_home  = obtener_stats()
    _total_pac   = _stats_home["total"]
    _pac_txt     = f"👥 {_total_pac:,} pacientes atendidos".replace(",", ".")
    ia_dot = "green" if tiene_ia_real() else ""
    ia_lbl = t('hm_ia_on') if tiene_ia_real() else t('hm_ia_off')
    st.markdown(f"""
    <div class="hm-hero" style="margin-top:6px;">
      <div class="hm-hero-icon">⚕️</div>
      <div class="hm-hero-body">
        <div class="hm-hero-title">{t('hm_hero_title')}</div>
        <div class="hm-hero-sub">{t('hm_hero_sub')}</div>
      </div>
      <div class="hm-caps">
        <div class="hm-cap"><span class="hm-cap-dot {ia_dot}"></span>{ia_lbl}</div>
        <div class="hm-cap"><span class="hm-cap-dot green"></span>{t('hm_cap_time')}</div>
        <div class="hm-cap"><span class="hm-cap-dot green"></span>{_pac_txt}</div>
        <div class="hm-cap"><span class="hm-cap-dot"></span>{t('hm_cap_pdf')}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA: TRIAJE ACTIVO
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pantalla == "triaje":
    sintoma   = st.session_state.sintoma
    preguntas = obtener_preguntas(sintoma)
    idx       = st.session_state.pregunta_idx
    total_pts = pts_max(sintoma)

    if idx >= len(preguntas):
        ir("resultado")

    else:
        progreso = int(idx / len(preguntas) * 100)

        st.markdown(f"""
        <div style="background:var(--surf);border:1px solid var(--bdr);border-radius:13px;
                    padding:12px 20px;margin-bottom:14px;display:flex;align-items:center;gap:12px;">
          <div style="font-size:1.6em;">🩺</div>
          <div>
            <div style="font-size:0.95em;font-weight:700;color:var(--txt);">{sintoma}</div>
            <div style="font-size:0.74em;color:var(--txt3);">{t("tx_eval")} · {len(preguntas)} preguntas</div>
          </div>
          <div style="margin-left:auto;">
            <div style="font-size:0.7em;color:var(--txt3);text-align:right;">{t("tx_pregunta")}</div>
            <div style="font-size:1.1em;font-weight:700;color:var(--acc);text-align:right;">{idx+1} / {len(preguntas)}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="nx-prog">
          <span class="nx-prog-lbl">{t("tx_prog")}</span>
          <div class="nx-bar"><div class="nx-bar-f" style="width:{progreso}%;"></div></div>
          <span class="nx-prog-pct">{progreso}%</span>
        </div>""", unsafe_allow_html=True)

        if idx > 0 and total_pts > 0:
            riesgo = int(st.session_state.puntuacion / total_pts * 100)
            rc = "#28b86e" if riesgo < 25 else "#d4a020" if riesgo < 45 else "#e87228" if riesgo < 70 else "#e84040"
            st.markdown(f"""
            <div class="nx-risk">
              <span class="nx-risk-lbl">{t("tx_riesgo")}</span>
              <div class="nx-risk-bar"><div class="nx-risk-f" style="background:{rc};width:{riesgo}%;"></div></div>
              <span class="nx-risk-pct" style="color:{rc};">{riesgo}%</span>
            </div>""", unsafe_allow_html=True)

        texto, _ = preguntas[idx]
        st.markdown(f"""
        <div class="tx-wrap">
          <div class="tx-hdr">
            <div class="tx-num">{idx+1}</div>
            <div>
              <div class="tx-tag">{t("tx_tag")}</div>
              <div style="font-size:.8rem;color:var(--txt2);margin-top:1px;">{sintoma}</div>
            </div>
            <div class="tx-counter">{idx+1} de {len(preguntas)}</div>
          </div>
          <div class="tx-body">
            <div class="tx-txt">{texto}</div>
          </div>
        </div>""", unsafe_allow_html=True)

        b1, b2, b3 = st.columns([5, 5, 2])
        if b1.button(t("btn_si"), use_container_width=True, key=f"si_{idx}"):
            st.session_state.puntuacion += preguntas[idx][1]
            st.session_state.respuestas.append((texto, True))
            st.session_state.pregunta_idx += 1
            st.rerun()
        if b2.button(t("btn_no"), use_container_width=True, key=f"no_{idx}"):
            st.session_state.respuestas.append((texto, False))
            st.session_state.pregunta_idx += 1
            st.rerun()
        if b3.button(t("btn_salir"), use_container_width=True, key="salir_triaje"):
            reset_triaje()
            ir("home")


# ══════════════════════════════════════════════════════════════════════════════
# PANTALLA: RESULTADO
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.pantalla == "resultado":
    sintoma   = st.session_state.sintoma
    total_pts = pts_max(sintoma)
    pts       = st.session_state.puntuacion
    porcentaje = int(pts / total_pts * 100) if total_pts > 0 else 0
    r          = calcular_nivel_triaje(pts, total_pts)
    e          = ncolor(r["color"])

    if not st.session_state.consulta_guardada:
        resp_si = [preg for preg, ok in st.session_state.respuestas if ok]

        edad_ext = st.session_state.get("edad_grupo")
        alt = st.session_state.get("altura_cm", "")
        pes = st.session_state.get("peso_kg", "")
        if alt and pes:
            try:
                imc_val = round(int(pes) / (int(alt) / 100) ** 2, 1)
                dato = f"Altura: {alt} cm · Peso: {pes} kg · IMC: {imc_val}"
                edad_ext = f"{edad_ext or 'No especificada'} · {dato}"
            except (ValueError, ZeroDivisionError):
                pass

        lbl_inf = t('rx_spin_inf') if tiene_ia_real() else t('rx_spin_calc')
        with st.spinner(lbl_inf):
            informe = generar_informe_triaje(
                sintoma, resp_si, r["nivel"], porcentaje,
                edad_grupo=edad_ext, sexo=st.session_state.get("sexo"),
            )
        st.session_state.informe_ai = informe

        token = uuid.uuid4().hex
        st.session_state.token_informe = token

        try:
            guardar_consulta(
                sintoma, st.session_state.respuestas, pts, total_pts,
                r["nivel"], informe_ai=informe,
                email=st.session_state.get("email_paciente") or None,
                token_informe=token,
            )
            st.session_state.consulta_guardada = True
        except Exception as _dbe:
            st.warning(f"⚠️ No se pudo guardar la consulta: {_dbe}")

    informe = st.session_state.informe_ai

    # ── Generar PDF (una sola vez) ────────────────────────────────────────────
    if "_pdf" not in st.session_state or (
        st.session_state.get("_pdf") is None and not st.session_state.get("_pdf_err")
    ):
        datos_pac = {
            "edad":   st.session_state.get("edad_grupo"),
            "sexo":   st.session_state.get("sexo"),
            "altura": st.session_state.get("altura_cm") or None,
            "peso":   st.session_state.get("peso_kg") or None,
        }
        try:
            _pb = generar_pdf(
                sintoma=sintoma, respuestas=st.session_state.respuestas,
                puntuacion=pts, puntuacion_maxima=total_pts,
                porcentaje=porcentaje, nivel=r["nivel"], emoji=r["emoji"],
                recomendacion=r["recomendacion"], que_hacer=r["que_hacer"],
                informe_ai=informe,
                centros=st.session_state.get("centros"),
                datos_paciente=datos_pac,
            )
            st.session_state["_pdf"] = _pb
            st.session_state["_pdf_err"] = None
        except Exception as _pe:
            st.session_state["_pdf"] = None
            st.session_state["_pdf_err"] = str(_pe)

    _pdf = st.session_state.get("_pdf")

    # ── Enviar email (una sola vez) ───────────────────────────────────────────
    _email = st.session_state.get("email_paciente", "").strip()
    if _pdf and _email and not st.session_state.get("webhook_enviado"):
        try:
            _ok, _err = enviar_informe(
                destinatario=_email, sintoma=sintoma,
                nivel=r["nivel"], emoji=r["emoji"], porcentaje=porcentaje,
                recomendacion=r["recomendacion"], que_hacer=r["que_hacer"],
                pdf_bytes=_pdf, informe_ai=informe,
            )
        except Exception as ex:
            _ok, _err = False, str(ex)
        st.session_state["webhook_enviado"] = True
        st.session_state["_email_ok"]  = _ok
        st.session_state["_email_err_mail"] = _err if not _ok else ""

    # ══ LAYOUT ═══════════════════════════════════════════════════════════════
    # — Hero banner (full width) —
    _hero_cls = "nx-hero-rojo" if r["color"] == "red" else ""
    _ring_spd  = "1.5s" if r["color"] == "red" else "2.2s"
    st.markdown(f"""
    <div class="{_hero_cls}" style="
      background:{e['bg']};border:2px solid {e['bdr']};border-radius:20px;
      padding:22px 26px 18px;margin-bottom:10px;
      animation:popIn .4s cubic-bezier(.22,.68,0,1.2) both;
      position:relative;overflow:hidden;">
      <!-- Shimmer line superior -->
      <div style="position:absolute;top:0;left:0;right:0;height:2px;
        background:linear-gradient(90deg,transparent,{e['txt']},rgba(255,255,255,.4),{e['txt']},transparent);
        background-size:200% 100%;animation:nxShimmer 3s linear infinite;"></div>
      <!-- Glow decorativo fondo -->
      <div style="position:absolute;top:-60px;right:-60px;width:220px;height:220px;
        border-radius:50%;background:radial-gradient(circle,rgba({e['rgb']},.12),transparent 65%);
        pointer-events:none;"></div>
      <!-- Fila superior: anillo+emoji + nivel + porcentaje -->
      <div style="display:flex;align-items:center;gap:24px;margin-bottom:18px;">
        <!-- Anillo de urgencia -->
        <div style="position:relative;flex-shrink:0;">
          <div style="
            width:96px;height:96px;border-radius:50%;
            background:radial-gradient(circle,rgba({e['rgb']},.14),rgba({e['rgb']},.03));
            border:2px solid rgba({e['rgb']},.55);
            display:flex;align-items:center;justify-content:center;
            animation:nxRingPulse1 {_ring_spd} ease-out infinite;
            position:relative;">
            <div style="position:absolute;inset:-8px;border-radius:50%;
              border:1px solid rgba({e['rgb']},.2);
              animation:nxRingPulse2 {_ring_spd} ease-out .4s infinite;"></div>
            <div style="font-size:3rem;line-height:1;
              animation:floatEmoji 4s ease-in-out 1s infinite;">{r['emoji']}</div>
          </div>
        </div>
        <div style="flex:1;">
          <div style="font-size:1.75rem;font-weight:900;letter-spacing:3px;
            color:{e['txt']};text-transform:uppercase;line-height:1;
            margin-bottom:6px;">{r['nivel']}</div>
          <div style="font-size:.8rem;color:{e['txt']};opacity:.6;">
            {t('rx_urg')} · NexaCare · {sintoma}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;">
          <div id="nx-pct-num" style="font-size:3rem;font-weight:900;color:{e['txt']};line-height:1;">0%</div>
          <div style="font-size:.68rem;color:{e['txt']};opacity:.55;margin-top:3px;">{t('rx_idx_grav')}</div>
        </div>
      </div>
      <!-- Barra de gravedad -->
      <div style="height:8px;border-radius:99px;
        background:linear-gradient(90deg,#28b86e 0%,#d4a020 33%,#e87228 66%,#e84040 100%);
        position:relative;box-shadow:0 2px 8px rgba(0,0,0,.35);margin-bottom:6px;">
        <div style="position:absolute;top:-5px;left:{min(max(porcentaje,2),98)}%;
          transform:translateX(-50%);width:18px;height:18px;border-radius:50%;
          background:#fff;border:3px solid {e['txt']};
          box-shadow:0 0 12px {e['txt']};"></div>
      </div>
      <div style="display:flex;justify-content:space-between;
        font-size:.62rem;color:{e['txt']};opacity:.45;">
        <span>{t('rx_leve')}</span><span>{t('rx_mod')}</span><span>{t('rx_urg2')}</span><span>{t('rx_emerg')}</span>
      </div>
    </div>""", unsafe_allow_html=True)

    # — Animación contador porcentaje —
    components.html(f"""<script>
    (function(){{
      var el = window.parent.document.getElementById('nx-pct-num');
      if(!el) return;
      var target = {porcentaje}, start = 0, dur = 1400, t0 = null;
      function step(ts){{
        if(!t0) t0 = ts;
        var p = Math.min((ts-t0)/dur, 1);
        var ease = 1 - Math.pow(1-p, 3);
        el.textContent = Math.round(ease*target) + '%';
        if(p < 1) requestAnimationFrame(step);
      }}
      requestAnimationFrame(step);
    }})();
    </script>""", height=0)

    # — Fila de stats (3 columnas) —
    st.markdown(f"""
    <style>
    .rx-stat-new {{
      background:linear-gradient(160deg,#0f1e36,#0c1a2e);
      border:1px solid rgba(61,142,248,.14);border-radius:14px;
      padding:16px 12px 14px;text-align:center;
      position:relative;overflow:hidden;
      transition:transform .18s,box-shadow .18s;
      animation:pageIn .4s ease both;
    }}
    .rx-stat-new:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.3);}}
    .rx-stat-new::before{{
      content:'';position:absolute;top:0;left:0;right:0;height:2px;
      background:linear-gradient(90deg,transparent,rgba(61,142,248,.5),transparent);
    }}
    .rx-stat-new.urg::before{{
      background:linear-gradient(90deg,transparent,rgba({e['rgb']},.8),transparent);
    }}
    .rx-stat-new.urg{{border-color:rgba({e['rgb']},.2);}}
    .rx-stat-icon{{font-size:1.4rem;display:block;margin-bottom:7px;}}
    </style>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px;">
      <div class="rx-stat-new" style="animation-delay:.1s;">
        <span class="rx-stat-icon">🩺</span>
        <div class="rx-stat-l">{t('rx_sintoma')}</div>
        <div class="rx-stat-v" style="font-size:.83rem;line-height:1.3;">{sintoma}</div>
      </div>
      <div class="rx-stat-new" style="animation-delay:.2s;">
        <span class="rx-stat-icon">📊</span>
        <div class="rx-stat-l">{t('rx_punt')}</div>
        <div class="rx-stat-v">{pts}/{total_pts}</div>
      </div>
      <div class="rx-stat-new urg" style="animation-delay:.3s;">
        <span class="rx-stat-icon">⚠️</span>
        <div class="rx-stat-l">{t('rx_grav')}</div>
        <div class="rx-stat-v" style="color:{e['txt']};font-size:1.2rem;">{porcentaje}%</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # — Botones de acción (2 columnas) —
    sc4, sc5 = st.columns([1, 1], gap="small")
    if _pdf:
        sc4.download_button(
            t('btn_pdf'), data=_pdf,
            file_name=f"NexaCare_{sintoma.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf", use_container_width=True, key="pdf_top",
        )
    elif st.session_state.get("_pdf_err"):
        sc4.markdown(
            '<div style="background:rgba(232,64,64,.08);border:1px solid rgba(232,64,64,.25);'
            'border-radius:10px;padding:10px;font-size:.75rem;color:#e84040;text-align:center;">'
            '⚠️ Error al generar PDF</div>', unsafe_allow_html=True,
        )
    if sc5.button(t('btn_nueva'), use_container_width=True, key="btn_nueva_top"):
        for _k in ("_pdf", "_email_ok", "_email_err_mail", "_pdf_err", "webhook_enviado"):
            st.session_state.pop(_k, None)
        reset_triaje()
        ir("home")

    # — Notificación email —
    if st.session_state.get("_email_ok"):
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;
          background:rgba(40,184,110,.1);border:1px solid rgba(40,184,110,.28);
          border-radius:10px;padding:10px 16px;margin-bottom:10px;">
          <span style="font-size:1.1em;">✅</span>
          <div style="font-size:.84em;font-weight:700;color:#28b86e;">{t('rx_email_ok')}</div>
        </div>""", unsafe_allow_html=True)
    elif _email and st.session_state.get("webhook_enviado") and not st.session_state.get("_email_ok"):
        _err_msg = st.session_state.get("_email_err_mail", "")
        _es_cred = any(w in _err_msg.lower() for w in ["credencial", "gmail_user", "gmail_pass", "no configurad"])
        if not _es_cred:
            _ecol1, _ecol2 = st.columns([3, 1])
            _ecol1.markdown(
                f'<div style="background:rgba(232,64,64,.08);border:1px solid rgba(232,64,64,.22);'
                f'border-radius:10px;padding:10px 16px;font-size:.82em;color:#e84040;">'
                f'⚠️ No se pudo enviar el email a <strong>{_email}</strong>.</div>',
                unsafe_allow_html=True,
            )
            if _ecol2.button("🔄 Reintentar", use_container_width=True, key="btn_email_retry"):
                st.session_state["webhook_enviado"] = False
                st.rerun()

    # — Columnas principales —
    col_izq, col_der = st.columns([1, 1], gap="large")

    with col_izq:
        # Informe IA
        if informe:
            badge_ia = "🤖 IA activa" if tiene_ia_real() else "📊 Demo"
            _badge_style = ("background:rgba(40,184,110,.1);border:1px solid rgba(40,184,110,.25);color:#28b86e;"
                            if tiene_ia_real() else
                            "background:rgba(61,142,248,.07);border:1px solid rgba(61,142,248,.18);color:var(--acc);")
            st.markdown(f"""
            <div class="nx-ai" style="animation:pageIn .5s ease both .1s;">
              <div class="nx-ai-hdr">
                <span class="nx-ai-dot"></span>
                <span class="nx-ai-t">{t('rx_ai_title')}</span>
                <span style="margin-left:auto;font-size:.68rem;{_badge_style}
                  border-radius:99px;padding:2px 9px;font-weight:700;">{badge_ia}</span>
              </div>
              <div style="font-size:.87rem;line-height:1.78;color:#a8c8e8;margin-top:4px;">{informe}</div>
            </div>""", unsafe_allow_html=True)

        # Recomendación
        st.markdown(f"""
        <div style="background:var(--surf);border:1px solid var(--bdr);
          border-left:3px solid {e['txt']};border-radius:0 12px 12px 0;
          padding:13px 16px;margin-bottom:12px;">
          <div style="font-size:.66rem;font-weight:700;color:{e['txt']};
            text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px;">
            {t('rx_reco')}
          </div>
          <div style="font-size:.88rem;color:var(--txt2);line-height:1.65;">{r['recomendacion']}</div>
        </div>""", unsafe_allow_html=True)

        # Respuestas en expander
        with st.expander(t('rx_resp_exp'), expanded=False):
            for preg, si in st.session_state.respuestas:
                _preg_esc = _html_mod.escape(preg)
                if si:
                    st.markdown(f'<div class="nx-resp-si">✅ {_preg_esc}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="nx-resp-no">❌ {_preg_esc}</div>', unsafe_allow_html=True)

    with col_der:
        tab1, tab2, tab3 = st.tabs([t('rx_tab1'), t('rx_tab2'), t('rx_tab3')])

        with tab1:
            _pasos = r["que_hacer"]
            _steps_html = ""
            for i, paso in enumerate(_pasos, 1):
                _is_last = (i == len(_pasos))
                _steps_html += f"""
                <div style="display:flex;gap:16px;align-items:flex-start;
                  padding:14px 6px 14px 4px;position:relative;
                  animation:slideInRight .4s ease both;animation-delay:{i*0.09}s;">
                  <!-- Número + línea vertical -->
                  <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;gap:0;">
                    <div style="
                      width:38px;height:38px;border-radius:50%;flex-shrink:0;
                      display:flex;align-items:center;justify-content:center;
                      font-size:.92rem;font-weight:900;color:#fff;
                      background:linear-gradient(135deg,rgba({e['rgb']},.9),rgba({e['rgb']},.65));
                      box-shadow:0 0 0 4px rgba({e['rgb']},.12),0 4px 14px rgba({e['rgb']},.3);
                      position:relative;z-index:1;">{i}</div>
                    {'<div style="width:2px;flex:1;min-height:18px;margin-top:4px;background:linear-gradient(180deg,rgba(' + e["rgb"] + ',.45),rgba(' + e["rgb"] + ',.05));border-radius:2px;"></div>' if not _is_last else ''}
                  </div>
                  <!-- Texto -->
                  <div style="flex:1;padding-top:8px;padding-bottom:{0 if _is_last else 4}px;">
                    <div style="font-size:.88rem;color:var(--txt2);line-height:1.6;">{paso}</div>
                  </div>
                </div>"""
            st.markdown(f'<div style="padding:4px 0;">{_steps_html}</div>', unsafe_allow_html=True)

        with tab2:
            st.markdown(f'<div class="nx-sec" style="margin-top:8px;">{t("rx_centros")}</div>', unsafe_allow_html=True)

            # ── Geolocalización del navegador (si disponible) ─────────────────
            if _GEOLOC_OK and st.session_state.get("pedir_geoloc"):
                _geo = _get_geolocation()
                if _geo and "coords" in _geo:
                    _glat = _geo["coords"].get("latitude")
                    _glon = _geo["coords"].get("longitude")
                    if _glat is not None and _glon is not None:
                        st.session_state.coords_busq = (float(_glat), float(_glon))
                        st.session_state.ubicacion_busq = "📍 Mi ubicación"
                        with st.spinner(t("rx_buscar_spin")):
                            st.session_state.centros = buscar_centros(
                                float(_glat), float(_glon), nivel_color=r["color"]
                            )
                        st.session_state.pedir_geoloc = False
                        st.rerun()

            # ── Barra de búsqueda ─────────────────────────────────────────────
            _geo_cols = [4, 1, 1] if _GEOLOC_OK else [4, 1]
            _cols = st.columns(_geo_cols)
            with _cols[0]:
                ub = st.text_input(
                    "Ubicación", value=st.session_state.ubicacion_busq,
                    placeholder=t("rx_ub_ph"), label_visibility="collapsed", key="i_ub",
                )
            with _cols[1]:
                if st.button(t("btn_buscar"), use_container_width=True, key="btn_buscar"):
                    if ub.strip():
                        st.session_state.ubicacion_busq = ub
                        with st.spinner(t("rx_buscar_spin")):
                            coords = geocodificar(ub)
                            if coords:
                                st.session_state.coords_busq = coords
                                centros = buscar_centros(coords[0], coords[1], nivel_color=r["color"])
                                st.session_state.centros = centros
                            else:
                                st.session_state.centros = None
                                st.session_state.coords_busq = None
            if _GEOLOC_OK:
                with _cols[2]:
                    if st.button(t("btn_mi_ubicac"), use_container_width=True,
                                 key="btn_geoloc", help="Usar mi ubicación GPS"):
                        st.session_state.pedir_geoloc = True
                        st.rerun()

            if st.session_state.centros is None and st.session_state.ubicacion_busq:
                st.markdown(f'<div class="nx-aviso">{t("rx_no_loc")}</div>', unsafe_allow_html=True)
            elif isinstance(st.session_state.centros, list) and st.session_state.centros:
                urgente = r["color"] in ("red", "orange")
                _coords = st.session_state.get("coords_busq")

                # — Mapa interactivo folium —
                if _coords:
                    _flat, _flon = _coords
                    _fmap = folium.Map(
                        location=[_flat, _flon],
                        zoom_start=13,
                        tiles="CartoDB dark_matter",
                        attr="&copy; CartoDB",
                    )
                    # Marcador de usuario (CircleMarker — siempre funciona sin iconos externos)
                    folium.CircleMarker(
                        location=[_flat, _flon],
                        radius=10,
                        color="#3d8ef8",
                        fill=True,
                        fill_color="#3d8ef8",
                        fill_opacity=0.9,
                        popup=folium.Popup("📍 <b>Tu ubicación</b>", max_width=160),
                        tooltip="Tu ubicación",
                    ).add_to(_fmap)
                    # Anillo exterior para el marcador de usuario
                    folium.CircleMarker(
                        location=[_flat, _flon],
                        radius=16,
                        color="#3d8ef8",
                        fill=False,
                        weight=2,
                        opacity=0.5,
                    ).add_to(_fmap)

                    # Marcadores de centros
                    _color_map = {"red": "red", "orange": "orange", "yellow": "beige", "green": "green"}
                    _pin_color = _color_map.get(r["color"], "green")
                    for _c in st.session_state.centros:
                        _clat = _c.get("lat")
                        _clon = _c.get("lon")
                        if _clat is None or _clon is None:
                            continue
                        _ic = "plus-sign" if _c.get("es_hospital") else "home"
                        _popup_html = (
                            f"<b style='font-size:13px'>{_html_mod.escape(_c['nombre'])}</b><br>"
                            f"<span style='color:#888'>{_html_mod.escape(_c['tipo'])}</span><br>"
                            f"📍 {formatear_distancia(_c['distancia_m'])}"
                            + ("<br><span style='color:red'>🚨 URGENCIAS</span>" if _c.get("urgencias") else "")
                            + f"<br><a href='{_c.get('maps_url','#')}' target='_blank'>🗺️ Cómo llegar</a>"
                        )
                        folium.Marker(
                            location=[_clat, _clon],
                            popup=folium.Popup(_popup_html, max_width=240),
                            tooltip=_c["nombre"],
                            icon=folium.Icon(color=_pin_color, icon=_ic, prefix="glyphicon"),
                        ).add_to(_fmap)
                        # Línea punteada desde usuario hasta centro
                        folium.PolyLine(
                            locations=[[_flat, _flon], [_clat, _clon]],
                            color="#3d8ef8", weight=1.5, opacity=0.4, dash_array="5 8",
                        ).add_to(_fmap)
                    st_folium(_fmap, use_container_width=True, height=290, returned_objects=[])

                # — Tarjetas de centros —
                for i, c in enumerate(st.session_state.centros):
                    urg = '<div class="nx-urg-badge">🚨 URGENCIAS</div>' if c.get("urgencias") else ""
                    rec = '<div class="nx-rec-badge">⭐ RECOMENDADO</div>' if urgente and c.get("es_hospital") else ""
                    _nombre_esc = _html_mod.escape(c['nombre'])
                    _tipo_esc   = _html_mod.escape(c['tipo'])
                    _maps_url   = c.get("maps_url", "#")
                    st.markdown(f"""
                    <a href="{_maps_url}" target="_blank" style="text-decoration:none;">
                    <div class="nx-hosp-card" style="animation-delay:{i*0.07}s;cursor:pointer;">
                      <div class="nx-hosp-ico-wrap">{c['icono']}</div>
                      <div class="nx-hosp-info">
                        <div class="nx-hosp-name">{_nombre_esc}</div>
                        <div class="nx-hosp-type">{_tipo_esc}</div>
                      </div>
                      <div class="nx-hosp-badges">
                        <div class="nx-dist-badge">📍 {formatear_distancia(c['distancia_m'])}</div>
                        {urg}{rec}
                      </div>
                    </div></a>""", unsafe_allow_html=True)
            elif isinstance(st.session_state.centros, list) and not st.session_state.centros:
                _coords_sc = st.session_state.get("coords_busq")
                if _coords_sc:
                    _fmap_sc = folium.Map(
                        location=list(_coords_sc),
                        zoom_start=13,
                        tiles="CartoDB dark_matter",
                        attr="&copy; CartoDB",
                    )
                    folium.CircleMarker(
                        location=list(_coords_sc),
                        radius=10, color="#3d8ef8", fill=True,
                        fill_color="#3d8ef8", fill_opacity=0.9,
                        popup=folium.Popup("📍 <b>Tu ubicación</b>", max_width=160),
                        tooltip="Tu ubicación",
                    ).add_to(_fmap_sc)
                    folium.CircleMarker(
                        location=list(_coords_sc),
                        radius=16, color="#3d8ef8", fill=False, weight=2, opacity=0.5,
                    ).add_to(_fmap_sc)
                    st_folium(_fmap_sc, use_container_width=True, height=290, returned_objects=[])
                st.markdown(f'<div class="nx-reco" style="color:var(--txt3);">{t("rx_sin_centros")}</div>', unsafe_allow_html=True)

            st.markdown(f'<div class="nx-sec" style="margin-top:14px;">{t("rx_telef")}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="nx-emerg">'
                f'<div class="nx-emerg-row"><span class="nx-emerg-n">{t("rx_emerg1")}</span><a href="tel:112" class="nx-emerg-num" style="color:#ff6060;background:rgba(232,64,64,.12);border:1px solid rgba(232,64,64,.2);">112</a></div>'
                f'<div class="nx-emerg-row"><span class="nx-emerg-n">{t("rx_emerg2")}</span><a href="tel:061" class="nx-emerg-num" style="color:#ff9444;background:rgba(232,114,40,.12);border:1px solid rgba(232,114,40,.2);">061</a></div>'
                f'<div class="nx-emerg-row"><span class="nx-emerg-n">{t("rx_emerg3")}</span><a href="tel:091" class="nx-emerg-num" style="color:#60a8ff;background:rgba(61,142,248,.12);border:1px solid rgba(61,142,248,.2);">091</a></div>'
                f'<div class="nx-emerg-row"><span class="nx-emerg-n">{t("rx_emerg4")}</span><a href="tel:080" class="nx-emerg-num" style="color:#e8c040;background:rgba(212,160,32,.12);border:1px solid rgba(212,160,32,.2);">080</a></div>'
                f'<div class="nx-emerg-row"><span class="nx-emerg-n">{t("rx_emerg5")}</span><a href="tel:024" class="nx-emerg-num" style="color:#44d48a;background:rgba(40,184,110,.12);border:1px solid rgba(40,184,110,.2);">024</a></div>'
                f'</div>',
                unsafe_allow_html=True)

        with tab3:
            _ia_lbl  = t('rx_ia_activa') if tiene_ia_real() else t('rx_ia_demo')
            _ia_pill = ('background:rgba(40,184,110,.12);border:1px solid rgba(40,184,110,.28);color:#28b86e;'
                        if tiene_ia_real() else
                        'background:rgba(61,142,248,.08);border:1px solid rgba(61,142,248,.2);color:#3d8ef8;')

            # Procesar chip pendiente del rerun anterior
            if st.session_state.get("chat_chip_pending"):
                chip_q = st.session_state.chat_chip_pending
                st.session_state.chat_chip_pending = None
                if len(st.session_state.chat_qa) >= 20:
                    st.session_state.chat_qa.pop(0)
                r_si = [p for p, ok in st.session_state.respuestas if ok]
                with st.spinner(t('rx_spin_ia') if tiene_ia_real() else t('rx_spin_demo')):
                    resp = responder_pregunta(chip_q, sintoma, r["nivel"], r_si)
                st.session_state.chat_qa.append((chip_q, resp or "Lo siento, inténtalo de nuevo."))
                st.rerun()

            # ── Header ──────────────────────────────────────────────────────────
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
              padding:13px 16px;margin-top:6px;
              background:linear-gradient(135deg,rgba(61,142,248,.08),rgba(61,142,248,.02));
              border:1px solid rgba(61,142,248,.2);border-radius:16px 16px 0 0;
              border-bottom:1px solid rgba(61,142,248,.1);">
              <div>
                <div style="font-size:.84rem;font-weight:700;color:#e8f0ff;margin-bottom:3px;letter-spacing:.01em;">
                  💬 {t('rx_chat_lbl')}
                </div>
                <div style="font-size:.71rem;color:#4a6080;">
                  {t('rx_responde')} <strong style="color:#3d8ef8;">{sintoma}</strong>
                </div>
              </div>
              <div style="font-size:.72rem;padding:5px 13px;border-radius:99px;font-weight:700;{_ia_pill};flex-shrink:0;">
                {_ia_lbl}
              </div>
            </div>""", unsafe_allow_html=True)

            # ── Área de mensajes ─────────────────────────────────────────────────
            if not st.session_state.chat_qa:
                st.markdown(f"""
                <div style="border-left:1px solid rgba(61,142,248,.2);
                  border-right:1px solid rgba(61,142,248,.2);
                  background:linear-gradient(160deg,#0c1a2e 0%,#071628 100%);
                  min-height:210px;padding:32px 16px;
                  display:flex;flex-direction:column;align-items:center;
                  justify-content:center;gap:12px;text-align:center;">
                  <div style="width:60px;height:60px;border-radius:18px;
                    background:linear-gradient(135deg,rgba(61,142,248,.14),rgba(61,142,248,.04));
                    border:1px solid rgba(61,142,248,.22);
                    display:flex;align-items:center;justify-content:center;font-size:2rem;">🤖</div>
                  <div style="font-size:.87rem;font-weight:700;color:#c0d4f0;">{t('rx_chat_empty')}</div>
                  <div style="font-size:.74rem;color:#334a66;">Pulsa una pregunta rápida o escribe la tuya abajo</div>
                </div>""", unsafe_allow_html=True)

                # ── Chips funcionales ────────────────────────────────────────────
                cc1, cc2, cc3 = st.columns(3)
                for col, chip_key, chip_tr in [
                    (cc1, "chip1_btn", "rx_chip1"),
                    (cc2, "chip2_btn", "rx_chip2"),
                    (cc3, "chip3_btn", "rx_chip3"),
                ]:
                    with col:
                        if st.button(t(chip_tr), key=chip_key, use_container_width=True):
                            st.session_state.chat_chip_pending = t(chip_tr)
                            st.rerun()
            else:
                msgs_html = ""
                for q, a in st.session_state.chat_qa:
                    _q = _html_mod.escape(q)
                    _a = _html_mod.escape(a)
                    msgs_html += f"""
                    <div class="nx-msg u" style="margin-bottom:12px;">
                      <div class="nx-av usr">👤</div>
                      <div class="nx-bubble usr">{_q}</div>
                    </div>
                    <div class="nx-msg" style="margin-bottom:14px;">
                      <div class="nx-av bot">🤖</div>
                      <div class="nx-bubble bot">{_a}</div>
                    </div>"""
                st.markdown(
                    f'<div style="border-left:1px solid rgba(61,142,248,.2);'
                    f'border-right:1px solid rgba(61,142,248,.2);'
                    f'background:linear-gradient(160deg,#0c1a2e 0%,#071628 100%);'
                    f'min-height:200px;max-height:340px;overflow-y:auto;padding:14px 12px;'
                    f'scrollbar-width:thin;scrollbar-color:rgba(61,142,248,.15) transparent;">'
                    f'{msgs_html}</div>',
                    unsafe_allow_html=True,
                )

            # ── Input ────────────────────────────────────────────────────────────
            st.markdown(
                '<div style="border:1px solid rgba(61,142,248,.2);border-top:none;'
                'border-radius:0 0 16px 16px;padding:10px 12px;'
                'background:rgba(10,20,38,1);">',
                unsafe_allow_html=True,
            )
            cq, cs = st.columns([6, 1])
            with cq:
                preg_usr = st.text_input(
                    "chat_input", placeholder=t('rx_chat_hint'),
                    label_visibility="collapsed", key="chat_in",
                )
            with cs:
                if st.button("➤", use_container_width=True, key="chat_send"):
                    if preg_usr.strip():
                        if len(st.session_state.chat_qa) >= 20:
                            st.session_state.chat_qa.pop(0)
                        r_si = [p for p, ok in st.session_state.respuestas if ok]
                        lbl = t('rx_spin_ia') if tiene_ia_real() else t('rx_spin_demo')
                        with st.spinner(lbl):
                            resp = responder_pregunta(preg_usr, sintoma, r["nivel"], r_si)
                        st.session_state.chat_qa.append((preg_usr, resp or "Lo siento, inténtalo de nuevo."))
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="nx-aviso" style="margin-top:12px;">{t("rx_aviso")}</div>', unsafe_allow_html=True)