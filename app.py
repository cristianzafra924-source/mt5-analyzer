import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import calendar
from datetime import datetime, date
import numpy as np

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MT5 Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Dark theme overrides */
.stApp { background-color: #0a0c10; }

/* Metric cards */
div[data-testid="metric-container"] {
    background: #111318;
    border: 1px solid #1e2330;
    border-radius: 12px;
    padding: 16px;
}
div[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 12px !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace;
    font-size: 24px !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #111318;
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    color: #64748b;
    font-size: 13px;
}
.stTabs [aria-selected="true"] {
    background: #1e2330 !important;
    color: #60a5fa !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #111318;
    border: 1.5px dashed #252b38;
    border-radius: 16px;
    padding: 20px;
}

/* Dataframe */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* Divider */
hr { border-color: #1e2330; }

/* Header */
.main-header {
    font-family: 'Syne', sans-serif;
    font-size: 32px; font-weight: 800;
    color: #f1f5f9; letter-spacing: -0.5px;
    margin-bottom: 4px;
}
.main-sub { color: #64748b; font-size: 14px; margin-bottom: 32px; }

.section-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: #64748b; margin: 24px 0 12px;
}

.alumno-bar {
    background: #111318; border: 1px solid #1e2330;
    border-radius: 12px; padding: 16px 20px; margin-bottom: 24px;
}
.alumno-name { font-size: 20px; font-weight: 700; color: #f1f5f9; }
.alumno-meta { font-size: 13px; color: #94a3b8; margin-top: 4px; }
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
st.markdown('<div class="main-header">📊 MT5 Analyzer</div>', unsafe_allow_html=True)
st.markdown('<div class="main-sub">Carga el historial .xlsx exportado desde MetaTrader 5</div>', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Arrastra aquí el archivo .xlsx del alumno",
    type=["xlsx", "xls"],
    label_visibility="collapsed"
)

if not uploaded:
    st.info("⬆️  Sube el historial exportado desde MT5 → Historial → Guardar como informe (.xlsx)")
    st.stop()

# ── Parse ─────────────────────────────────────────────────────────────────────
with st.spinner("Procesando historial..."):
    try:
        data = parse_mt5(uploaded)
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
        st.stop()

df    = data["df"]
stats = data["stats"]
meta  = data["meta"]

# ── Alumno bar ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="alumno-bar">
  <div class="alumno-name">{meta['alumno'] or 'Alumno'}</div>
  <div class="alumno-meta">{meta['cuenta']} · {meta['empresa']} · {meta['fecha']} · {len(df)} operaciones</div>
</div>
""", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
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
c1.metric("Total ops",      len(df))
c2.metric("Win rate",       f"{wr:.1f}%",       f"{int(wins)}G · {int(losses)}P")
c3.metric("Factor beneficio", f"{stats['pfactor']:.3f}")
c4.metric("Mejor op.",      f"${stats['best']:+,.2f}")
c5.metric("Peor op.",       f"${stats['worst']:,.2f}")
c6.metric("Expectativa",    f"${stats['expected']:+,.2f}" if stats['expected'] else f"${df['pnl_net'].mean():+,.2f}")

st.markdown('<div class="section-label">Long vs Short · Costes</div>', unsafe_allow_html=True)
longs  = df[df.type=="buy"];  shorts = df[df.type=="sell"]
lwr = longs["win"].mean()*100 if len(longs) else 0
swr = shorts["win"].mean()*100 if len(shorts) else 0
tc = df["comm"].sum(); ts = df["swap"].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Long (buy)",    len(longs),  f"WR {lwr:.1f}% · ${longs['pnl_net'].sum():+,.2f}")
c2.metric("Short (sell)",  len(shorts), f"WR {swr:.1f}% · ${shorts['pnl_net'].sum():+,.2f}")
c3.metric("Comisiones + Swap", f"${tc+ts:,.2f}", f"Comm ${tc:.2f} · Swap ${ts:.2f}")
c4.metric("Promedio ganadora / perdedora",
    f"${stats['avg_win']:,.2f}", f"Pérd: ${stats['avg_loss']:,.2f}")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
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

    # Build calendar
    try:
        if "-" in sel_month:
            yr, mo = map(int, sel_month.split("-"))
        else:
            yr, mo = map(int, sel_month.split("."))
    except:
        yr, mo = date.today().year, date.today().month

    cal_data = {}
    for d_date, pnl in daily.items():
        cal_data[d_date.day if hasattr(d_date, 'day') else int(str(d_date)[-2:])] = pnl

    ops_by_day = dm.groupby("close_date").agg(
        ops=("profit","count"),
        wins=("win","sum")
    )
    ops_data = {}
    for d_date, row in ops_by_day.iterrows():
        day_num = d_date.day if hasattr(d_date, 'day') else int(str(d_date)[-2:])
        ops_data[day_num] = {"ops": int(row["ops"]), "wins": int(row["wins"])}

    # Calendar grid using HTML
    days_in_month = calendar.monthrange(yr, mo)[1]
    first_weekday = calendar.monthrange(yr, mo)[0]  # 0=Mon

    day_names = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
    cal_html = """<style>
    .cal-wrap { display:grid; grid-template-columns:repeat(7,1fr); gap:6px; margin-top:8px; }
    .cal-hdr  { text-align:center; font-size:11px; font-weight:600; color:#64748b;
                text-transform:uppercase; letter-spacing:.08em; padding:6px 0; }
    .cal-cell { background:#111318; border:1px solid #1e2330; border-radius:10px;
                min-height:80px; padding:8px 10px; position:relative; }
    .cal-cell.empty { background:transparent; border:none; }
    .cal-cell.weekend { background:#0e1117; }
    .cal-cell.profit { border-top:2px solid #22c55e; }
    .cal-cell.loss   { border-top:2px solid #ef4444; }
    .cal-num  { font-size:11px; color:#475569; margin-bottom:6px; font-family:'DM Mono',monospace; }
    .cal-pnl  { font-family:'DM Mono',monospace; font-size:14px; font-weight:500; }
    .cal-ops  { font-size:10px; color:#475569; margin-top:4px; }
    .cal-dots { display:flex; gap:3px; margin-top:5px; flex-wrap:wrap; }
    .dot-w    { width:6px; height:6px; border-radius:50%; background:#22c55e; }
    .dot-l    { width:6px; height:6px; border-radius:50%; background:#ef4444; }
    </style>
    <div class="cal-wrap">"""

    for d in day_names:
        cal_html += f'<div class="cal-hdr">{d}</div>'

    for _ in range(first_weekday):
        cal_html += '<div class="cal-cell empty"></div>'

    for day in range(1, days_in_month + 1):
        dow = (first_weekday + day - 1) % 7
        is_weekend = dow >= 5
        pnl = cal_data.get(day)
        info = ops_data.get(day, {})

        cls = "cal-cell"
        if is_weekend: cls += " weekend"
        if pnl is not None:
            cls += " profit" if pnl > 0 else " loss"

        bg = ""
        if pnl is not None:
            alpha = min(abs(pnl) / max(abs(v) for v in cal_data.values() if v), 1) * 0.15
            bg = f"background:rgba({'34,197,94' if pnl>0 else '239,68,68'},{alpha:.2f});"

        cal_html += f'<div class="{cls}" style="{bg}">'
        cal_html += f'<div class="cal-num">{day}</div>'

        if pnl is not None:
            color = "#22c55e" if pnl > 0 else "#ef4444"
            sign  = "+" if pnl >= 0 else ""
            cal_html += f'<div class="cal-pnl" style="color:{color}">{sign}{pnl:,.2f}$</div>'
            ops = info.get("ops", 0); wins = info.get("wins", 0); losses = ops - wins
            cal_html += f'<div class="cal-ops">{ops} op{"s" if ops>1 else ""}</div>'
            dots = '<div class="cal-dots">'
            dots += ''.join('<div class="dot-w"></div>' for _ in range(min(wins, 8)))
            dots += ''.join('<div class="dot-l"></div>' for _ in range(min(losses, 8)))
            dots += '</div>'
            cal_html += dots

        cal_html += '</div>'

    total_cells = first_weekday + days_in_month
    remaining = (7 - total_cells % 7) % 7
    for _ in range(remaining):
        cal_html += '<div class="cal-cell empty"></div>'

    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

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
