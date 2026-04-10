import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import calendar
from datetime import datetime, date, timedelta
import numpy as np
import requests

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Analizador CRZ MT5",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=JetBrains+Mono:wght@300;400&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    font-weight: 300;
    letter-spacing: 0.01em;
}

.stApp { background-color: #080a0e; }



div[data-testid="metric-container"] {
    background: #0f1117;
    border: 1.5px solid #1e2a3a;
    border-radius: 0px;
    padding: 16px 18px;
    border-left: 4px solid #2dd4bf;
    box-shadow: 2px 2px 0px #0a0c10;
}
div[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 10px !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 500;
}
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 22px !important;
    font-weight: 500 !important;
    color: #e2e8f0 !important;
    letter-spacing: -0.02em;
}
div[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    font-weight: 400 !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 0.5px solid #161b27;
    gap: 0; padding: 0;
}
.stTabs [data-baseweb="tab"] {
    color: #2d3748;
    font-size: 11px;
    font-weight: 400;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 10px 18px;
    border-radius: 0;
}
.stTabs [aria-selected="true"] {
    background: transparent !important;
    color: #94a3b8 !important;
    border-bottom: 1px solid #94a3b8 !important;
}

[data-testid="stFileUploader"] {
    background: #0c0e14;
    border: 0.5px dashed #161b27;
    border-radius: 6px;
    padding: 20px;
}

[data-testid="stDataFrame"] { border-radius: 4px; overflow: hidden; }
[data-testid="stDataFrame"] * { font-size: 12px !important; font-family: 'JetBrains Mono', monospace !important; font-weight: 300 !important; }

hr { border-color: #161b27; border-width: 0.5px; }

.main-header {
    font-family: 'Inter', sans-serif;
    font-size: 20px; font-weight: 300;
    color: #94a3b8; letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.main-sub { color: #64748b; font-size: 12px; margin-bottom: 28px; font-weight: 300; letter-spacing: 0.06em; }

.section-label {
    font-size: 9px; font-weight: 600; letter-spacing: 0.15em;
    text-transform: uppercase; color: #64748b; margin: 24px 0 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e2a3a;
}

.alumno-bar {
    background: #0f1117;
    border: 1.5px solid #1e2a3a;
    border-radius: 0px;
    padding: 14px 18px;
    margin-bottom: 20px;
    border-left: 4px solid #2dd4bf;
    box-shadow: 2px 2px 0px #0a0c10;
}
.alumno-name { font-size: 15px; font-weight: 500; color: #e2e8f0; letter-spacing: 0.02em; }
.alumno-meta { font-size: 11px; color: #64748b; margin-top: 4px; font-weight: 300; letter-spacing: 0.02em; }
</style>
""", unsafe_allow_html=True)

# ── Parser ────────────────────────────────────────────────────────────────────
def parse_mt5(file) -> dict:
    df_raw = pd.read_excel(file, header=None, dtype=str)
    rows = df_raw.values.tolist()

    meta = {"alumno": "", "cuenta": "", "empresa": "", "fecha": ""}
    header_row = -1

    for i, r in enumerate(rows[:25]):
        c0 = str(r[0] or "")
        if "ombre" in c0:   meta["alumno"]  = str(r[3] or r[1] or "").strip()
        if "uenta" in c0:   meta["cuenta"]  = str(r[3] or r[1] or "").strip()
        if "mpresa" in c0:  meta["empresa"] = str(r[3] or r[1] or "").strip()
        if "echa" in c0 and str(r[3] or "").strip()[:4].isdigit():
            meta["fecha"] = str(r[3] or "").strip()
        if "osici" in str(r[1] or "") and "echa" in str(r[0] or ""):
            header_row = i

    if header_row < 0:
        raise ValueError("No se encontró la sección de Posiciones en el archivo")

    trades = []
    for r in rows[header_row + 1:]:
        c0 = str(r[0] or "")
        if any(x in c0 for x in ["rdene", "ransacc", "Balance:", "Resultado"]):
            break
        try:
            pos_id  = float(str(r[1]).replace(",", "."))
            profit  = float(str(r[12]).replace(",", "."))
        except (ValueError, TypeError, IndexError):
            continue

        def n(v):
            try: return float(str(v).replace(",", "."))
            except: return 0.0

        trades.append({
            "open":    str(r[0]),
            "pos_id":  int(pos_id),
            "symbol":  str(r[2]).strip(),
            "type":    str(r[3]).strip().lower(),
            "volume":  str(r[4]),
            "p_in":    n(r[5]),
            "sl":      n(r[6]),
            "tp":      n(r[7]),
            "close":   str(r[8]),
            "p_out":   n(r[9]),
            "comm":    n(r[10]),
            "swap":    n(r[11]),
            "profit":  profit,
            "pnl_net": profit + n(r[10]) + n(r[11]),
        })

    if not trades:
        raise ValueError("No se encontraron operaciones cerradas en el archivo")

    df = pd.DataFrame(trades)
    df["open_dt"]  = pd.to_datetime(df["open"],  format="%Y.%m.%d %H:%M:%S", errors="coerce")
    df["close_dt"] = pd.to_datetime(df["close"], format="%Y.%m.%d %H:%M:%S", errors="coerce")
    df["close_date"] = df["close_dt"].dt.date
    df["open_date"]  = df["open_dt"].dt.date
    df["month"]  = df["close_dt"].dt.to_period("M").astype(str)
    df["hour"]   = df["close_dt"].dt.hour
    df["win"]    = df["profit"] > 0

    # Summary stats from MT5
    stats = {"pnl_net":0,"gross_win":0,"gross_loss":0,"pfactor":0,
             "expected":0,"total_ops":len(df),"max_dd":"—","best":0,
             "worst":0,"avg_win":0,"avg_loss":0,"balance":0}
    for r in rows:
        c0 = str(r[0] or "")
        def g(idx):
            try: return float(str(r[idx]).replace(",",".").replace(" ",""))
            except: return 0.0
        if "Beneficio Neto" in c0:
            stats["pnl_net"]=g(3); stats["gross_win"]=g(7); stats["gross_loss"]=g(11)
        if "Factor de Beneficio" in c0: stats["pfactor"]=g(3); stats["expected"]=g(7)
        if "Total de operaciones" in c0: stats["total_ops"]=int(g(3)) or len(df)
        if "absoluta" in c0: stats["max_dd"]=str(r[3] or "—")
        if "transacci" in c0.lower() and "rentable" in c0.lower() and "Promedio" not in c0:
            stats["best"]=g(7); stats["worst"]=g(11)
        if "Promedio" in c0 and "transacci" in c0.lower():
            stats["avg_win"]=g(7); stats["avg_loss"]=g(11)
        if c0.startswith("Balance:"):
            try: stats["balance"]=float(str(r[3]).replace(" ","").replace(",","."))
            except: pass

    if not stats["pnl_net"]: stats["pnl_net"] = df["pnl_net"].sum()
    if not stats["gross_win"]: stats["gross_win"] = df[df.profit>0]["profit"].sum()
    if not stats["gross_loss"]: stats["gross_loss"] = df[df.profit<0]["profit"].sum()
    if not stats["pfactor"] and stats["gross_loss"]:
        stats["pfactor"] = stats["gross_win"] / abs(stats["gross_loss"])
    if not stats["balance"]: stats["balance"] = stats["pnl_net"]
    if not stats["best"] and len(df): stats["best"] = df["profit"].max()
    if not stats["worst"] and len(df): stats["worst"] = df["profit"].min()
    if not stats["avg_win"] and df["win"].any():
        stats["avg_win"] = df[df["win"]]["profit"].mean()
    if not stats["avg_loss"] and (~df["win"]).any():
        stats["avg_loss"] = df[~df["win"]]["profit"].mean()

    stats["balance_ini"] = stats["balance"] - stats["pnl_net"]

    return {"meta": meta, "df": df, "stats": stats}

# ── Plotly theme ──────────────────────────────────────────────────────────────
LAYOUT = dict(
    paper_bgcolor="#111318", plot_bgcolor="#111318",
    font=dict(color="#94a3b8", family="DM Mono, monospace", size=11),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor="#1e2330", linecolor="#1e2330", showgrid=True),
    yaxis=dict(gridcolor="#1e2330", linecolor="#1e2330", showgrid=True),
    hoverlabel=dict(bgcolor="#1e293b", bordercolor="#252b38", font_color="#f1f5f9"),
)
GREEN = "#22c55e"; RED = "#ef4444"; BLUE = "#3b82f6"; MUTED = "#475569"

# ── Main ──────────────────────────────────────────────────────────────────────
# Dark/Light mode toggle
col_logo, col_toggle = st.columns([8,1])
with col_toggle:
    dark_mode = st.checkbox("🌙", value=True, help="Modo oscuro / claro")

if not dark_mode:
    st.markdown("""<style>
    .stApp { background-color: #f8fafc !important; }
    div[data-testid="metric-container"] {
        background: #ffffff !important;
        border-color: #e2e8f0 !important;
        border-left-color: #0f172a !important;
        box-shadow: 2px 2px 0px #e2e8f0 !important;
    }
    div[data-testid="metric-container"] label { color: #94a3b8 !important; }
    div[data-testid="stMetricValue"] { color: #0f172a !important; }
    .alumno-bar {
        background: #ffffff !important;
        border-color: #e2e8f0 !important;
        border-left-color: #0f172a !important;
        box-shadow: 2px 2px 0px #e2e8f0 !important;
    }
    .alumno-name { color: #0f172a !important; }
    .section-label { color: #94a3b8 !important; border-bottom-color: #e2e8f0 !important; }
    .stTabs [data-baseweb="tab-list"] { border-color: #e2e8f0 !important; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8 !important; }
    .stTabs [aria-selected="true"] { color: #0f172a !important; border-color: #0f172a !important; }
    </style>""", unsafe_allow_html=True)
LOGO_B64 = "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAQDAwQDAwQEAwQFBAQFBgoHBgYGBg0JCggKDw0QEA8NDw4RExgUERIXEg4PFRwVFxkZGxsbEBQdHx0aHxgaGxr/2wBDAQQFBQYFBgwHBwwaEQ8RGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhoaGhr/wgARCAUABQADASIAAhEBAxEB/8QAHAABAAMBAQEBAQAAAAAAAAAAAAYHCAUEAwIB/8QAGwEBAAIDAQEAAAAAAAAAAAAAAAMEAgUGAQf/2gAMAwEAAhADEAAAAc/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOjYOVSrX9/mNsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB0V+56t2y1xVc09qfMsHU+AQ9AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA6K/c9W7Za4oPcGZNN5jg6PxCDqQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHRX7nq3bLXFB7gAzFp3MMHR+QQdSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA6K/c9W7Za4oPcAAGYNP5gg6TyiDqAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHRX7nq3bLXFB7gAAAy/qDL0HSecQdQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA6K/c9W7Za4oPcAAAAP5l/UGX4Ok84g6gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB0V+56t2y1xQe4AAAAAfzL2ocuwdL8RB04AAAE/gWgY/Nz1OP7/IehAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAejz9Bhf3bLvzkPcAAAAAAPzl7UOXoOl+Ig6cAAADQcmjUlufO65p7U9cxbqnH6/MHVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOjzul7HpcXfm4AAAAAAH4y9qHL0HS/IQdOAAABoWSRyR3PnYZV65p7U9cwdFTj9fmDqgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHS5vT9i0sLvzgAAAAAAD8Zd1Dl2DpvwIOmAAAA0PIo9IbnzoMoAK5p7U9cwdFTj+/wAg6oAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB1eV1fYtKC784AAAAAHD8z7j5/T3D55d1Dl2DpvyIOmAAAA0TII/ILnzoMoADhVThsOjXH9/lXtA8sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOtyev7FpIXfnAAAA53mXR5NZ19Fvp1Avwg6TUX3+P2u/PPll3UWXYOl/Ig6YAAADRfe4PeufOhWr2Z1XBvlX6z9/gj3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB/f4AAAAOzxuz7DpAXfnIA8730eOuqzi3diVv50HTBjaA1J9fn9L3zT45d1Fl2Dpv4IOlAAAA0Z3eH3LvzlSN3UhHs4KK3ZgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOiv3PVwaqrtpL3EI9sAAA7XF7fsOjhd+cvl4c/x7Oyqv56v1gY3QAANS/T8fu98z+GXtQ5dg6cIOlAAAA0d2+J27vzlR94UdHs4OK3ZgAAAdvjWd05NRTj+/yPbgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOjzrhypS3tlvg4FSd2UnW7AI9yAAA7fE7nsGjRd+dR/O2iM71+tCHfgAAAan/X5/V75n58vagy/B04QdKAAABo/tcbs3fnCjrxo2PaQgVuzAAAAtG2Kote1w1c09qeucL9OP7/IOqAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXJTdyyaixBa4qA0pdVK1e0CPcAAAO7wu77BowXfnUezvofPFbrQi34AAA/pqf8Av8/t75n5sv6fzBX6gIekAAAA0h2eP2LvzhRl50VHtYWK3ZAAAAWna1U2ta4YJNZXNPanrmDoqcf3+QdUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAuambmk1Fhi1xUApW6aWq9oEe4AAAd7g9/2DRQu/Oo5nnQ2ea3WhFvwAAH6/P6eam/pe+aeTMOncxV+oCHpAAAANJdfk9a784UTe1Ex7WGCt2QAAAFqWrVdqWuGCTWAVzT2p65g6KnH9/kHVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALope6ZNPYAtcXX1L3RS9XtAj3AAACQR+Q+waIF351G89aEz3W64It8AAA/f4+jzUovfNPFmPTeZK/UhD0YAAAGlOry+pd+bqIveh49vDhW7EAAAC1bUqy07XChJrQAK5p7U9XwdJUwg6gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABdNLXVJp5+LXF15TNy01V7UI9uAAAkMekftfQwu/O4znzQWfa3XBFvgAAH1+X2eajF75p4My6azLX6kIejAAAA0t0+Z07vzdQ98UNHt4eK3YgAAAWvaVXWjb4UM9aAPB56oJwq3ZhHuAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAF1UrdcmnnwtcXXVN3HTlXtQj24AACRxySe19Ci787jGfdAZ/rdeEW9AAAff4fdjqIXvmvPzNpjM9fqQh6MAAADS/S53Ru/N1C31Qke3iIrdiAAABbNoVfaFvhQz1o8HnqgnCrdmEe4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXZSd2yaaeC1xlc05cVO1e2CPbAAAJLGpN7W0GLvzyK0Bf1A1uvCLegAAPR5/Sx1AL3zXm5o0vmiv1QQ9EAAABpnoeD33fmyhL7oOPcxIVuwAAAAtqz6xs63wg8GWvUE4Vbswj3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACwq9e19Uf2nrgt8NXFPXDT1fqwj2wAACTxiT+1tBC788ilA37QVbsAi3gAAD1eX1sdPC9815madK5qr9UEPRAAAAab93h9135soK/aBj3MUFbsAAAALcs2s57a4ZQThQ9CEe4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWRW72vb9QdXlexBjdAAASiLynKtoAXPnkSoO+6ErdgEW8AAAezx+1hpwXvm3KzXpPNlfqgh6IAAADTnt8fsu/NVA39n+PdRYVuwAAAAs6HcX8ZUwxuAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJTFpV7Vv8AF357EaEvqha3YBFvAAAHu8PuYabF75tyM26SzbX6sIehAAAA077PJ67vzVn/AEBn2LdxgV+vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASuKSzKrfoufPYfQ180NW7AIt4AAA9/g6CPTIvfN+Pm7SGb6/VhD0IAAAGn/V5fVd+as+6Cz5Fu4yK/XgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJbEpblVvwXPnsOoe96IrdiEW7AAAdDn9H2PTAu/N+LnDR2ca/WBD0AAAAGofR8Pve+aM96Ez3DvY0K/XAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJfEJflUvoXPn0Mom9aKrdiEW7AAAdLm9L2PS4u/N+JnHRucq/WBD0AAAAGo/t8fte+aM9aFzzDvY4K/XAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJhD5jlUvgXPn0Kou86MrdkEW6AAAdPmdT2LSou/OOFnPRedK/WBD0AAAAGpPr8/pe+aM8aHzvDvY8K/XAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJPGHsWqP7T1wW+DhNG3lRsHThFugAAHV5XW9i0mLvzjg500Tnat1oRb8AAADU37/Piu/Nf5nf2cKt2gR7YAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABZFbva94Uf3uDlXDDYAAAOvyOx7DpEXfnMezvojO9frQh34AAAGmKEcKTUBHtwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHZ43a9h0eLvzmO540Nnmt1oRb8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB2uL2/YdHC785jmedC56rdcEW+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAO3a2evrC2Zb/Z+XCTVxrPeg8+VuuCLfAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJJGyPU37p64LnBf0ZVAIznzQWfa3XBFvgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFkVu9r6o/tPXBb4b+jKpF8/X/QFbrwi3oAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACyK3e19Uf2nrRtcRwqD7vCr9cGGxAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAevyHgPQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB7DxrBlBSzQ3RM0NOfEzS0HHynE2h58QAAAAHe+5GklEaSURpJRGklEaSURpJf4RtIPAc4AAAAAA75wElEaSURpJRGklEaSURpJRGklEaSURpJRGklEaSURpJRGkl/hGwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH2uopm1tEdcrue/cAAAAPD7hVVQ6zGA/xtPPRWIAANnTGHTEAAAAAAA8UYmgpKttbDA/w3PSpQT2eMAAbXxRtclAAAAAAAAAAAAHx+3xMDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAATSWaXI5KwAAAAAAAAAqrM27osYpSCPgGzpjDpiAAAAAAAAAAcDL2wPiYGWxU4A2vija5KAAAAAAAAAAAAPj9vOYIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAu3j6nP7+gAAP5XhYnzy3XRsfg5EGsPvkgbSk+BvYbzZOuIs9+f0AAR3Gl852PyDZ0xh0xAAPP+ckQE3qwUN6sFDerBX9N8/XA3ZNwMp2eW68/oAAPjkTYMdMRPT5hs7GI3qwUN6sFDerBQ3qwUN6sFDerBQ3qwUN6sFDerBV8GhwAAM+SzLR+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJJHNeE19oAAI3GsskzrwAAAAAJtprF/qN6qmtY/uf+fSQABs6Yw6YgAGPoDPoCAAAAASPU2NvebwRSVgAGbqR2li0AAAAAAAAEqJHq7ye8AAQ3tY3OX5AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAs3WUBnwAAr6VYuPB5wAAAAAAA+k8r8AAAbOmMOmIABj6Az6AgAAAAAFia7wFuE7gAP5h7cWSitQAAAAAAD6nu2PHbHAAHw+2ZSLQQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEljV5mi/6AA4hQFNfb4gAAAAAAAAAAAGzpjDpiAAY+gM+gIAAAAAA1tknVJawAGZdNZsKTAAAAAAA0fEtOH9AAK6Itm76/IAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAavyhtokoAFIXflAq8AAAAAAAAAAAAGzpjDpiAAY+gM+gIAAAAAA13krcp1AAMw6eyIV2AAAAABOuFsk6PoAAeE5GOOxFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD97ywnvQ/QAGJ9sYSOaAAAAAAAAAAAADZ0xh0xAAMfQGfQEAAAAAHbJ1qridsAA+eF9XY+AAAAAHq8+oiTzQAAPnlKV0MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAereeBt6H3AAwfvDEBHwAAAAAAAAAAAAbOmMOmIABj6A2VBTnugOe6A57ofo5qQ9wgS7bRM+6hkH6AABByjqp/f4AAAABZpK9D/P6AACpJNj8838AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABuPDmvCwwAMi66z+UAAAAAAAAAAAAADZ0xh0xAAAAAAAAAAByD9456EKAAAAB0js7F5MlAAHG6OQjhcIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGg8+Tw2GABEJeMALErsAAAAAAAAAAAA2dMYdMQAAAAAAAAAimby8sz8L+AAAAAH11pFbwAAH8/tHERp8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH6/I25I83aRAAIfjffFIGbwAAAAAAADsnGAABs6Yw6YgAHL+OWICblYaG5WGhuVhobl7WA9aFkAA8GMNvQEx8+nzAAAAFwxjXp6AACMEeyb7eaAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAenauIbLNaPz+gACgKB37VRlV1uSAAAAAHS0eRK/vaMhV7vXKhWoANnTGHTEAAx9AZ9AQAAB2uKN19TKmqj+gAzxQ++MckNAAA7vM2AdzsgAPmePHMirQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0feGBdUlogAA5tI6AGHeFvyImMWmuEUEvL7lDNLy8yhcGgvscjrgA+P2GVKr3hiM5YNnTGHTEAAx9AZ9AQAAABqDL/QN3o/IABE5YME+bSGbwB/f5fBLLbAABnbQdfGR2txkhrcZIa3GSGtxkhrcZIa3GSGtxkhrcZIa3GSF10oAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPv8AAaltrAd4mi3w+4AAAAAAAAA8XHyudSuQA2dMYdMQADH0Bn0BAAAAALA13gTRJewAPxknXPDMOOnzCRbZxhtMAAAAAAAAAAAAApPNmk82AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEr0Zkgb+/uObrLbeP2AAAAABwaiLypKkuGezxgABs6Yw6YgAGPoDPoCAAAAAPv8Bs+YYu2QekAFT5Y3/l0h208WbTAAAAAAAAAAAAAKTzZpPNgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB6Z7XIv6VZXGw+jisbZ8+LhryP5jF3QOGj9fkAAAALU6VMi5lMi5lMjtcUAAAAAAFiV2LmUyLmUyLm8FUDp2nTIuZTIuZTIuZTIuZTIuZTIuZTIuZTIuZTIuZTIuZTIuZTIuZTIuZTInkDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABY1c9jKpeaouzNztiO9SGVO0as8vEi3nMEW9AAAuCV8j6WuK6f4qX74W5jVt1e/3HOT9fmv1gAAACzq50nLpOdQuhIDnrqpFfrAAAAOtetHaPn5fgq05vsdqxfgWQworwaTz1Fu/CMNoAAB9NC571DNznEQOOZVbfVA8kjvl+nzg6gHoACewKyc6FhPbSs/MW5yK9mWNmCRfUedI9nxxHugAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEjjkj9r6GzNpnM03O88QdUAAABenh93hs8dTJ9K3YSDQtX2LZ43OfN+3xrdgDMAAfssSw/tWVjkPBc+Z9HeT51+FjVzDvw8sgAAdrR+cNH2OTzfxuzxoOmff4PJdK192fpZ42jhW7MAAD66hy9qGfmKJh+ofwwzC09BsblNCLfAAALJrayc9dZGbtI5uz17+pjFu7tp66s/2OVi4rdgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkcckftfQ2ZtM5mm53niDqgAAAL0mUN+FrhZt+81SfG7clK3fnl7xBX6wAABNoToHPVSesu/HJuf/EuijyzOM56epTzOEiDqQAAO1o/OGj7HJ5v43Z40HTHrsz2KWxyxM9zc1HhX7AAAD66hy9qGfmKZi3Zh8e46/n8DC2CQAABZNbWTnrrf+Xgz5PzGlP1nW/mNb1ZYNfQdUGGwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASOOfb2PUeZvrzs9Z8xHtwAAAL08NU/mXSeERbu45Hn/3y6Ln/AC+3xi3gPQAJNoDMnol0v75JFtwZ3H3qH9cui5Yi3oAAHa0flv3yabSP8zek12lOJQHhxlmEPIugDyUAAD66hy105NTpD+ZwSavR7OA90d+3xg6YPJAAFk1t6va2h83dPmZVU3hDG7p/O/482et8gj3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH//xAAyEAAABAQDBQkBAQEBAQEAAAADBAUGAAECMBAgNRQVNDZgBxMWFzEyM0BwERIhoCKw/9oACAEBAAEFAv8AxXEiYp4dQa3dlPx0mSFPjpqaEmAQvIO0R6fjZImKeHTEwJMAxO8Z+MkyQp8dNTQkwDIc4v8AGCRMU8OmJgSYBlN8V+LkyQp8dNTQkwDMb4r8WJExTw6YmBJgGc1xP4qTJCnx01NCTALBniPxQkTFPDpiYEmAWTHz/iZMkKfHTU0JMAtGPn/EiRMU8OmJgSYBbH+b8RJkhT46amhJgFwf5vxAkTFPDpiYEmAXRvm/DyZIU+OmpoSYBeG+W1uOZpHnL+fgZImKeHTEwJMAvT9BfltN7R15B2j8CCDmKImpoSYBfn6C/Jab+jwvIO0ROX8/ACPG/Qn6C/JaQNHwXkHaPwAhxv0KvaJ77SBpGK8g7RE5fzr4hx30KvaJ77SDpGReQdo6+T+O+hX7a/faQtIyr6DtETl/OvE7j/oV+yr3WkLScy8g7R14m8f9Cv2Ve60h6Tnc4JKkXrpN1C6eViqfKir/AHRAnx1e60iaVlPq5VPkoOQybj167TNRtnVIsQpUHQOYic51TB+GBPjn62kTSsTqmWIUqDnMGYnOdU+vEvUbJs6ASoUHUKLAglQtWAXxQL8c/W0i6Vg4lkwTHrrqEq6+StSzmDQJShQddVUCjCD15A/jgX4p20bSsHZqnX6TqWUYcMvQoOuUoMGRTVeYP2QL8VtG0vB16p1mTJCnx1pNCTUW0k6niIJQFSoOoMODRwc7XYo9kDfFbR9LwdeqWiScKeDnL+dTkiYp4dMTAkwB2aZaSNTwUDEyhI4omD9Vqn2wN8NtI0vB16paZ3yLyDtHUxMkKfHTU0JMAh26ZaSNUwXNJt0+kD/DbSNMwdWqWmd74XkHaInL+dSNCUtlwdum2kfVMFzSbcvSB/gtpOmYOnVbTO92C8g7R1I0ODwd2m2kbVMF3SbcvSDHD20nTcHTqtpneuK8g7RE5fzqJocFg7tNtI2q4Luk2pYmeHtpWm4OnVrTN9ci8g7R1E0OBwd2nWkbVcF3SbUvXA1w1tL03B0avaZuZeQdoicv51A0OAwd2nWkXVcF7SLVPrga4W2l6dg6NXtM3OvIO0dQNHgMHdp9pE1XBe0i1T7sDfCW0zT8HPq9pm+mdeQdoicv5080dPwd3AWkPVsF/SLVHvwOcJbTdPwc+r2md6WHMkg00dOtHTsHfwFpD1bBwaRaD9+B3g7adwGDn1e0zfbnOHAiICmpiqY/TrR07B38DaQtWwcGkWg/kwPcFbT+Awc2r2md7Mxw4ERAU1MVTH6eaOm4O/grSDq+Dh0i0F8uB/gbafwODm1e0zfZlOHAiICmpiqY/T7S03B38HaQNXwcOkWgflwP8DbIcFg5dXtM348hw4ERAU1MVTH6gaWm4O/hLSBrGDi0i0B82ChwFsjwWDl1e0zfixOHAiICmpiqY/ULS0zB4cJab+sYOPSLRf58FDgLZLg8HJq9pm/FgcOBEQFNTFUx+om6s0Eo9cHhwtpv6xg5NHtFuIwUdPtkuDwcer2md8MHDgREBTUxVMfqRBXtnj1h4cLab2sYOTSLRbicFLTrZPhMHHq9pnfAcOBEQFNTFUx+pkFe2eHhwtpvaxg5NHtFeJwU9OtlOEwcWr2m2cCIkFNTFUx+qBTwoxW03dYwcuj2inFYKenWynC4OLV7X9n/ADrRuaxg5dItFOLwVNNtleFwcOr9ftzWMHNpFonxeCrptsrw2Dg1fr9uaxg5tItEuMwVdNtluHwcGr9ftvWMHNpFolxmCtplsvw+C/q/X7b1jBz6RaI8bgr6ZbA+DBf1br9tavg59ItEONwV9Ltg/Dgvat1+2tXwdGkWiHHYLGl2wviwXtW6/bOr4OnSbSfx2CzpdsL48F3Vuv2zq+Dp0m0ncfgs6VbD9mC7q3X7Y1bB06VaTuPwWtKt0ezBc1br9BMhlVL1wdWlWk3UMFvSrdPtg4cCIgHTO2GvwBBXtnj1h16VaTNRwW9Jt0+hw4ERAU1MVTH/AAJBXtnh1f8AUq0l6jguaTbNnAiJdTUxVMf8EqUxRE60lajguaTbUlMVTG/EEnUsF3SfxxJ1PBe0j8cSNTwXtI/HEjVMF7SPxsgjGlCE1vliE8F/SPxkilGVCae2SxWJS/ksXBpH4wjVEpG6ZU005XBpH4ygr2zx65XBpH40gr2zx65HFpH42gr2zx64uLSPxxBXtnj1wclUqUn8dQV7Z4NnQiQCmpiqY/48IYFGo/8AB+AVHNVFWYsGYA7ODtUB9mocS7OCMeXKdFXZwRnAvZrTA3Z0oBwaaSwUgQKsKq0CiqA4e4FSNwKkbgVI3AqRuBUjcCpG4FSNwKkbgVI3AqRuBUjcCpG4FSJoijTAhA0FeDRFEYPcCpG4FSNwKkbgVI3AqRuBUjcCpG4FSNwKkbgVI3AqRuBUjcCpG4FSNwKkbgVI3AqRuBUjcCpG4FSNwKkbgVI3AqRuBUjcCpG4FOXSIBYY0Im9n501BBlJJKAggwKLJgmXOUn2CmGoU2SpJ8TpnTPO1OXb4xQuYgw00czBzs4K1wfY6qSgQKsGqw29B+yL8XRwQVY1aL2fijwQTCiYFfVW6QWJLbLOpWdqcu/TPJZNSoV+z2dMGSoxMXM29B+yL8XRqG2za4IjN4miB/TcLLLqcHCQ6ePkanLv1VRGKLALgaxlDrytvQfsi/F0Y12dWpwAAGWC+qtoRZcLK6QYRjWLU5d+sKFQMG62nNJqyNvQfsjT/gPRbQaW1x6Waq6aJDOJKLwI90UOPHyNFL6RaoAc6QYgMWgWVhZRwFomfJ1EDeDU5dy1DhUz2kGNpBjaQY2kGNpBjaQY2gGKRKKrQoVA4bpb9SGdxbo4VKFtIMbSDG0gxtIMbSDG0gxtIMbSDG0gxtIMbSDG0gxtIMbSDG0gxtIMbSDG0g2Hu5v9dFs9s72GpplTLOqvNNTIUH8pGoMnzJyrKAbHK1J75VCUJT4T1CJT/ssrsePcxOf9ng1OXcr05mz0i10wAtqJWCj9VS8Jz/IGZgjBmA8y2lBrCeOBWWG+oyGx3k8zxc26gJz/ALPolESRFo+UKhES+ZXXCiKCtu88r3EVznkSpEcZNcDxdjy/1lanLuV6czW0pbOIwrfchZdCzdoSV3Jr6bSbc1kzTTKinK414NCJGTAhsbopoockhNzOZ1BItBs4MfHulzApUVru+hWic5Uydjw2rM1OXcr05muFDYxEw31oNcIZXKQ3ii/SQUUZcPEyYJAtlU1EFKJq6qMsHeimUj7zVczpcdCGVGGrMC36ap0VKDuPqKfmanLuV6czXWcqzTFjL6wsFdiVfoESQyiaQ0cJFJZRhqC4TmcNa6b6LaCXuxGyqagElklJQFVDn2Gpy7lenM12U/8AM0c3t6XlfYHdOK/RRUJW025Silcz0c28Bei0AhvNXzP1Z2s79lqcu5XpzNeYoveN3L2j0fxWvsls7PTmezm2ajozs5Jf7NZVY/JLThBKhhPstTl3K9OZr3Z9oGXtI1C8zGzvEXM6nHSiFRBKha+jGEV7hAy9ox7/AAU+01OXcr05mvMgLum7l7Ra/wDSxdbLeEXTgINBcLKtrAKISPnhlI10a3wNmRMr8NbQv/aanLuV6czXQ6Ji1pxXYSGV7D9+4biSljLB1LTQEknlOGwiBZeWxlw70bKX+qi1Hdl8riF75d+01OXcr05musZImeU8tVUqKVAztp62XLiGhm2gBoRLLVVKil2uSayZ6OL/APR5f8llUKv9H/tNTl3K9OZriWljq5tJTAUglleKju9Dt+sM1s7sBzPdz/7n0eW/4YzHpf5OfaanLuV6czW0VqnlmaQjFkUvmfStt6nbZDZ7yeZ5ObdgPSFE/wDNYNX+gsq4H3Kz9pqcu5XgVHEcewmY2EzGwmY2EzGwmY2EzEk83VFCGpCQAzVoeCnZwarhNZqWmzlL+Z3QtyRU2c51TtNJtzWTNNMqKcrkXw0IkYMCGhukUYbaEnK9i+zuH7TU5d+uoHwU0qtrAq0etIKIMuHSZMEgWyqikAkk1VUGVznSTJMd+3svaQS/79pqcu/WUVIulFnC4h14zaIkhlE0iIwKISyjjBlgXM4BF050n2bm/wD5yuZO3ojfaanLv1Vx4k0mSormlge1RRULW1G7Silczzc28RelGgf2BdzPBH3UrfZanLv015boQiis8VFUusls9xTmezm7inpWU50zQlGSqlZXIjUraaKFWAJ9hqcu5RVImBXvdPje6fG90+N7p8b3T43unxvdPiSunzqynSYR8qspQqMftsxs7xFzOxyUopWuuoSvpbs9Vu4NZns2dop+iOmGypXM1OXcr05mzynOmbQX98EsrrQZLZCqmdFVlst+tdOAghlgsq4tAoZI8dGUTXS4A9ZYZFVKFhOzOxmx6X2ozahKjRQE4XcjZGQxsrU5dyvTmawlqQqSeTz4KmUyvtvd3XYSUsZYOJaaAkk8p06CnlV1aGXD3TLPXtzns7iZgCrB9OMpg9skRHUB26yQU2eBguEaBc7WERRMjU5dyvTmayzHBus5lGBoMBONErQ1DMXAENDNtADQiWWqqVFLsck1oz02yHLIYPOdIFlEFV7O5weRzybPOSTDajWldngtcyCYUSwsgoVA4bpadaRXi1OXcr05mtMhw7wLZXAihrieOAIWGyesM1s7sBzPZzd9PpyiuoOtpumlYCsVUyqkbaySdgfs6IVxX2aVR5amIp7NBIA7OCNMFGgjlIDCoBpznBAAiqhWXEOYNTl3K9OZrRM4KQMoyqEskMr7b3fhZGQ2e8nmFDkKH4FRY8CoseBUWPAqLHgVFjwKix4FRY8CoseBUWPAqLHgVFjwKix4FRY8CoseBUWPAqLHgVFjwKix4FRYebeIIxTooIWsARrvANUl9Y0aBJAOZ0CrguLU5dyvTma21F6aKfpqlXTknKVUnagTRj2CEXDNrFNMqKftdpOn9FynOmbdfVQMgRgzAf01dcKIoK44jS6LkanLuV6czXGI4e8pyqyYErkTxIVONw2df+32k6f0ajuA6iVozzIKkvoDjhFg1t/0BwZNDHBsrU5dyvTma4CLWAK3FuhcT8r1b28ysNnX/t9pOn9HpTrUkmE1/EDMi5oA3RbPrRBMkp9otMoUFc4qV52py7lenM11vLVaGoAD0GQcr2b27jLZ1/7faTp/SII4pesm9lcpBbtJnAPaClCRQ8kUSJOVInHiFJit0I9ECPdFDgftFT6IM9pBqqDjpVT0Tn/Z2U99HU4l5kKEeZChHmQoR5kKEeZChCqo1qx+8jPA6ilfMhQjzIUI8yFCPMhQjzIUIOvs2fKkDlSec8yFCPMhQjzIUI8yFCPMhQjzIUI8yFCPMhQjzIUI8yFCPMhQjzIUI8yFCPMhQjzIUI8yFCPMhQjzIUI8yFCPMhQjzIUI8yFCPMhQjzIUI8yFCPMhQjzIUIXHSZXgP/FU1iQBuNyp8blT43KnxuVPjcqfDmKglTlhvJxUym7lT43KnxUhJ1UG2mXEkdIDJ4tttJIRkKaIQnI6WqJmrSbRSKf3KnxuVPjcqfAjfThJG2jRORooMTEs0e6lFIf53KnxuVPjcqfG5U+DEpUj2GuUBNmNyp8blT43InwYa5EWSmiGE3o8kpGU+PEqjCUunjKhBpwqAZnxKowcPDnxLDW0lxHhyBXxKowG6FCiaQthqklVPpUSk/8AloEKocUoWpKFiZ4M7N2kbaTqcH18+Ad8SqMAus7RNMWy6lCgnhKIBotWTMWKPfT7VxZOE1HxIox4kUY8SKMVVTrqsM7ij4tQBLxKoxJzKMoSnNtIooVAwakU2E70ehatB7jbTW0l38Dgg1zoVoUJSpPWWoR70ysndhINs7sqgcLUnCwoVQIllJ1OFXUsAhagRE43I8Td5X+WaPfT7XNq9xncUq6ZiXqnWXdspSUej0LVoPcbaa2ku/gYpoqrm3UQUEUyPSVAEEmLXYlKdU0snsBJ1ne+NSnOmaWc24i6yPdGbKTqcKupYtOc5prr0uxR76fbUAFXPZgY2YGHUCGGn2WdxSrpmCShDnRfSF83I2pdHoWrQe4201tJnTKqO6oiVMqYNGgiYK0uVKU7LaI7UfgVp1DC+DYR0qpKpVSe3EZynTOwk6nCrqWKEVmUTHeP/C1ij30+1wnTAKpvM5G8zkCnDA9NlncV6x3VESoplE5/ySw5ZCUdIIWrQe4201tJdQwgJLbzUIq2IVNChUGAlRPqTTVlBI7Enq67Qli+MpR4ylHjKUADUmAXKR2U/YSdThV1KASwpiaO2qqK666QqFhQ3idsUe+n2ubV7jO4pTqnQnbeagsqmi45Q1QdLuRK2UbpBC1aD3G2mtpLv4HBsqvfBrKZJTK10TDqzoZLblCqqVFKibmeOYtM73hdfI7an2EnU4/xTHd0R6QbVyZKSsuiqVqj30+2YdFU+6Djug47oOFyX8VrDO4pV0zBuquwmDAFBoFRI1p5ro+gSoKreR2KpzqnaDOGQaRTZgeWFFdQdW8jsV11C1ZwTIxeKlA3XLIEMIBVvI7ZoqqDq3kdjeR2N5HYrOGBLu8jsbyOxvI7G8jsbyOxXXULVYBMCl51KBuunGSiclIUyMY//cn/AP/EAD8RAAAEAggDBQYEAwkAAAAAAAECAwQABRAREiAxMzRxMkGBEyFQYLEiI0JRYcEVMKHwFFORJTVSYoCCkKDR/9oACAEDAQE/Af8AQuq7RROBDj3j5PfPitS1BxQc5lDWjYxKHB1Simbl5NfPitS1BxQc5lDWjY0STjP08mPnxWpag4oOcyhrRsaZJxH6eS3z4rUtQcUHOZQ1o2NyScR+nkp8+K1LUHFBzmUNaNjdknEfp5JfPitS1BxQc5lDWjY3pJifp5IfPitS1BxQc5lDWjY35JifpebzGyuZJXCsah8gmGoojBzmUNaNj+RJMT9LznPPuMS6Y2fdK4ch8gKcA/kyT4+l5znn3GiXTGz7pXDkPj6uWbb8mSfH0vOM4+40y6Y2fdK4ch8eVyzbDfIQyg2ShWNEk+PpecZx9x9aWzBdz3gFQfOG6QoJgQRr8dWyzbDdKUTDUWG0oOf2lu71hFBJAKkwqgcYknx9Ly+cbcfWG6B3KlgkNpWij3m9ofH1so2w0gFfcENpSqp3q+yH6wg1SbBUmFI4xJMD9Ly+abcfWJRqug+NPnxWpag4olZzKN7RsaxurZRth9KGTAzvvrqAIbs0W3AHf870kwP0vLZptx9YlGp6DeF+CToUVMOXibxcWyAnCDnMoa0bGJRpeo3V8o2w+lElyTb35JgfpeWzTbj6xJ9T0G9NNWbpEumNn3SuHIfEptpR6USjS9Rur5Rth9KJLkm3vyThP0vLZptxiT6npemerN++VEumNn3SuHIfEZtpR3CiU6XqN1fJPsPpRJck29+ScJ+l5XMNuMSfU9L0z1Zv3ypl0xs+6Vw5D4hNtKO4USnShuN1xkn2H0ok2Qbe6NEk4T9LyuYbcYk+p6Xpnqz/AL5XJbMBAQRU6eHzbS9QolOlDcbrjJPsNEmyDb3RwoknAfpeUzDbxJ9SO16Zas/75UlKJhqCGDAGwWz8Xp4fN9L1CiU6UOt1zkH2GiTZA73RwoknAfe8pxjEn1A7Xplqz/vlQUomGoIYMAbBbPxeniE30vUKJVpA63XOQfYaJNpx3um4RoknAfe8pxjEm1A7Xplqz/vlBSiYaghgwBsFs/F6eIroEcJiQ8Omp2p7JolWkDrdc5B9hok2nHe6bhGiSZZ9/tePxDEm1A7XpgUTPDAEMGANgtn4vTxNdAjglg8M0BbI9mP1uutOfYaJNpx3un4RokmWff7Xj8QxJtQO14jUhFjLcx8adac+w0SbTjvdPwDRJMs+/wBrxuIYk2eO3kB3pz7DRJ9OO91TgGiS5R9/teNxDEmzzbeQHenPsNEn03W6pwDRJco+/wBrxsRiS55tvIDvTn2GiT6brdU4DbUSXKNv9rw4xJc823kB5pj7USfTdbquWbYaJLkm3+14YkucbbyAoQFSCQecOmp2p7Jok+m6jdVyzbDRJck2/wBrwFExqgiXsf4Uto3EPkFdAjglg8MW5myQpm+d1bLNsNElyTb3mDAGwWz8Xp5IWyjbD6USXJNv5OWyjbD6USXINv5NcvkW3cYax+UOZks47g7gok2QbfyYoTtCCWuqHTZRqpZNTJsgd/Jq6BHBLB4dNTtT2TUSbIHfycugRwSweHDRVBXs6q68PrDBsZqjZNj5PqAf+7Y6TOqiJExqGDsHpCiYT4fUYapuXYiBD4fUYZs3SK1pQ1YbjdWFZV4ZMhufzj8Pfh8f6jCL9w1V7JxhemzkUUgIUe8YlrhRNx2So4/O9OFDkULZGrugrB8YoCB/1GDlmLL2q6w/rDF8DsKh7jBdnKhyWLI1YwmxeqkA4Hx+ox+HPv5n6jAdwXH4iVqcQhsi6dlESHw+owdrMG4WwNX1iXPhdVkPxB4Q4yD7DEk4z3if3p/uomihV3AAn38oIFRQC6H9oP8A/KHoH/sTdESHKuWGywOEgUDndnWaTb7wjlF2CB74RD+HmNkvzquzv4OsIzcqSZSWMIQmxVlQTsY3ZjpDxJcs+/2hVUiJbRxiUFEzkTBh3+EOMg+wxJOM95VIVnxkwHEYVlCpCCYDVxKCoGONriDC7M3HYNxAMR7oaoviFtoBjtCqUzWLYOHd0iTr2DmQNdnWaTb7wjlF2CHDpJsWs4xLyGcu+2Hl33Z38HWGiaYtyeyGEAmQO8AuzHSHhmxM7KIgaqqHjFRpUIjWAwwKgCACjz8IUL2iYl+cMGJmZjCJq67xZcYHfb2uddCssN2/bImqgK6u+49YKO1ANaqAIKUCFAoUKy04ue3TNVzuv2BnZwMBqqo/BVf8frCclCv3h/6QkkREtkgVBdfsjPLNQ1VR+DK/zPWPwZX+Z6wmWwQC/K45RFdEyYc4YNDMyiURrrhZIq6YkNzhiyVaGH2qwH/nU//EACkRAAEDBAICAgIBBQAAAAAAAAECAyAAEBExEjJQYCFBEzAiQlGAkKD/2gAIAQIBAT8B/wAFwkn09KeVapwY+fTUp5VqzvpiU8q1d30tKeVag76UlPKtRd9JSnlWpO+kJTyrU3ZFHxkeha/Q7IapaPsegD9Lshqy0fY8+P0uyGrrR9jzw/S7IauVgUTk+dG5Fz+1Ek2dkNUTgUVk+fG4FwDVFRMHZDVOdfNJTypfwYjdlL40VEydkNU51lwynI8mkZNapztEbs7ubshqnOskdaWj7Hkm+1nO0Ruzu5uyGqc1JHWy0fY8i32s52iN2d3N2Q1TmpI63Wj7HkG+1nO0Ruzu5uyGqc1JHWC0fY8e32s52iN2d3N2QpzUkdYLXnx7faznaKd2c3N2QpzUkdbrXnyDfaznaKd2c3N2bmpI62WvPkQcUlXKnO0U7s5ubs3NSR1pa8+TBxSjk5indnNzd3NzUuXxjzSd2c3N3c3NegJ3Zzc3dzd16AndnNxFndzc16AndnNxFndzc16AndnNxFndzd16APikq5U52iN2d3NauXoIOKUeRiN2d3Ja8+kDdnd+nDdnd+mhJVQQBZ3fpg+KSrkLu79NBxSVcrOb9OBxQUCM0s8j/wB3aTg1zTSilNKUkj4iMBOa5popChkSbGTSwCMiTY+K5pr+CqUnjFuitIrmmKO1KKU1yQaWnj4gbp2X9FkDA+ZdEU2fqiMGLWqO7H5RFqi3k0W8DMUdqd3QGac6+IG6dkDhOaDgpzMUDJpRT90CgU4PuLWqO6CSaX/FOItUo/NZijtSlcaSoKpec/PiBS1cpc/44sF/GDFKwkXC/jBihfGvyii7ROYoVxr8gr8gowScHNKVyoHBpSgr/ep//8QAShAAAQICAgoNCwMFAAMAAwAAAQIDAAQRMBASICExNFFyc7EFIiMyM0FCUmBxkZPBEyQ1QGFwgYKSodEUYrJDU2OD4RWgoqOw8P/aAAgBAQAGPwL/ANK5LTApUftCVSZK3UDbjndXueDTApUftFo1fUd+vLYVMyY3XCtHOi/7m0tMClR+0Wjd9Z368txMaRWv3NBpgUqP2i0avqO/XluZjSK1+5lLTApUftFo3fWd+vLdP6RWv3MBpgUqP2i0avqO/Xlu3s86/culpgUqP2i0bvrO/XlqHs8+5YNMClR+0WjV9R368tS7nn3KpaYFKj9otG76zv15ap3PPuUDTApUftFo1fUd+vLVu5x9yaWmBSo/aLRu+s79eWsczj7kg0wKVH7RaNX1Hfry1rmcfcilpgUqP2i0bvrO/XlrnM4+5ANMClR+0WjV9R368te5nGrYmpXhqDbp518xf9waWmBSo/aLRu+s79eX1BecauV6jrMGZkk7ry0Dle4JDYwqNEWjV9R368vqBhecauV6jrNhUzJjdcK0c6KD7gJfSJ1+omFddXK9R12TMyad15aByvcBL6ROv1E9UK66uVzfG4VMyY3XCtHOig9PpfSJ1+onqhXXVyub43JmZNO68tA5XT6W0idfqKuqFddXK5vjdKmZMbry0c6L/TyW0idfqKuqD11crmXZmZJO68tA5XTyW0ifUVdUGrlMyo8ow4kTB36B07ldIK7d17fmDDCVZRTYV1QauVzLrdl0r5gwwUs7g1+03+3p5K6UVlMy4AeJPHBRKbg3l44pVfJ44bzRYV1QauUzLimYcAPEkYYKJXcG/vFJvnp7K6QVVvMuBA1wUSI8knnnfQVOKKlHCTZRmiwvqrJTRiyJaWIRSikr44KlqKlHCT0/ldKKi3mHEtp9sFGx6bUc9WGCt5ZWs8ZuUdVhfVWSmjFlOiHj7gJXSi6K31hCRxmCjY5NP+RUW8w4pxXtu09VheaayU0YsjRDx6aBpgUqP2hKG76i6LdWXDVymkFwVOqCEjCVGCiQT5RXPOCLeZcKzUjqsLzTWSmjFn/WKt9TF9TQptcsX+k6WmBSo/aLRu+s79eWE6UajVymkFl55ABUhNIpimZcKsg4hViw5mmslNELP+sVc11CDMySd15aByukwaYFKj9otGr6jv15bCdKNRq5TSCzN5lYLDmaayU0QsnRpq5rqTYVMyY3XCtHOi/0kfNF+38LKNKNRq5TSCzNZlYLDmaayU0QsnMFXNdSbJmZJO68tA5XSR/SeFlGlGo1cppBZmsyudzDWSmiFlWYmrmvluFTMmN1wrRzov8ASJ7SeFlvSjUauU0gszWZXO5hrJXRCyrMTVzfy+NyZmSTuvLQOV0ie0vhZb0o1GrlNILM1m1z2YayV0QsrzE1c38vjdKmZMbrhWjnRf6QPaXwst6UajVymkszWbViy/mHVWSuiFlzNTVzfy+N2ZmSTuvLQOV0gd0vhZa0vgauVz7M1m+NWLL+jVWSuiFlzNTVzfy+NQqZkxuuFaOdF/o87pfAWWtL4Vcrn2Znq8atPXZf0atVZLaNNlzNTqq5v5fGpM42Utqp2yed0ec0p1CyzpfCrlc+zM9XjVp67Mxo1aqyW0abLuanVVzfy+NQp19VCR94t3LyBvE5OjzmlOoWWdJ4VcrnWZnqGurT12ZnRK1Vkto02XepOqrm+tPjdl180JH3i3cvIG9Rk6PuaU6hZZ0nhVyud4WZj4VaM4WZnRK1Vkto02XepOqrm+tPjdKdfVQkfeLdy8gbxOTpAvSnULLGk8KuVzvCzMfDXVt5wszWiVqrJfRpsu9SdVXN9afG5Lr5oSPvFu5eQN6jJ0hXpTqFljSeFXK9Z1WZj4a6tvOFma0StVZL6NNl7qGqrms5PjcKdfVQkfeLdy8gbxOTpErSnULLGk8KuV6zqNl/4a6trPFma0StVZL6NOqy98NVXN5ybJdfNCR94t3LyBvUZOkf6aZvNLNIVkNmXz/Crles6jZf+GurazxZm9CrVWMaNNl/4aquazhYLr6qEj7xbuXkDeJydJUy04rcuSo8mxL5/hVy3WdRsv8Aw11bOeLM3oV6qxjRpsv/AA1Vc1nCC9MGhI+8W7t5I3qcnSdMtOK3LAlR5MS2fVy3x1Gy91jXVs5412ZvQq1VjGjTZf8Ahqq5t580AKHxi3cvIG8Tk6Uty7ptkNmlPsq5b4/xNl7rTrq2dINdmb0KtVYxoxZmPhqq6OLprLfN/E2XutOurY0iddmb0KtVYzmCzMdY1e4CX+bUbL3WnXVsaROuzN6JWqsZzBZmOse4CX+bUbLvWnXVy+kTrszeiVqrGcwWZnr9wEv82qy7nJ11cvpE67M3olVjWYLMz1+4BjqVqsuZyddXL6ROuzN6I6qxvNFmZ6/D3AMdStVlzOTrq5fSJ12ZvRGsbzRZmc73AM9StVleemrltInXZm9GaxGaLM1ne4BrqVqsrz01ctpE67M3ozWI6rM1ne4BrNVqsqz01ctpE67M3ozWJ6rM1ne4BvNNk6QVctpE67M3o6xPVZms/wBwDa3zaooIpyWTpBVyulFmbzKwdVguvmgD7w6/Ra26qaPcCmWnFblyVHk2P9gq5XSizN5lYIL0waEj7xbu3kDepye4NMtOK3LAlR5Mf7BVyukFmazKwuzBoA4ssW7l5I3qcnuF/Ru7dIUCg5PZVyukFmazKy3dvJG9Tk9yMrpRZms33OymlFmazfH3OymkFmazfc7KaQWZrN8fc4C0i1b56sEBxW6vDlHi6hZmerx9zXm6NrxqOAQFTPnDnt3sUC9cTPV4+5kf+RTSg4CcAPtgBAATxUXUx1ePuaTLTity5KjybqY6hr9zaZacVuWBKjybmY+Gv3OJlpxW5clR5NxMfDX7nUy04rcsCVHk2XgogU0Ue55MtOK3LkqPJgvPq2vF7Yt3byRvU5Pc+hDiypLYoSDxf+iBayzK3TkQmmMU8kMrigmN3mmG+qlUbrsgo5rf/YvzT57IxiZ7R+I2s2+OyNw2QIzmv+xuLzDvaI28mtYyt7aLV1JQocRFFWlxmSfcbVgUlGGPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zi/IzHdmN0lnkdbZrkuMyT60KvhQRhj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92Y9HzPdmPR8z3Zj0fM92YvyEx3Z6IhuWaW6s8lCaTAVPLEojJhVAKmf1K+c6aftFoyhLaRxJFFVazTLbyci00xTLW8or9ppHZBU0j9W1lbw9kUKFBHFUbH6L1Dd2G3c5AMbeRbT7UbXVFMjNOMnIsWwglDYmkZWr/wBotHUKbWMIUKKnY7QJ9aXmnoeltpJWtV4JHHCXdl1FhH9pO+jyckwlpPsF8+oedMgOf3EXlQXJfzqW5yRfHWLvY/ReqWs7Ltve0i+PjCnNh3Lb/E5+YLU02ppwYUqF3sdoE+tLzT0O3EeTYG+dVgiiWRbO8p1W+Pqin5GiXmv/AJVCmJtstOJ4jc7H6L1byc63bUb1XGmCu+9KHA4BrutjtAn1peaehqZrZEFuUwpTxr/5CWpdCW203glIwereTmRauDeODCmCxNDNUMChcbH6L1dTbyQtCrxB44/UyQKpM4R/budjtAn1pwnmnoYie2SRuGFts8v29VVStQSPaY3XZCXp9i6YxkqzWzG/e7qMYWOtoxtJ9kZ6rXXFLS0rGVJpqVMTAv8AIXxpMOyzikrU2qilJvWdj9FdUKcQD7VRwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1RwqPqjaqB6jVKbdSFIWKFA8cbSkyrt9s+FxseFOoB8gnlRwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwzf1Rwrf1VCtjJBd7A+sfx6F/qpseZtnBzzkgBIoAwCoUgL/UvDkN/mCJW0lEftvnti2m5h14/vWTdW0s84ycqF0RQ8sTaMjmHtgImPM3f3m92xSL4ulyOxS90wOOji9gik2dj9FdT3yfwFRtVqHUY3CemEezyhojdlNzKf3poP2gInUqlFZTfTAcYWlxtWBSTTduyzl5RvoVzVQtl9Nq4g2qh6qnZKeRtP6CTx/uuzKSivPHBh5gyxScPQpEs3eThWrmiG5eWTaNNigC7t5te2O9bG+VCmwf08t/bRx9ZrAGl+VY42lm9/yPN1Wjw3zSsIuFyOxK72Bx4ahc7H6K6nvk/gKy3k3CBTtkHAqNpuUynftE6rtufaG1e2rmd6p5aZHmbR237zkgJQKEi8BdFd5Uwu80jLC3phRW6s0qJ6FpU4POXxbOez2XZZl6HJw4E832mFPzbhdcVhJrkuy61NuJwKSYErPUNzfEeJcUm8IXJbFroYwOOjl9Xsutj9FdT3yfwFaiYlVlDqDSDCX07V0XnEZDdTTVFKwm3R1j1NLLW1bF9xfNENy8qi0aQKALpyamjQhP3OSFzMwcO9TzRk6Fhx0UsS+3PXxXdq1Qqbc3icnthTryitxZpUo8fqAUg0KF8EQ3JuqtRRQ4oYXOu72P0V1PfJ/AVzYUdxmNzX4Xc4xxIdUB1eoty0qm2cWaISwzfVhcVzjdKdeUENoFKlHija0plW+CT49DGrYUOv7ou6dmpjetjtOSHZqZNK1nsGT1nY/RXU98n8BXUi8REpMca2klXXx3TxH9RCV//wB2eoBKAVKVeAEeUfAM46NueaMl2ZGSV5s2duocs/joZKyxFKVL23UMN2JFlW5S+/8Aav1rY/RXU98n8BXs08hak/e6l1c5jxPqCdkp5O6q4FJ5Iy3atjpFW6q4ZQ5IydDZqbV/TTaJ+N1MTSv6aaQMp4oU44bZajST61sforqe+T+Ar/8AerwupPRHXXienU+atnaA8s/i7tGCDOOjaDm+2CtxRUtV8k9DUr43nFL8PC6lpNOFxVurqHrex+iup75P4Cvl/wB5Ur73TCeawNZrqFUplW+FX4QhplIQ2gUJA4rpUw9fVgbRzjDkzNKtnFnodIN/4Ek/EU3S0cTLYR4+Prex+iup75P4CuShF9SjQIlpYf0m0pupn/GAj7VqJaWF84TzRlhEtKihKcJ5xy3TkxMqtGmxSTBec2rYvNo5o6HAZYaTzUAXWyCv86h2Gj1vY/RXU98n8BXCacTuEtf+biuipWACkxMzB/quKV96xDLCStxZoSkccWl5Uwu+6vwuipZoSL5JjyMsfM2jtf3nL0PazxdzSsrqj9/W9j9FdT3yfwFamXlU0qOE8SRlhuVl8CcJ5xy3T9BoW/uSfjWicnE+duC8DyBdq2NkV7QcOscf7eiDWeLuYH+RWv1vY/RXU98n8BWBSUeRluN1Y1ZY8lKJw75Zwqu/0zRpalr3WrjrE7JT6doL7CTx/uu/0cmrztwXyOQOiKTkMIVlSLqfRkmF6/W9j9FdTqm2XFJNrfCf2CMWe7sxiz3dmMWe7sxiz3dmMWe7sxiz3dmNrKvn/WY3ORmFf6zGJlGeoCKZ2abZGRAtjAV5L9S4OU7f+0XrtSkHzhzatDxglRpJq/LTIok2jtv3nJASgBKRgAurffTC7zSPGFvPqK3FmlRPRKRc5zCNV1M5HQF+t7H6L1hyZmlWraB2wqYdvJwITzRVpZb2rYvuL5ohuXlk2jTYoAulzM0aEpwDKckLmZk3zgHNGTonLj+2Si6k5we1tWset7H6L1dUxOLtED7xSqluXTwbeSrblpVNs4s3oSwzfVhcXzjdLdfUENoFKieKKRSmVb4JPj0UnJQ+xwarqZZSKXALZHWPW9j9F6sptkiZmuak3h1mPLTrlseSOJNWlDYKlKNAA448o+KZx0bf9vsuzJSSvNWztlDlnorLFRoQ7uavj/27WUChh/bo8R61sfovVA+4yt6k0C18YKAv9MxzG/zWp2Rnk7qrgUnkjLdq2OkVboeGUOT7Oi1IvGJeZ5Sk0LzuO6Wz/WTtmj7YW26koWg0KB4vWdj9FdFD02w2sYUqdAMY/K98mMfle+TGPyvfJjH5Xvkxj8r3yYx+V75MY/K98mEpE9LFSjQAHk37p2XmU2zbgoMOSz3FvFc4ZawTs6nzVs7VJ5Zu/JMEGcdG1HNGWFLWbZSjSSei7mx7qto9tm867VsjIp3VPDIHKGX1JmZfZUhl7eKPHd7H6K6nvk/gKikXjHknz52wKF/uGW63IedNX2zl9kFKhQReIqqFUplW+FV4QhphIQ2gUJA4rpT719ZvNo5xhyYmlW7qzSejDbzJtXG1WyTDU03hI24yK47tc9sSj2uMjWIv16Z3ZZFq2L7bR4+uFS8y2FtKFBSYt0UuSajtV5PYbrY/RXU98n8BUtTUvvkG+MoyQ1MyxpbcHZdHZOUTtVcMBly1KJaWF84TzRlhEtKihKcJynLdOTE0q0bQKTCn3byBebRzR0a8m+qiVfvL/actQp+Sol5rj5qo8jOtKaX7eOsSxJtKdcPEITMbI0PzPEnkpsrZmEBxtYoUkwXmKXJJRvHm+w3Ox+iup75P4Cq/TTKvNXz9Kst0tp5IW2sUKB44U1hZVtmlZRdoZYSVuLNCQItd9MLvur8LoqWQlIvkmPJS5Ik2jtf3HL0cTsbOr3VPAqPKGSo8lOspdR7YK9iHv9bn5iidlXGv3UXu2otZKXceP7RegL2WdDaf7beHtjyciylpPHRhNypt5IW2oUEHjgzEmCuSPai42P0V1PfJ/AVf6GaV5wyNqecm6UwqgOi+0rIYWy+kocQaFA8V0JycT524LwPIF2rY2RVuY4ZY4/29HQtslKkmkEQJabNrOoH1jLU0KAI9sUuyTaVZUbXVHm777XXQqNz2RHxZ/wCxjzX0GNtsgn4Nf9jziZfczaExtZRLp/y7aLVpCUJyJFFQ6udtfIBO3tsFEPKkUFuXKtok8Qs7H6K6nvk/gKtuYllWrjZpENzLN6nfJ5puv/JSqd0QN2A4xluU7JTyNoOASeP912pCiQFCi8aDGLr71UYuvvTGLr70xi6+9MYuvvTGLr70xi6+9MYuvvTGLr70xi6+9MYuvvTGLr70xi6+9MYuvvTGLr70xi6+9MYuvvTGLr70xi6+9MS7kg2pCluUGlZPF0LS4yoocSaUqHFCZafIbnOI8S/V1PTTgbaThJjybVLcmk7VPO9puNj9FdT3yfwFYPKHzV284MntgKQaUm+DckKvgxbNDzR40t+z2WZJl8Wza3QFCAlIoSLwHrcnpjq6GUi8RCZbZklaMCXuMdcJcYWHG1YFDj9Ut5te2O9bGFUUvG0ZB2jQwC52P0V1PfJ/AVv/AIybVtk8CTkyXTkq/gVgPNOWHZaZFq42aDY2O0w9ck9MdXQ7zVzcyds2remAh1X6WY5qzePUfUS5MOJabGFSjRCmdhhbq/vKwfCFPTLhdcVhUbrY/RXU98n8BWodZUUuINKSOKEu3g+m86nIbr9XLJ86YGAcpNjY7TD1yT0x1dEAlt3yrI/puXxATPAyjmXCnti3lXUPIypNNZ57NNtnm03+yCjYpik/3HfxFtPTC3cg4h8KjY/RXU98n8BXIfFJaVtXU5Uwh5lVs2sUpN1+slk+bPG+OaqNjtMPXJPTHV0St2HFNLypNEUF8TCf8qafvHnkl8W1RuofZ60U6oxwJzkmL2yMv9cekZbvRF/ZBj4KpjGSrNQY3Bh90+0ARRKSjTXtUbaN1nFpTzW9rFJqmZVqXl1IaFAKqadcYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8w7OPJShbtFITgwUV/wCnZQ083TSPKU3oxWV7FfmMVlexX5jFZXsV+YxWV7FfmMVlexX5hyXmJSVU24KDvvzDM02ApbSrYBUYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MYrK9ivzGKyvYr8xisr2K/MNNTLTTYbVbC0p/9KuZ/UtJctaKKYxRrsjFGuyMUa7IxRrsjFGuyG0y7aW0lumgddSFzDCHF2xvkRijXZGKNdkX5VHwvRTKLUyrIb4jycwmg8R4jWOTE22HEnaoBgj9K2PhDjK8KDRVyyHBbJU4ARGKNdkYo12RijXZGLAZpIimSdKTzV/mPJzCChVUOuB5q32RijXZGKNdkYo12RijXZDoTgCjUvpmW0uAIvUxijXZGKNdkYq3G5BTJ9hi2VujXPHQ9f6Vdpb4b0cMPoEMNPOgoUq+LUWHkIeFqlZA2oyxww+gQFzKrZQFGCpTnmGlyy7VRcoN72Rww+gRtlIX1ogpKfJvJwpywtsjbi+g5DF+qQ23vlmgQ0yjAhNEPeS/pLtYbm0D9i/CrlNKLD7bbtCErIG1EcMPoEbqG3R1URap3N3mGC26L/JVkhbLu+QaKlPXAhbUu7aoAF61GSOH/APgRw/8A8COH/wDgQVKwm/UzGjiYcbNC0NkiOGH0COFSfkEJZnEhClXgsYIU26m2QoUEQ6xxJN7q6ISudYmdKrXVpzzDGl8DZlrXjVRYmQMHlFa6pcyobVq8nrh1wHbm8jrgIUdo9tT18UOsLwLFEKbcFCkmg1UppRYmtKbKXGjarTfBhp/nC/1wzMp49oqpT1wId6k6q2Y0cTeiVquGlL3xQCYR7WhrPRCVzrEzpVa6tOeYY0vgbFCAVHII/VTabQjeJMOPO71AphS1YVGmpoF8mGmeUL6uuEy6TtWsPXAIvEQ09yiKFdcJmUjau3lZ1VKaUWJrSm4UMjhj/YKlPXAilbaFHKUxwLf0RwLf0QgobSk+UGAVUxo4m9ErVZSp5BbYGEm9TYdUg0pTtB8OiErnWJnSq11ac8xtgDG8T2RtQBBdfNqgeymPJti0lxxZaoOKG5s7b48Vhbi5zbLNJ3OMb/8Ax/8AYcR5byqFX6LWiiHWuVRSnrgg3iKmU0osTWlNw0ld5atsYZZ41KtqlPXAhxDT7iE0C8FRjTv1xjTv1xavPLcTkUqqmNHY3ieyLyQIJMKYkKaDvnPx0Rlc6xM6VWurTnmGSytSD5XCk0cRjGXu8MUTTq1srvG2VTR7YU24LZCxQYU0q+nCk5RVItuEc26oQ35LyqlCk7aiiMUPef8AIxQ95/yMUPef8hDre9WKRBcQNze23x46mU0osTWlNihltTh/aIS9shxXw3+YUtZtUpFJMKc/pi8jqqU9cCHepOqtmNHE0UkghpVBHVGMvd4YQ55ZxdqcClk0wh5neq+0fqWRuLhvjIeiMrnWJnSq11ac8wxpfA2f0b526ODOUQUjhU30GClYoULxFQ2kjc07ZUEqNCQIdfPKN7quFyqzfbvp6oWEjdG9smplNKLG9HZG9HZGSD5Z5JVzU3zFokeSY5uWqT1wIpKQfhG8T2RvE9kbxPZE0BzqmY0cTeiVqs+SeO4OfY5YW06KULFBhTLnynKOiAU2ooUMBBjG5jvTFKjSTx1dqzMOtpyJWRFD77joHPWTZCm1FChgIMY3Md6YKnFFajhJNQfIOrap5iqIKVTTygcILhubZlxTasqTRGNzHempCkEpUMBEY3Md6YxuY70xjcx3pjdH3V9aya3G5jvTGNzHemMbmO9MY3Md6YxuY70wVOKK1HCSaklh1bRPNVRBSuaeUk4QXDcUCbfA0hgeXdW7Rz1U/wD7yf8A/8QALRAAAQEFBQgDAQEBAAAAAAAAAQARITFR8CAwQWGhEEBgcYGRscFw0fHhoLD/2gAIAQEAAT8h/wAV2KnBwCZQn3EtaEEEguPw7jTwcAmVyxIeewYMeAahmiCTHCPhvFTg4BMoAHIDz+rFWm+GsaeDgEyuWJDzs1qb4ZxU4OATKAByA8/q1TJvhjGng4BMrliQ8/h47FTg4BMoAHIDz+rihz+FsaeDgEyuWJDzuaLP4VxU4OATKAByA8/q6rM/hTGng4BMrliQ87sm0T/hPFTg4BMoAHIDz+rynT+EsaeDgEyuWJDzvMFTp/COKnBwCZQAOQHn9XuCqE/hDGng4BMrliQ874wVIndgTyQykIWaIRAMI+A8VODgEygAcgPP6v4iqk7xcMGZEB3DNEEEguPwCR0AMSc3LliQ89w0Srk70UMGPANQzRDIGERHwBRpNx0y1O7q0+0Ys4HgdwzRBBIIYR8IuBr13qnlYGLHhGoZohkDCIjj6rSbjry1S71LysjFnA8DuGaIIJBDCPg7TVFrG42YmPEDUM0QiAYR8Gmagteu6bO2MGYDwO4ZoggkFx47p09x19ak3dTncNRSxbczI8d1ud86ScL0kwBzLY1Nai70e0RAeC9QuU2weeaEkmmPHdRneSFUPPomUMCb9I7MXoliqhLZra113otjmJEH0UUNiC/1wRwUkiTx7W53TXoQGPIE/wA/MLlJRKjFpO2qS2ar4UXnfAZ4EEGJsOyjpkDSeP6rO4Mc0MeSrCs4KM0wrSbOk7Nb8KI30qjPjUwxu6bO1Eq8VifipPgInMOJtt4uXZVJIxN8qoz40Y08HAJlAbfliTLtU52MFrwALtxSHIYqWR2wHIXOhbKZJGN3Q5bYdbzduWePEGSIRAMI4nxU4OATKAByA8/q82Uue0uwQIGqJYOSzkC7wMhsqUkbuoy20vO7o+aGDMB4HcM0QQSC48S408HAJlcsSHnenKnO/HBQZspkrykyvkUTPYMGPANQzRCIBhHEjszsN3EofRZ3yq0rygyvr1TPaMGYDwO4ZoggkFx4jrMm4mFU2d2IqA3ZRZXlJlfK0/tYGDHgGoZohEAwjiKvybiIJTZ3cQQ2OVrrwKXDbTJbgAYMwHgdwzRBBILjxDQZNxcQr87uDzQ2UOV47Su21SV3FaAwY8A1DNEIgGEcQUGS+saRtoM7vVIX01BltoUruC3hgzAeB3DNEEEguPD+ueG3SLs0/bpF21o21CV5SZbatLczDBjwDUM0QiAYRw9rG00zyu6LLbod20C/co0r6zX3NEPsY8s+ITFBmu67I7dFu2iX5lClfIau4sANBiUgjo8I1cP3xCIoc13X5G+g0u/CqUttWk3KrU3wpBHB8JFw/fEQijzXepeW3Q+V3UJ7aPPeUKW2jSbitgBoMSkEdHhGrh++I/FZmu9U8tunuykT21ue8p0tteku6VKy1N8KQRwfCRcP3xfs5Up77FOntoc95RJbaTJd0SVhgBoMSkEdHhGrh++JTmpbylOpM9tfnv4NL4rukSO3U3wpBHB8JFw/fEZwsPemyQIBoeNmv3zNR5Lt6tftqM95RpbanJd1WR2YQ6DEpBHR4Rq4fviU5SbphyQIBoeCtbvnbXXfU5jbQJ7yiS20+S7qcitQTCkEUGMNlw/fE/PNbtOSIFgwgl4u9fuOr+oM95UJbavJdils2MTYXBGB4Bq4fvil70tMXIcrvV7jKSna1+8qMtuo8F3jJeaz4SQxobq8ttUk+HWlfHqHLbVJD4di8EcwVI26T4HwBoPLuOGlGleVGW3S/A+AKhPvtFjVWlt0fw+AKRPuMjlBleVCW3TvA+AK5Ntqk96kXVJbdN8D4Ao022kT3rRWi7a3IfDsEjIaPtoch8AUmW4981S80DbVZD4AfPYnBoIEA0PF6msz26reYWGxhr0MSkEYt2o+ATlJumHJAgGh4Koed3UZ30hYKS1BMKQTWWEy4fv4D55rdpyRgJDx993T57aLO7CDVGdiKQRhhoZcP38CxxOpez4Pu6fPbVZ3jakEMuH7+EabPbS5/DtRn8QCpc9tBn8O1Oe3SPhweaFhs/pYonhgtpofw0ZcpyLrIAxSQc6YoAAABIWNF+GQlhwz+QhggHAcy1ofw0OUm6YckCAaHg/EFHPNbtOSBANDxY0fw4HKTdMOSBANDwfiDHPNbtOSBANDxsLBDHMW/Dxyk3TDkmXwcETkESGwWXD9/D7cXxIP8IGepx4oGC1+SIrR9/QgtIQg3jw2ZvGGSL8heE1rSlukZxB4ojjabguwdgaZIC9yyyyyyyyyyyynIod1AGiMp6vhIeasgN6yyyyyyyyyyyyyyyyyyyyyyyyyITQxwjQgDEaCFFrWCHkx0hyCIEhAuso8DyTYbv8AbJnYDDJWZmRxBhuKDM7gFZVQ9Dy0TNNAZwEC9SZbzFa9kbxQIQ6G5pEt6qkuDyM6YrSSBRUYrmcFMCx7gYncD2QxMOuKYGIn2xlBmd0ZrmHZkQQxgpz+i4B0QNukS3qqS4OjZTg5ymULt4GAN+ndAQhLyyLmFHt0GOYmLNBmd2Zb4S7lFDgCksyltUiW9VSXBvIEg+lASXcgBuxdhTn31knt+PXIWKDM7uDDzHaARuacwl9WaRLehGDAGh6cGN7muTuIAAYHAXOc8WARogAIgJ6LynPpftFRE9FFvl9Emv7wIaXLCNEIc2ERwI2wttBmbRGO4gAK/Er8SvxK/Er8SvxKBodutB8N0Q80U4CnBlCXhn5WA7I0BGS/Er8SvxK/Er8SvxK/Er8SvxK/Er8SvxK/Er8SvxK/Er8SgQsBjy3FKIOe+CyDYY9h+E0BsEwAcBcEIHy9AOcCJtTk1yJqKBtrMhq8USFGphGyiXB95KARWkCLUYVOkUQxGkxO2gzNrW2y0iC1PQKHQJrsKPgAX6CHZvG1gg/0awBtsWgGroFH8HycCN1gXX4pN6tixCYY/lJEMVpRPBWnLNiUEiwdb6kceQE0TO5p/RePCTFOhGgYBpnamNpIAaXBcwfY5vuzQZm1rbwiJbaeucEVhgHEOcwtjZZjmAOPbxujWkfUH2h6BQAHAWi5ihxTOQU26qjwUA1wimScQhiGHTbYsfkKGsW96DK+IfdrIITstDp39UclAHklFnZB+S0UGZta29LJQpVBDZBNbgbQx7Rgymjc2qVFuKEgZQ8nO0x4lwxwgTzU42dhhwXAHObh22qwc5mdEloItJbgf4aCDCCg0AtHbFBmbWtvizXGHUi72iADDBYU9WTtNxdseCWZyCe9OZm2iS0GGAEalsWe3meDBOau/AdmWiHMbWY4Ac1h8WwwgyG80GZta2+JgFaGgpuxb0w+1r8JczcBF5AA0krNTIZG01kU0H5SPpwYN9Td9oCAZCFqe5MUO3qgzNrW35IL+ie7WTaO24UFEaF+k24A8wr9J4NEAQOc8bTO8tyuQHdiPLJHYk71QZm1rb8xqXbq07WIX6IBkIWs4RAxOiCkJdpJmeDW1h6OUFo0w9A7Gu90GZta2/J237W0rXG+mCCDfQzKH3RCgFovoNEPlp4c45ZDIcHTmHNGjzaqHTW9qDM2tbfENzAFMlDxZvMB9p0odivWJM8PFJMRIzMQrQYbQSbvxbd9s+DmY4mJg/0QtFN1x43ugzNrW3xOiahueFaO6w4mQR/tCkbxhzdDyQFA4GJkyFofwVoMACdmnUPbg8GKflQMBIWqI497oMza1t6cacPqCCy6fh+IVoDmL2tG3gBJgeShdQVvDmbZMPgiKT3wgTTLyoFoBtZLC1b3QZm1rbwlOGwAMyJH8ejKZt4qG7iXgvV0JR1sJqc3MolrzHhDLmKzOmlrBIMPJtm90GZtHeIyWQbaggggghpw/Xslog4efu0bGKpHqCbx0vAgAADALY9vfX0R2hDSSXk3bfn6QfaHhFgDABaMnBzMGbII392NHhIAV7YebLbRSmOH1DPI3ugzO8A5tjMpDNfk/Nu2zbDTXoTf7BHO0xWpxHCBYXzHDADhObRvof7aYAYikc97oMzu4qcFM5AYlPBDF7jnduwfBLM5BPg+AfPtFGjhQBEDUCPbzPCjY48EHV6tF8jLw3ugzO7DjJ0YoJSBQXCkBdjgsDNJHBM1XgkltNZFPMcpP0OFXji9TwtmeO8v+m9UGZ3Qa2ZzgBzYIa3rFYSM0a2N5B3GhfpNuCPsKglz4WGCkDwUNZBdDAHWgSAB+cJeqMWKKeQw3mgzNqBX8t0JVZe1WXtVl7VZe1WXtVl7VZe0Hv4sEjgA200yaP3zQQiQbew3iVOJD9C2YFkGtfSMjKFHknHhdwUB5JEdR4tlbOBw6HMbzhySgzNrW3BGCkDwUN6QNAtSghZnXOtFhHNAeDdBjQQfTzKGVHCgFqcVA9JArSJZDLhg3EABgQ9MpAxBwoLZWtJta6Igkxwi+ioCsG/PlTHR4HI6tCuUGZta25JoOgMYuafF4EyxBztGeBZa5ci37sQkxWt5HGK0JK1ieQzTYDLL7eGo6k8hgKCCGh4tkmqv9kTRYGYMOCYON5gYHYZmQTIavqWnawZUFxCHjmDsygzNrW3RO6ggael9k1sLJKAYUBT8fph5i2N+fGiUBGwMTBkyFof0WgwAJtWQDrfXDjJABhn6RcHRjwGHI4JoEEYH8KZgUzZ9Drh4oHly5mAU0SBpc0yzUdw42Wf1TtAI+7eZZHLOxQZm1rbssxof7D9i1HEW1sKMpeKeQsgEmB5KD9RzfO3HZ2GR0fw6NSwowgjFBk9MFgznckZiiAajZKERto3zkpA2ix72epE9oQKKtmgvdAozgKHYXB/AOdNQZ/wmtO0oMza1t2Tfm6+jkn4QWd5FpoVktKzNugopvVsryhEzAyIgiUtNVmq59qufarn2q59qufarn2q59qufarn2q59qufarn2q59qufarn2q59qufarn2j20HcPNwW3+qFhJCL50H+u7hWa09GHPMlYKDM2tbeGLnjTOlD2CgAuIsjaATCDijp/BJ8dvNStAkh6hQAHAcTsBBS8AhCU2Y9lAKS01oDdIRl6ksapj3JmzQZm1rb0stxM9aR6sDDfgguvHUzGR4s2w3LZsevpQFxnRggFsNwC8loMAmYMIgd5MUQFTy0m1QZm1rb0hQJNPIIKYL+7yNqIh5B0uY4u2wE/PjYhQcOJeIhs0YcLwgZPM7T0CN4UDtUT4elnKB1xQZm1rb4uYSDoaEL0LFxBtQPO1Ww8X7YCgpA8tEzhhg0eydgGnAoe9uW1FeIw9Ly4AbJAL9UgvM1ekP6WHym3mRn6TeBpFx0RDEaTE3TJEOGwtECBAgQRZZGwwMXK/JBCytOUMItIECBAgYzwDEg9zghInviBAgQIECBAgQIECBAgQIECBAgQIECBAgPjgQYmMxJ/xV5G1YNbaCEIQtlyE1q5Ptg3osG0IQLA+rwRbgSX+yNe3hmDeHEkwXZlC41CISKMeYYG7GVKRiCbAQheQugYjjnwhC/NiB5G6BozAgiSE5IsghCEJTAYHW5BRcQwv2hCSesIuze3HYo64KXB8y4PcjcQzDmqZ9Ji8cymuOwbAHsIEqZ9J0vwQAd0upxU1QFzU1TPpNYHkL0xMgybgBMIfRkkASIcIuhlNFFmVCb3McSg6cc881UhNd0mewI0GcJqpn0uWplt3CEwUPPHlNci+HnMIU7Gxnnc6YtCE7mfaIpkqMlkqMlkqMkcRpyXO50Lyml4ORiAqZ9Iw3qEBMeYqOYQFDSAwR31GZk8cIV+R2UGa/nsSXS0ciNkEkyuj6YHUqDodZTVBqlEwnpHAps4cGYuqTPZVZ7SYSGDAobmAuYwBxQCEYfsC50xaEXwmhebBwLC0RWtEoxHMRauECvyOygzX09hM0wA0oDZJPPxKLQw8k+tMLmbkBC0MAQWIGDUYnFPHht56MW0NBQIt0JinF3YF1SZ7KrOwckGLsEAexFyaYtCFkCkEr8wvzCeAtEIwN1oXnacA2CKppo/QCAAMDgE4YMvCCvyOygzXk3UAzC/OrTkCI/cSQgPKNaMRzN0+mA14EYOcm6Y3nOuxCUbICIIMZ7DghFtDCLmkz2VWdgexaRnBqAOMe5Af250xaEIeIv0BBfql+qTJOFrQRdaF5RABheM1+dRdvKggOgAsGkkc7hFX5HZQZryZguYJPYKnfaFHp03dIXpmmSaV3QxlwZqsB2TVJ2zhrYaaaJI0VTqADFyUmeyqz2ZF8aoJYGdvQYNqAwCILaHFkudMWhF8JoXlEnOEMIKU77UXPCIBJGmaHukoc3CrYeEa/I7KDNfz2wwzztdEwqHXcuqJcNaMDcP4uzjBAyNImQTQBjnLBYjgXW/1PItDiO1zSZ7Cd5Kc9gzgkWcALRUOyYC/mutMWhCaB2afl1+XX5dCAAAMPIXOhebB0Gp3t2RrSPdgH9mPCGFXpiOqqn2iswhpJ5Ju8t780Q2ZTQAIPXaftDWMQqp9rHrSxPW4IEeiJW+yCSphGCO9lzdmNZM6KqfajcFJg0lhByVU+1VPtVT7TrGVjbwFkFVPtVT7VU+1VPtVT7WPXpietyCNDCTN9kCRDCMEcm2AIKQAH7RgjUBIz3/AO5P/9oADAMBAAIAAwAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+KAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+IBYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+IABcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+IAABIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+IAAABYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+IAAAACsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB+IAAAAACYAAAABQgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOIAAAAAADAAAAACrcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADkAAAAAIDcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABUAAAAAAABwAAAAAMADMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAAAAAAIk0AAAAAoAAGoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQAAAAYhEFEAAAAAINMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAUAAAWEAADAAAAAAEYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB8gAAAAAAvMAAACmQAAAAAhcAAAABAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABaKsAAABMCgAAAAAmkAAAACEMAAAAANMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABcAoAAAAUAsAAABQgIAAAACkQAAAAAsBMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYAoAAAAICMAAAAWAsAAAAAAEAAAAAIABMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMCMAAAAAAoAAAAACoAAAAANQAAAACsAABYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABMCoAAABMCsAAAAACMAAAAApAAAAACAAANsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABYCsAAABYAoAAAAcAMAAAACpUAAAAAgANsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABcAgAAABcCsAAABYCIAAAACMAAAAACENsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAO2AAAAAcAIAAABYAMAAAAAoUAAAAAJMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKoAAABAAoAAAAMCsAAAACMUAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABcAkAAAAYCAAAAACsYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABACEAAABMCkAAAAAoMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAABUCgAAAAAFIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAUAkAAAAQAAAAAAAlYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQCgAAABUAEAAAAChcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABG2EAAABQAoAAAAQKgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKgAAABECAAAABQIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAnMCsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABI0AAsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAK0AoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKqAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQQAwwwAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAjhAAAABACgAAAAAAAAAAADAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAADQgAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAhBAAQQAACwAAAAAABCgQgAAQhAAAAAAAABQAABgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAiAAAAAAAyAAAAAAAAAAABAAAAAAAAAAAAARgAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAwAAAAAAACAAAAAAAAAAAAAAgAAQAAAAAAAAgAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAQAAAAAAAAAAAAAAAAAAAAAABQAAAAAAAAABAAASgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQABQAAAAAAAAAAAAAAAAAAAAAAAQABQAAAAABiAADgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABwAAAAAAAAAAAAAAAAAAAAAAAAASAADAAAAABAAACgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABwABAAAAAAAAAAAAAAAAAAAAQAhgAAAgAAAACgABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAATgAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABQABCAAAAAAAAAAAAAAAAAAAAAAAyAAAAACgAASAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAABQAAAAAAAAAAAAAADDDDAAABAAAAABwAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAgAAQAAAAABSCwAAAAAAAABCgACQAABCAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACgAAACwggiiAAAgAAAAAAAAAQABCABSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABCQAAAAAAAAABiAAAAAAAAAABAACABgAAAAAAAA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"

st.markdown(f'''
<div style="text-align:center;padding:32px 0 24px;">
  <img src="data:image/jpeg;base64,{{LOGO_B64}}" style="width:120px;height:120px;border-radius:16px;object-fit:cover;margin-bottom:16px;display:block;margin-left:auto;margin-right:auto;"/>
  <div style="font-family:Inter,sans-serif;font-size:22px;font-weight:300;color:#94a3b8;letter-spacing:0.1em;text-transform:uppercase;">CRZ Trader</div>
  <div style="font-size:12px;color:#64748b;margin-top:6px;letter-spacing:0.06em;">Analizador de Historial MT5</div>
</div>
'''.format(LOGO_B64=LOGO_B64), unsafe_allow_html=True)

# ── Noticias (independiente del historial) ───────────────────────────────────

@st.cache_data(ttl=900)
def fetch_news(week_offset=0):
    """Fetch economic calendar - tries multiple sources"""
    from datetime import datetime, timedelta
    today = datetime.now()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    date_from = monday.strftime("%Y-%m-%d")
    date_to   = (monday + timedelta(days=6)).strftime("%Y-%m-%d")

    # Try 1: ForexFactory
    try:
        suffix = "thisweek" if week_offset == 0 else "nextweek"
        r = requests.get(
            f"https://nfs.faireconomy.media/ff_calendar_{suffix}.json",
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        if r.status_code == 200 and r.json():
            return r.json(), date_from, date_to
    except:
        pass

    # Try 2: FMP Economic Calendar (free tier)
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/economic_calendar?from={date_from}&to={date_to}&apikey=demo",
            timeout=6
        )
        if r.status_code == 200:
            raw = r.json()
            # normalize to FF format
            events = []
            for e in raw:
                events.append({
                    "date":     e.get("date",""),
                    "time":     e.get("date","")[-8:-3] if e.get("date","") else "",
                    "country":  e.get("country",""),
                    "impact":   {"High":"High","Medium":"Medium","Low":"Low"}.get(e.get("impact",""),"Low"),
                    "title":    e.get("event",""),
                    "forecast": e.get("estimate",""),
                    "previous": e.get("previous",""),
                    "actual":   e.get("actual",""),
                })
            if events:
                return events, date_from, date_to
    except:
        pass

    return None, date_from, date_to


uploaded = st.file_uploader(
    "Arrastra aquí el archivo .xlsx del alumno",
    type=["xlsx", "xls"],
    label_visibility="collapsed"
)

tab_news, tab_analysis = st.tabs(["📰 Noticias & Calendario", "📊 Análisis de Historial"])

with tab_news:
    # Header
    col_n1, col_n2 = st.columns([3,1])
    with col_n1:
        st.markdown("### 📰 Calendario Económico")
        st.caption("Foco en NAS100 · SP500 · XAU (Oro) · XAG (Plata) · Actualización cada 30 min")

    # Asset quick reference
    asset_cols = st.columns(4)
    assets = [
        ("📈 NAS100", "#3b82f6", "Nasdaq 100 — Tecnología USA\nAfectado: Fed, NFP, CPI, Earnings"),
        ("📈 SP500",  "#8b5cf6", "S&P 500 — Índice amplio USA\nAfectado: Fed, NFP, CPI, GDP"),
        ("🥇 XAU",   "#f59e0b", "Oro — Refugio seguro\nAfectado: Fed, CPI, DXY, Geopolítica"),
        ("🥈 XAG",   "#94a3b8", "Plata — Metal industrial\nAfectado: Fed, CPI, DXY, Industria"),
    ]
    for col, (name, color, desc) in zip(asset_cols, assets):
        col.markdown(f"""
    <div style='background:#161c28;border:1px solid #2a3a52;border-top:3px solid {color};
     border-radius:4px;padding:10px 12px;margin-bottom:8px;'>
      <div style='font-size:14px;font-weight:700;color:{color};letter-spacing:0.03em;'>{name}</div>
      <div style='font-size:11px;color:#94a3b8;margin-top:6px;white-space:pre-line;line-height:1.7;font-weight:400;'>{desc}</div>
    </div>""", unsafe_allow_html=True)
    with col_n2:
        if st.button("🔄 Actualizar noticias", key="refresh_news"):
            st.cache_data.clear()
            st.rerun()

    st.divider()

    # Impact colors
    impact_color = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#64748b", "Holiday": "#3b82f6"}
    impact_emoji = {"High": "🔴", "Medium": "🟡", "Low": "⚪", "Holiday": "🔵"}

    ff_data, date_from, date_to           = fetch_news(0)
    ff_data_next, date_from_next, date_to_next = fetch_news(1)

    def parse_events(raw):
        events = []
        for e in raw:
            events.append({
                "date":     e.get("date", ""),
                "time":     e.get("time", ""),
                "currency": e.get("country", ""),
                "impact":   e.get("impact", ""),
                "event":    e.get("title", ""),
                "forecast": e.get("forecast", ""),
                "previous": e.get("previous", ""),
                "actual":   e.get("actual", ""),
            })
        df = pd.DataFrame(events)
        df["dt"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["dt"]).sort_values("dt")
        return df

    def render_week(raw_data, label):
        if not raw_data:
            st.info(f"📡 No se pudieron cargar los eventos de {label}.")
            return

        df_news = parse_events(raw_data)

        # Filters
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            impact_filter = st.multiselect(
                "Impacto", ["High","Medium","Low"],
                default=["High","Medium"], key=f"imp_{label}"
            )
        with col_f2:
            currencies = sorted(df_news["currency"].unique().tolist())
            currency_filter = st.multiselect(
                "Divisa", currencies,
                default=[c for c in ["USD","EUR","GBP","JPY","XAU","XAG"] if c in currencies],
                key=f"cur_{label}"
            )
        with col_f3:
            days = sorted(df_news["dt"].dt.strftime("%A %d/%m").unique().tolist())
            day_filter = st.multiselect("Día", days, default=days, key=f"day_{label}")

        mask = df_news["impact"].isin(impact_filter) if impact_filter else df_news["impact"].notna()
        if currency_filter:
            mask &= df_news["currency"].isin(currency_filter)
        if day_filter:
            mask &= df_news["dt"].dt.strftime("%A %d/%m").isin(day_filter)

        df_filtered = df_news[mask]
        st.markdown(f"**{len(df_filtered)} eventos** encontrados")
        st.markdown("")

        impact_es = {"High":"ALTO","Medium":"MEDIO","Low":"BAJO","Holiday":"FESTIVO"}
        day_es_map = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles",
                      "Thursday":"Jueves","Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}

        for day, group in df_filtered.groupby(df_filtered["dt"].dt.strftime("%A %d/%m")):
            day_translated = day
            for en, es in day_es_map.items():
                day_translated = day_translated.replace(en, es)
            st.markdown(f"#### 📅 {day_translated.upper()}")

            for _, row in group.iterrows():
                imp   = row["impact"]
                color = impact_color.get(imp, "#64748b")
                emoji = impact_emoji.get(imp, "⚪")
                imp_es_str = impact_es.get(imp, imp)
                prev  = str(row["previous"]) if row["previous"] else "—"
                fore  = str(row["forecast"]) if row["forecast"] else "—"
                actual_html = ("&nbsp;|&nbsp;<b style='color:#22c55e;'>Real: " + str(row["actual"]) + "</b>") if row["actual"] else ""

                card_html = (
                    "<div style='background:#161c28;border:1px solid #2a3a52;border-left:3px solid " + color + ";border-radius:4px;padding:12px 16px;margin-bottom:8px;'>"
                    "<div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;'>"
                    "<div>"
                    "<span style='font-size:11px;font-weight:700;color:" + color + ";letter-spacing:0.08em;'>" + emoji + " " + imp_es_str + " &nbsp;·&nbsp; </span>"
                    "<span style='font-size:11px;font-weight:600;color:#cbd5e1;'>" + str(row["currency"]) + " &nbsp;·&nbsp; " + str(row["time"]) + "</span>"
                    "</div>"
                    "<div style='font-size:10px;color:#94a3b8;'>"
                    "Anterior: " + prev + " &nbsp;|&nbsp; Previsión: " + fore + actual_html +
                    "</div></div>"
                    "<div style='font-size:14px;color:#f1f5f9;font-weight:600;margin-top:6px;'>" + str(row["event"]) + "</div>"
                    "</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)
            st.markdown("")

    # Week selector tabs
    week1, week2 = st.tabs(["📅 Esta semana", "📅 Próxima semana"])
    with week1:
        if ff_data:
            st.caption(f"Semana del {date_from} al {date_to}")
            render_week(ff_data, "esta_semana")
        else:
            st.info("📡 No se pudieron cargar los eventos en tiempo real. Mostrando eventos clave de referencia.")
            key_events = [
                ("🔴 ALTO",  "NAS100 · SP500", "Fed Interest Rate Decision — Mayor impacto en índices USA", "Cada 6 semanas · 20:00 CET"),
                ("🔴 ALTO",  "NAS100 · SP500", "Non-Farm Payrolls (NFP) — Mueve fuerte el Nasdaq y SP500", "Primer viernes del mes · 14:30 CET"),
                ("🔴 ALTO",  "NAS100 · SP500", "CPI USA (Inflación) — Clave para la Fed y los índices", "Día 10-15 del mes · 14:30 CET"),
                ("🔴 ALTO",  "XAU · XAG",      "Fed Decision / CPI — Oro y Plata reaccionan fuerte al USD", "Mismo timing que eventos Fed"),
                ("🔴 ALTO",  "XAU · XAG",      "FOMC Minutes — Impacto directo en metales preciosos", "3 semanas tras reunión Fed · 20:00 CET"),
                ("🟡 MEDIO", "NAS100 · SP500", "ISM Manufacturing PMI — Indicador de salud económica USA", "Primer día hábil del mes · 16:00 CET"),
                ("🟡 MEDIO", "NAS100 · SP500", "Initial Jobless Claims — Datos semanales de empleo USA", "Cada jueves · 14:30 CET"),
                ("🟡 MEDIO", "NAS100 · SP500", "Retail Sales USA — Consumo e impacto en tecnológicas", "Día 15 del mes · 14:30 CET"),
                ("🟡 MEDIO", "XAU · XAG",      "DXY (Índice Dólar) — Correlación inversa con metales", "Seguimiento continuo"),
                ("🟡 MEDIO", "NAS100 · SP500", "Resultados trimestrales — AAPL, MSFT, NVDA, GOOGL, AMZN", "Enero, Abril, Julio, Octubre"),
            ]
            for imp, currency, event, timing in key_events:
                color = "#ef4444" if "ALTO" in imp else "#f59e0b"
                card_html = (
                    "<div style='background:#161c28;border:1px solid #2a3a52;border-left:3px solid " + color + ";border-radius:4px;padding:12px 16px;margin-bottom:8px;'>"
                    "<span style='font-size:11px;font-weight:700;color:" + color + ";letter-spacing:0.05em;'>" + imp + " &nbsp;·&nbsp; " + currency + "</span>"
                    "<div style='font-size:14px;color:#f1f5f9;font-weight:600;margin-top:5px;'>" + event + "</div>"
                    "<div style='font-size:11px;color:#94a3b8;margin-top:4px;'>" + timing + "</div>"
                    "</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)

    with week2:
        if ff_data_next:
            st.caption(f"Semana del {date_from_next} al {date_to_next}")
            render_week(ff_data_next, "proxima_semana")
        else:
            st.info("📡 Los datos de la próxima semana aún no están disponibles. Prueba el viernes o sábado.")

# ── TABS — always visible ─────────────────────────────────────────────────────

with tab_analysis:
    if not uploaded:
        st.markdown("""
<div style='text-align:center;padding:60px 20px;'>
  <div style='font-size:48px;margin-bottom:16px;'>📂</div>
  <div style='font-size:18px;font-weight:300;color:#94a3b8;margin-bottom:8px;'>Sube el historial para ver el análisis</div>
  <div style='font-size:13px;color:#475569;'>MT5 → Historial → Click derecho → Guardar como informe (.xlsx)</div>
</div>""", unsafe_allow_html=True)
    else:
        with st.spinner("Procesando historial..."):
            try:
                data = parse_mt5(uploaded)
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo: {e}")
                st.stop()

        df    = data["df"]
        stats = data["stats"]
        meta  = data["meta"]

        # ── Alumno bar ────────────────────────────────────────────────────────
        st.markdown(f"""
<div class="alumno-bar">
  <div class="alumno-name">{meta['alumno'] or 'Alumno'}</div>
  <div class="alumno-meta">{meta['cuenta']} · {meta['empresa']} · {meta['fecha']} · {len(df)} operaciones</div>
</div>
""", unsafe_allow_html=True)

        # ── KPIs ──────────────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Capital & Resultado</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Balance inicial", f"${stats['balance_ini']:,.2f}")
        c2.metric("Balance actual",  f"${stats['balance']:,.2f}")
        ret = stats["pnl_net"] / stats["balance_ini"] * 100 if stats["balance_ini"] else 0
        c3.metric("Beneficio neto",  f"${stats['pnl_net']:+,.2f}", f"{ret:+.2f}%")
        c4.metric("Drawdown máximo", stats["max_dd"])

        st.markdown('<div class="section-label">Estadísticas de trading</div>', unsafe_allow_html=True)
        wins = df["win"].sum(); losses = (~df["win"]).sum()
        wr = wins / len(df) * 100 if len(df) else 0
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total ops",        len(df))
        c2.metric("Win rate",         f"{wr:.1f}%", f"{int(wins)}G · {int(losses)}P")
        c3.metric("Factor beneficio", f"{stats['pfactor']:.3f}")
        c4.metric("Mejor op.",        f"${stats['best']:+,.2f}")
        c5.metric("Peor op.",         f"${stats['worst']:,.2f}")
        c6.metric("Expectativa",      f"${stats['expected']:+,.2f}" if stats['expected'] else f"${df['pnl_net'].mean():+,.2f}")

        st.markdown('<div class="section-label">Long vs Short · Costes</div>', unsafe_allow_html=True)
        longs  = df[df.type=="buy"];  shorts = df[df.type=="sell"]
        lwr = longs["win"].mean()*100  if len(longs)  else 0
        swr = shorts["win"].mean()*100 if len(shorts) else 0
        tc = df["comm"].sum(); ts = df["swap"].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Long (buy)",    len(longs),  f"WR {lwr:.1f}% · ${longs['pnl_net'].sum():+,.2f}")
        c2.metric("Short (sell)",  len(shorts), f"WR {swr:.1f}% · ${shorts['pnl_net'].sum():+,.2f}")
        c3.metric("Comisiones + Swap", f"${tc+ts:,.2f}", f"Comm ${tc:.2f} · Swap ${ts:.2f}")
        c4.metric("Promedio ganadora / perdedora", f"${stats['avg_win']:,.2f}", f"Pérd: ${stats['avg_loss']:,.2f}")

        st.divider()

        # ── Sub-tabs análisis ─────────────────────────────────────────────────
        tab_ops, tab_sym, tab_mon, tab_cal, tab_charts = st.tabs([
            "📋 Operaciones", "📈 Por símbolo", "📅 Por mes", "🗓️ Calendario", "📊 Gráficas"
        ])

        # ── Tab: Operaciones ──────────────────────────────────────────────────────────
        with tab_ops:
            display = df[["open","symbol","type","volume","p_in","close","p_out","comm","swap","profit","pnl_net"]].copy()
            display.columns = ["Apertura","Símbolo","Tipo","Vol","Entrada","Cierre","Salida","Comisión","Swap","Beneficio","PnL neto"]

            def color_profit(val):
                if isinstance(val, (int, float)):
                    return f"color: {'#22c55e' if val > 0 else '#ef4444' if val < 0 else '#94a3b8'}"
                return ""

            st.dataframe(
                display.style
                    .map(color_profit, subset=["Beneficio", "PnL neto"])
                    .format({
                        "Entrada": "{:.2f}", "Salida": "{:.2f}",
                        "Comisión": "{:.2f}", "Swap": "{:.2f}",
                        "Beneficio": "{:+.2f}", "PnL neto": "{:+.2f}"
                    }),
                use_container_width=True, height=400
            )

        # ── Tab: Por símbolo ──────────────────────────────────────────────────────────
        with tab_sym:
            sym_g = df.groupby("symbol").agg(
                Operaciones=("profit", "count"),
                Ganadoras=("win", "sum"),
                PnL_neto=("pnl_net", "sum"),
                Gan_bruta=("profit", lambda x: x[x>0].sum()),
                Perd_bruta=("profit", lambda x: x[x<0].sum()),
                Mejor=("profit", "max"),
                Peor=("profit", "min"),
            ).reset_index()
            sym_g["Perdedoras"] = sym_g["Operaciones"] - sym_g["Ganadoras"]
            sym_g["Win_rate"] = sym_g["Ganadoras"] / sym_g["Operaciones"] * 100
            sym_g["Factor"] = sym_g["Gan_bruta"] / sym_g["Perd_bruta"].abs().replace(0, np.nan)
            sym_g = sym_g.sort_values("PnL_neto", ascending=False)
            sym_g.columns = ["Símbolo","Ops","Ganadoras","PnL Neto","Gan. Bruta","Pérd. Bruta","Mejor","Peor","Perdedoras","Win Rate %","Factor Ben."]

            st.dataframe(
                sym_g[["Símbolo","Ops","Ganadoras","Perdedoras","Win Rate %","PnL Neto","Gan. Bruta","Pérd. Bruta","Factor Ben.","Mejor","Peor"]]
                .style.map(color_profit, subset=["PnL Neto","Gan. Bruta","Pérd. Bruta","Mejor","Peor"])
                .format({"Win Rate %":"{:.1f}%","PnL Neto":"{:+.2f}","Gan. Bruta":"{:+.2f}",
                         "Pérd. Bruta":"{:.2f}","Factor Ben.":"{:.2f}","Mejor":"{:+.2f}","Peor":"{:.2f}"}),
                use_container_width=True
            )

        # ── Tab: Por mes ──────────────────────────────────────────────────────────────
        with tab_mon:
            mon_g = df.groupby("month").agg(
                Operaciones=("profit","count"),
                Ganadoras=("win","sum"),
                PnL_neto=("pnl_net","sum"),
                Mejor=("profit","max"),
                Peor=("profit","min"),
            ).reset_index()
            mon_g["Perdedoras"] = mon_g["Operaciones"] - mon_g["Ganadoras"]
            mon_g["Win Rate %"] = mon_g["Ganadoras"] / mon_g["Operaciones"] * 100
            mon_g.columns = ["Mes","Ops","Ganadoras","PnL Neto","Mejor","Peor","Perdedoras","Win Rate %"]

            st.dataframe(
                mon_g[["Mes","Ops","Ganadoras","Perdedoras","Win Rate %","PnL Neto","Mejor","Peor"]]
                .style.map(color_profit, subset=["PnL Neto","Mejor","Peor"])
                .format({"Win Rate %":"{:.1f}%","PnL Neto":"{:+.2f}","Mejor":"{:+.2f}","Peor":"{:.2f}"}),
                use_container_width=True
            )

        # ── Tab: Calendario ───────────────────────────────────────────────────────────
        with tab_cal:
            # Month selector
            months_avail = sorted(df["month"].unique())
            sel_month = st.selectbox("Mes", months_avail,
                                      index=len(months_avail)-1,
                                      format_func=lambda m: datetime.strptime(m, "%Y-%m").strftime("%B %Y")
                                      if "-" in m else m)

            # Filter by month
            mask = df["month"] == sel_month
            dm = df[mask]

            # Monthly summary
            m_pnl = dm["pnl_net"].sum()
            m_ops = len(dm)
            daily = dm.groupby("close_date")["pnl_net"].sum()
            win_days  = (daily > 0).sum()
            loss_days = (daily < 0).sum()

            c1,c2,c3,c4,c5 = st.columns(5)
            color = GREEN if m_pnl >= 0 else RED
            c1.metric("PnL del mes", f"${m_pnl:+,.2f}")
            c2.metric("Operaciones", m_ops)
            c3.metric("Días operados", len(daily))
            c4.metric("Días ganadores", int(win_days))
            c5.metric("Días perdedores", int(loss_days))

            st.markdown("---")

            # Build calendar using Streamlit columns
            try:
                if "-" in sel_month:
                    yr, mo = map(int, sel_month.split("-"))
                else:
                    yr, mo = map(int, sel_month.split("."))
            except:
                yr, mo = date.today().year, date.today().month

            cal_data = {}
            for d_date, pnl in daily.items():
                day_num = d_date.day if hasattr(d_date, 'day') else int(str(d_date)[-2:])
                cal_data[day_num] = pnl

            ops_by_day = dm.groupby("close_date").agg(ops=("profit","count"), wins=("win","sum"))
            ops_data = {}
            for d_date, row in ops_by_day.iterrows():
                day_num = d_date.day if hasattr(d_date, 'day') else int(str(d_date)[-2:])
                ops_data[day_num] = {"ops": int(row["ops"]), "wins": int(row["wins"])}

            days_in_month = calendar.monthrange(yr, mo)[1]
            first_weekday = calendar.monthrange(yr, mo)[0]

            # Header row
            day_names = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
            cols = st.columns(7)
            for i, d in enumerate(day_names):
                cols[i].markdown(f"<div style='text-align:center;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;padding:4px 0'>{d}</div>", unsafe_allow_html=True)

            # Build all cells
            all_cells = [None] * first_weekday
            for day in range(1, days_in_month + 1):
                all_cells.append(day)
            while len(all_cells) % 7 != 0:
                all_cells.append(None)

            # Render week by week
            for week_start in range(0, len(all_cells), 7):
                week = all_cells[week_start:week_start+7]
                cols = st.columns(7)
                for i, day in enumerate(week):
                    with cols[i]:
                        if day is None:
                            st.markdown("<div style='min-height:86px;'></div>", unsafe_allow_html=True)
                        else:
                            pnl = cal_data.get(day)
                            info = ops_data.get(day, {})
                            if pnl is not None:
                                color = "#22c55e" if pnl > 0 else "#ef4444"
                                bg = "rgba(34,197,94,0.08)" if pnl > 0 else "rgba(239,68,68,0.08)"
                                sign = "+" if pnl >= 0 else ""
                                ops_count = info.get("ops", 0)
                                st.markdown(f"""
                                <div style='background:{bg};
                                     border:1.5px solid {color};
                                     border-radius:6px;
                                     padding:10px 8px 8px;
                                     min-height:86px;
                                     box-shadow:0 0 0 0.5px rgba(0,0,0,0.3);'>
                                  <div style='font-size:12px;font-weight:500;color:#94a3b8;margin-bottom:6px;'>{day}</div>
                                  <div style='font-size:14px;font-weight:600;color:{color};line-height:1.2;'>{sign}{pnl:,.2f}$</div>
                                  <div style='font-size:10px;color:#64748b;margin-top:4px;'>{ops_count} op{"s" if ops_count>1 else ""}</div>
                                </div>""", unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div style='background:rgba(34,197,94,0.05);
                                     border:1px solid rgba(34,197,94,0.2);
                                     border-radius:6px;
                                     padding:10px 8px 8px;
                                     min-height:86px;'>
                                  <div style='font-size:12px;font-weight:400;color:#4ade80;'>{day}</div>
                                  <div style='font-size:10px;color:rgba(74,222,128,0.4);margin-top:4px;'>—</div>
                                </div>""", unsafe_allow_html=True)

        # ── Tab: Gráficas ─────────────────────────────────────────────────────────────
        with tab_charts:
            col1, col2 = st.columns(2)

            # ── Equity curve ─────────────────────────────────────────────────────────
            with col1:
                st.markdown("**Curva de equity acumulada**")
                sorted_df = df.sort_values("close_dt").copy()
                sorted_df["equity"] = stats["balance_ini"] + sorted_df["pnl_net"].cumsum()
                eq_color = GREEN if stats["pnl_net"] >= 0 else RED

                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(
                    x=list(range(len(sorted_df)+1)),
                    y=[stats["balance_ini"]] + sorted_df["equity"].tolist(),
                    mode="lines",
                    line=dict(color=eq_color, width=2),
                    fill="tozeroy",
                    fillcolor=f"rgba({'34,197,94' if stats['pnl_net']>=0 else '239,68,68'},0.08)",
                    hovertemplate="Op #%{x}<br>Balance: $%{y:,.2f}<extra></extra>"
                ))
                fig_eq.update_layout(**LAYOUT, height=260)
                fig_eq.update_xaxes(title_text="Operación #")
                fig_eq.update_yaxes(tickprefix="$")
                st.plotly_chart(fig_eq, use_container_width=True)

            # ── Daily PnL ─────────────────────────────────────────────────────────────
            with col2:
                st.markdown("**PnL diario**")
                daily_pnl = df.groupby("close_date")["pnl_net"].sum().reset_index()
                daily_pnl.columns = ["date", "pnl"]
                daily_pnl["color"] = daily_pnl["pnl"].apply(lambda v: GREEN if v >= 0 else RED)

                fig_d = go.Figure()
                fig_d.add_trace(go.Bar(
                    x=daily_pnl["date"].astype(str),
                    y=daily_pnl["pnl"],
                    marker_color=daily_pnl["color"],
                    hovertemplate="%{x}<br>PnL: $%{y:+,.2f}<extra></extra>"
                ))
                fig_d.update_layout(**LAYOUT, height=260)
                fig_d.update_yaxes(tickprefix="$")
                st.plotly_chart(fig_d, use_container_width=True)

            col3, col4 = st.columns(2)

            # ── PnL por símbolo ───────────────────────────────────────────────────────
            with col3:
                st.markdown("**PnL neto por símbolo**")
                sym_pnl = df.groupby("symbol")["pnl_net"].sum().sort_values()
                colors_sym = [GREEN if v >= 0 else RED for v in sym_pnl.values]

                fig_s = go.Figure()
                fig_s.add_trace(go.Bar(
                    x=sym_pnl.values, y=sym_pnl.index,
                    orientation="h",
                    marker_color=colors_sym,
                    hovertemplate="%{y}: $%{x:+,.2f}<extra></extra>"
                ))
                fig_s.update_layout(**LAYOUT, height=260)
                fig_s.update_xaxes(tickprefix="$")
                st.plotly_chart(fig_s, use_container_width=True)

            # ── Distribución ──────────────────────────────────────────────────────────
            with col4:
                st.markdown("**Distribución de resultados**")
                profits = df["profit"].values
                mn, mx = profits.min(), profits.max()
                bins = np.linspace(mn, mx, 12)
                counts, edges = np.histogram(profits, bins=bins)
                colors_dist = [GREEN if (edges[i]+edges[i+1])/2 >= 0 else RED for i in range(len(counts))]
                labels = [f"{edges[i]:+.0f}→{edges[i+1]:+.0f}" for i in range(len(counts))]

                fig_dist = go.Figure()
                fig_dist.add_trace(go.Bar(
                    x=labels, y=counts,
                    marker_color=colors_dist,
                    hovertemplate="%{x}<br>%{y} operaciones<extra></extra>"
                ))
                fig_dist.update_layout(**LAYOUT, height=260)
                fig_dist.update_yaxes(title_text="Operaciones")
                st.plotly_chart(fig_dist, use_container_width=True)

            # ── Win rate por hora ─────────────────────────────────────────────────────
            st.markdown("**Win rate por hora UTC (hora de cierre)**")
            hr_g = df.groupby("hour").agg(
                ops=("profit","count"),
                wins=("win","sum"),
                pnl=("pnl_net","sum")
            ).reindex(range(24), fill_value=0).reset_index()
            hr_g["wr"] = hr_g["wins"] / hr_g["ops"].replace(0, np.nan) * 100
            hr_g["wr"] = hr_g["wr"].fillna(0)
            hr_colors = [GREEN if w >= 55 else RED if w < 40 else MUTED for w in hr_g["wr"]]

            fig_hr = go.Figure()
            fig_hr.add_trace(go.Bar(
                x=[f"{h:02d}h" for h in hr_g["hour"]],
                y=hr_g["wr"],
                marker_color=hr_colors,
                customdata=np.stack([hr_g["ops"], hr_g["pnl"]], axis=-1),
                hovertemplate="%{x}<br>WR: %{y:.1f}%<br>Ops: %{customdata[0]}<br>PnL: $%{customdata[1]:+,.2f}<extra></extra>"
            ))
            fig_hr.add_hline(y=50, line_dash="dash", line_color=MUTED, opacity=0.5)
            fig_hr.update_layout(**LAYOUT, height=220)
            fig_hr.update_yaxes(ticksuffix="%", range=[0,105])
            st.plotly_chart(fig_hr, use_container_width=True)

# ── Download ──────────────────────────────────────────────────────────────────
    st.divider()
    col_dl1, col_dl2 = st.columns([1,4])
    with col_dl1:
        csv = df[["open","symbol","type","volume","p_in","close","p_out","comm","swap","profit","pnl_net"]].to_csv(index=False)
        st.download_button(
            "⬇ Descargar CSV",
            data=csv,
            file_name=f"MT5_{meta['alumno'].replace(' ','_')}.csv",
            mime="text/csv"
        )
