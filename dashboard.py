import math
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database import (
    get_actas_by_type,
    get_jee_detail_history,
    get_jee_porcentaje,
    get_jee_totals_history,
    get_jje_detail,
    get_kpi_history,
    get_kpis,
    get_onpe_candidate_history,
    get_onpe_candidate_history_by_run,
    get_onpe_latest,
    get_onpe_run_summary_history,
    get_onpe_totals_history,
    get_run_timestamps,
)


st.set_page_config(page_title="Elección Presidencial Perú 2026", layout="wide")

ONPE_BLUE = "#003F7D"
ONPE_LIGHT = "#74B6E6"
JNE_RED = "#C8102E"
JNE_MUTED = "#8A8A8A"
GREEN = "#168A4A"
AMBER = "#D99A19"
INK = "#1F2937"
GRID = "#E5E7EB"


st.markdown(
    """
    <style>
    .block-container {
        max-width: 1500px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        display: none;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #e5e7eb;
        margin-bottom: 18px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        padding-left: 18px;
        padding-right: 18px;
        border-radius: 6px 6px 0 0;
        font-weight: 650;
    }
    .source-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px 18px;
        background: #ffffff;
        min-height: 132px;
    }
    .source-kicker {
        font-size: 0.78rem;
        color: #6b7280;
        margin-bottom: 4px;
        font-weight: 700;
        text-transform: uppercase;
    }
    .source-value {
        font-size: 2rem;
        line-height: 1.1;
        color: #111827;
        font-weight: 750;
    }
    .source-sub {
        margin-top: 8px;
        color: #4b5563;
        font-size: 0.92rem;
    }
    .ok-pill, .warn-pill, .info-pill {
        display: inline-block;
        border-radius: 999px;
        padding: 3px 9px;
        font-size: 0.78rem;
        font-weight: 700;
    }
    .ok-pill { background: #e9f8ef; color: #166534; }
    .warn-pill { background: #fff7e6; color: #92400e; }
    .info-pill { background: #eaf3ff; color: #1e40af; }
    div[data-testid="stMetric"] {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px 14px;
        background: #ffffff;
        min-height: 104px;
    }
    div[data-testid="stMetricLabel"] {
        color: #4b5563;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_float(value, default=None):
    if value is None:
        return default
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    num = safe_float(value)
    if num is None or math.isnan(num):
        return default
    return int(round(num))


def normalize_pct(value):
    num = safe_float(value)
    if num is None:
        return None
    if math.isnan(num):
        return None
    return num * 100 if abs(num) <= 1 else num


def fmt_num(value):
    num = safe_float(value)
    if num is None or math.isnan(num):
        return "-"
    return f"{num:,.0f}"


def fmt_pct(value, digits=1):
    pct = normalize_pct(value)
    if pct is None:
        return "-"
    return f"{pct:.{digits}f}%"


def parse_timestamp(value):
    if value is None:
        return None
    text = str(value)
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000)
    try:
        return pd.to_datetime(text).to_pydatetime()
    except Exception:
        return None


def fmt_time(value):
    dt = parse_timestamp(value)
    if not dt:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M")


def short_election_type(value):
    text = str(value or "").strip().upper()
    mapping = {
        "PRESIDENCIAL": "Presidencial",
        "PRESIDENCIA": "Presidencial",
        "DIPUTADOS": "Diputados",
        "PARLAMENTO ANDINO": "Parlamento Andino",
        "SENADORES DISTRITO ÚNICO": "Senadores distrito único",
        "SENADORES DISTRITO UNICO": "Senadores distrito único",
        "SENADORES DISTRITO MÚLTIPLE": "Senadores distrito múltiple",
        "SENADORES DISTRITO MULTIPLE": "Senadores distrito múltiple",
        "MAS DE UN TIPO DE ELECCIÓN": "Más de una elección",
        "MÁS DE UN TIPO DE ELECCIÓN": "Más de una elección",
    }
    return mapping.get(text, str(value or "").strip().title())


def apply_fig_style(fig, height=360, legend=True):
    fig.update_layout(
        height=height,
        margin=dict(t=48, l=12, r=12, b=24),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=INK),
        showlegend=legend,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def style_donut(fig, height=440):
    fig.update_traces(
        hole=0.55,
        textinfo="percent",
        textposition="inside",
        insidetextfont=dict(size=12, color="white"),
        marker=dict(line=dict(color="white", width=2)),
        sort=False,
    )
    fig.update_layout(
        height=height,
        margin=dict(t=46, l=8, r=8, b=92),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=INK),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.06,
            xanchor="center",
            x=0.5,
            font=dict(size=9),
        ),
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    return fig


def metric_card(label, value, subtext="", pill=None, pill_kind="info"):
    pill_html = ""
    if pill:
        pill_html = f"<div style='margin-top:10px'><span class='{pill_kind}-pill'>{pill}</span></div>"
    st.markdown(
        f"""
        <div class="source-card">
            <div class="source-kicker">{label}</div>
            <div class="source-value">{value}</div>
            <div class="source-sub">{subtext}</div>
            {pill_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def gauge(title, value, color, subtitle=None):
    pct = normalize_pct(value) or 0
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            domain={"x": [0, 1], "y": [0.24, 1]},
            value=pct,
            number={"suffix": "%", "font": {"size": 30}},
            title={"text": title, "font": {"size": 15}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 0,
                    "tickcolor": "rgba(0,0,0,0)",
                    "tickfont": {"color": "rgba(0,0,0,0)", "size": 1},
                },
                "bar": {"color": color},
                "bgcolor": "#F3F4F6",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 50], "color": "#FEE2E2"},
                    {"range": [50, 85], "color": "#FEF3C7"},
                    {"range": [85, 100], "color": "#DCFCE7"},
                ],
            },
        )
    )
    if subtitle:
        fig.add_annotation(
            text=subtitle,
            x=0.5,
            y=0.02,
            showarrow=False,
            font=dict(size=12, color="#4b5563"),
            xanchor="center",
            yanchor="bottom",
        )
    fig = apply_fig_style(fig, height=270, legend=False)
    fig.update_layout(margin=dict(t=42, l=8, r=8, b=42))
    return fig


def is_blank_or_null(row):
    name = f"{row.get('nombre_partido', '')} {row.get('nombre_candidato', '')}".upper()
    return "BLANCO" in name or "NULO" in name


def candidate_label(row):
    candidate = (row.get("nombre_candidato") or "").strip()
    party = (row.get("nombre_partido") or "").strip()
    text = f"{party} {candidate}".upper()
    if "FUJIMORI" in text:
        return "Keiko Fujimori"
    if "SANCHEZ" in text or "SÁNCHEZ" in text:
        return "Roberto Sánchez"
    if "LÓPEZ ALIAGA" in text or "LOPEZ ALIAGA" in text:
        return "Rafael López Aliaga"
    if "JORGE NIETO" in text:
        return "Jorge Nieto"
    if "BELMONT" in text:
        return "Ricardo Belmont"
    if "ALVAREZ" in text:
        return "Carlos Álvarez"
    if "LOPEZ CHAU" in text or "LOPEZ CHAU" in text:
        return "Pablo López Chau"
    if "BLANCO" in text:
        return "Votos en blanco"
    if "NULO" in text:
        return "Votos nulos"
    if candidate:
        first = candidate.split()[0]
        last = candidate.split()[-1]
        return f"{first.title()} {last.title()}"
    return party.title()[:28]


def party_color(row):
    text = f"{row.get('nombre_partido', '')} {row.get('nombre_candidato', '')}".upper()
    if "FUERZA" in text or "FUJIMORI" in text:
        return "#F58220"
    if "JUNTOS" in text or "SANCHEZ" in text or "SÁNCHEZ" in text:
        return "#00843D"
    if "BLANCO" in text:
        return "#9CA3AF"
    if "NULO" in text:
        return "#6B7280"
    return ONPE_LIGHT


def row_delta(rows, col):
    if rows is None or len(rows) < 2:
        return None
    latest = safe_float(rows[-1].get(col) if isinstance(rows[-1], dict) else rows[-1][col])
    prev = safe_float(rows[-2].get(col) if isinstance(rows[-2], dict) else rows[-2][col])
    if latest is None or prev is None:
        return None
    return latest - prev


def kpi_map_for(run_id):
    if run_id is None:
        return {}
    return {row["measure_name"]: row["value"] for row in get_kpis(run_id)}


def kpi_value(kpi_map, name, default=None):
    raw = kpi_map.get(name, kpi_map.get(f"{name}__0", default))
    num = safe_float(raw)
    return num if num is not None else raw


def validation_status(ok, warn=False):
    if ok:
        return "OK"
    return "Revisar" if warn else "Diferencia"


def validation_table(onpe_data, jne_kpis, latest_jne):
    rows = []

    totals = onpe_data.get("totals", {})
    candidates = onpe_data.get("candidates", [])
    total_actas = safe_int(totals.get("total_actas"))
    contabilizadas = safe_int(totals.get("contabilizadas"))
    actas_pct = normalize_pct(totals.get("actas_contabilizadas")) or 0
    rows.append(
        {
            "Chequeo": "ONPE actas contabilizadas",
            "Resultado": validation_status(contabilizadas == total_actas or actas_pct >= 99.99),
            "Detalle": f"{fmt_num(contabilizadas)} de {fmt_num(total_actas)} ({actas_pct:.1f}%)",
        }
    )

    valid_sum = sum(safe_int(c.get("votos_validos")) for c in candidates if not is_blank_or_null(c))
    emitted_sum = sum(safe_int(c.get("votos_validos")) for c in candidates)
    total_valid = safe_int(totals.get("votos_validos"))
    total_emitted = safe_int(totals.get("votos_emitidos"))
    rows.append(
        {
            "Chequeo": "ONPE votos válidos",
            "Resultado": validation_status(abs(valid_sum - total_valid) <= 1),
            "Detalle": f"Candidatos {fmt_num(valid_sum)} vs total {fmt_num(total_valid)}",
        }
    )
    rows.append(
        {
            "Chequeo": "ONPE votos emitidos",
            "Resultado": validation_status(abs(emitted_sum - total_emitted) <= 1),
            "Detalle": f"Candidatos + blanco + nulo {fmt_num(emitted_sum)} vs total {fmt_num(total_emitted)}",
        }
    )

    if latest_jne:
        jee_rows = get_jje_detail(latest_jne)
        attended_sum = sum(safe_int(r["cantidad_actas_atendidas"]) for r in jee_rows)
        kpi_attended = safe_int(kpi_value(jne_kpis, "ActasObservadas.CantidadActasAtendidas"))
        rows.append(
            {
                "Chequeo": "JNE actas atendidas por JEE",
                "Resultado": validation_status(abs(attended_sum - kpi_attended) <= 1, warn=True),
                "Detalle": f"JEE {fmt_num(attended_sum)} vs KPI {fmt_num(kpi_attended)}",
            }
        )

        type_sum = sum(safe_int(r["actas_completas"]) for r in get_actas_by_type(latest_jne))
        adjusted = safe_int(kpi_value(jne_kpis, "ActasObservadas.Expedientes_Ajustado"))
        rows.append(
            {
                "Chequeo": "JNE total por tipo de elección",
                "Resultado": validation_status(abs(type_sum - adjusted) <= 1, warn=True),
                "Detalle": f"Tipos {fmt_num(type_sum)} vs ajustado {fmt_num(adjusted)}",
            }
        )

    return pd.DataFrame(rows)


KPI_LABELS = {
    "ActasObservadas.PorcentajeAvance": "% de avance",
    "ActasObservadas.PorcentajePronunciamientos": "% de pronunciamientos",
    "ActasObservadas.ActasObservadas": "Actas observadas",
    "ActasObservadas.ActasProcesadas": "Actas procesadas",
    "ActasObservadas.ActasRecuento": "Actas enviadas a recuento",
    "ActasObservadas.ExpedientesFaltantes": "Expedientes faltantes",
    "ActasObservadas.ActasEnTramite": "Expedientes en trámite",
    "ActasObservadas.MedidaAudienciasRealizadas": "Audiencias públicas realizadas",
    "ActasObservadas.MedidaAudienciasRealizadasSinReconteo": "Resueltas sin recuento",
    "ActasObservadas.MedidaAudienciasProgramadas": "Audiencias públicas programadas",
    "ActasObservadas.MedidaAudienciasNoProgramadas": "Audiencias públicas pendientes",
    "ActasObservadas.%audienciasRealizadas": "% de audiencias realizadas",
    "ActasObservadas.%audienciasRealizadasSinReconteo": "% resuelto sin recuento",
    "ActasObservadas.%audienciasProgramadas": "% de audiencias programadas",
    "ActasObservadas.%audienciasPendientes": "% de audiencias pendientes",
}


def source_label(source):
    return {"onpe": "ONPE", "jne": "JNE"}.get(source, str(source).upper())


def kpi_label(name):
    return KPI_LABELS.get(name, name.replace("ActasObservadas.", "").replace("_", " "))


def fmt_delta(value, pct_like=False):
    num = safe_float(value)
    if num is None:
        return "-"
    if pct_like:
        return f"{num:+,.2f} pp"
    return f"{num:+,.0f}"


def fmt_age(minutes):
    num = safe_float(minutes)
    if num is None:
        return "-"
    if num < 60:
        return f"{num:.0f} min"
    if num < 48 * 60:
        return f"{num / 60:.1f} h"
    return f"{num / 1440:.1f} días"


def short_health_status(status):
    if not status:
        return "-"
    return str(status).split(" / ")[0]


def source_health(runs_df, source, cadence_minutes=15):
    source_runs = runs_df[runs_df["source"] == source].sort_values("Fecha")
    if source_runs.empty:
        return {
            "status": "Sin capturas",
            "pill_kind": "warn",
            "latest": None,
            "age_minutes": None,
            "count": 0,
        }
    latest = pd.Timestamp(source_runs["Fecha"].iloc[-1]).tz_localize(None)
    now = pd.Timestamp.now().tz_localize(None)
    age_minutes = max((now - latest).total_seconds() / 60, 0)
    if age_minutes <= cadence_minutes + 5:
        status, pill_kind = "En cadencia", "ok"
    elif age_minutes <= cadence_minutes * 4:
        status, pill_kind = "Demorado", "warn"
    else:
        status, pill_kind = "Histórico / inactivo", "warn"
    return {
        "status": status,
        "pill_kind": pill_kind,
        "latest": latest,
        "age_minutes": age_minutes,
        "count": len(source_runs),
    }


def add_line_trace(fig, df, x, y, name, color):
    fig.add_trace(
        go.Scatter(
            x=df[x],
            y=df[y],
            name=name,
            mode="lines+markers",
            line=dict(color=color, width=3),
            marker=dict(size=7),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y:,.2f}<extra>" + name + "</extra>",
        )
    )


def kpi_history_df(name):
    hist = get_kpi_history(name)
    if not hist:
        return pd.DataFrame(columns=["Fecha", "Valor"])
    df = pd.DataFrame({"Fecha": [r["scraped_at"] for r in hist], "Valor": [r["value"] for r in hist]})
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    return df.dropna(subset=["Valor"]).sort_values("Fecha")


def top_real_candidates(candidates, limit=None):
    rows = [
        c
        for c in sorted(candidates or [], key=lambda x: safe_int(x.get("votos_validos")), reverse=True)
        if not is_blank_or_null(c)
    ]
    return rows[:limit] if limit else rows


def margin_summary(top_candidates):
    if len(top_candidates) < 2:
        return {"leader": {}, "second": {}, "votes": 0, "pp": None, "text": "-"}
    leader = top_candidates[0]
    second = top_candidates[1]
    votes = safe_int(leader.get("votos_validos")) - safe_int(second.get("votos_validos"))
    pp = (normalize_pct(leader.get("pct_validos")) or 0) - (normalize_pct(second.get("pct_validos")) or 0)
    return {
        "leader": leader,
        "second": second,
        "votes": votes,
        "pp": pp,
        "text": f"{fmt_num(votes)} votos / {pp:.2f} pp",
    }


def detect_onpe_change():
    totals_hist = get_onpe_totals_history()
    if not totals_hist or len(totals_hist) < 2:
        return {
            "Fuente": "ONPE",
            "Estado": "Sin histórico suficiente",
            "Detalle": "Se necesitan al menos 2 capturas ONPE.",
            "Cambió": False,
        }
    df = pd.DataFrame([dict(r) for r in totals_hist]).sort_values("run_id")
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    deltas = {
        "actas": safe_float(latest.get("contabilizadas"), 0) - safe_float(prev.get("contabilizadas"), 0),
        "participación": safe_float(latest.get("participacion"), 0) - safe_float(prev.get("participacion"), 0),
        "votos válidos": safe_float(latest.get("votos_validos"), 0) - safe_float(prev.get("votos_validos"), 0),
        "votos emitidos": safe_float(latest.get("votos_emitidos"), 0) - safe_float(prev.get("votos_emitidos"), 0),
    }
    changed = any(abs(v) > 0.0001 for v in deltas.values())
    detail = (
        f"Actas {fmt_delta(deltas['actas'])}; participación {fmt_delta(deltas['participación'], True)}; "
        f"votos válidos {fmt_delta(deltas['votos válidos'])}; emitidos {fmt_delta(deltas['votos emitidos'])}."
    )
    return {
        "Fuente": "ONPE",
        "Estado": "Cambió" if changed else "Sin cambio visible",
        "Detalle": detail,
        "Cambió": changed,
    }


def detect_jne_change():
    watched = [
        "ActasObservadas.ActasProcesadas",
        "ActasObservadas.ActasRecuento",
        "ActasObservadas.ActasEnTramite",
        "ActasObservadas.ExpedientesFaltantes",
    ]
    rows = []
    for name in watched:
        hist_df = kpi_history_df(name)
        if len(hist_df) < 2:
            continue
        delta = hist_df["Valor"].iloc[-1] - hist_df["Valor"].iloc[-2]
        rows.append((kpi_label(name), delta))
    if not rows:
        return {
            "Fuente": "JNE",
            "Estado": "Sin histórico suficiente",
            "Detalle": "Se necesitan al menos 2 capturas JNE con KPIs numéricos.",
            "Cambió": False,
        }
    changed = any(abs(delta) > 0.0001 for _, delta in rows)
    detail = "; ".join(f"{label} {fmt_delta(delta)}" for label, delta in rows)
    return {
        "Fuente": "JNE",
        "Estado": "Cambió" if changed else "Sin cambio visible",
        "Detalle": detail + ".",
        "Cambió": changed,
    }


def build_alerts(totals, top_candidates, validation_df, onpe_health, jne_health, onpe_change, jne_change, jne_kpis):
    rows = []
    for label, health in [("ONPE", onpe_health), ("JNE", jne_health)]:
        age = health.get("age_minutes")
        if age is None:
            rows.append(
                {
                    "Nivel": "Alerta",
                    "Alerta": f"{label} sin capturas",
                    "Detalle": "No hay capturas registradas para esta fuente.",
                    "Acción sugerida": "Revisar credenciales, endpoint y scheduler.",
                }
            )
        elif age > 30:
            rows.append(
                {
                    "Nivel": "Atención",
                    "Alerta": f"{label} fuera de cadencia",
                    "Detalle": f"Última captura hace {fmt_age(age)}; objetivo operativo: 15 minutos.",
                    "Acción sugerida": "Verificar si el scraper está pausado o si la fuente no se está actualizando.",
                }
            )

    margin = margin_summary(top_candidates)
    if margin["pp"] is not None and margin["pp"] < 5:
        rows.append(
            {
                "Nivel": "Atención",
                "Alerta": "Margen presidencial competitivo",
                "Detalle": f"Margen actual: {margin['text']}.",
                "Acción sugerida": "Mirar evolución por captura y cambios de participación.",
            }
        )

    if not validation_df.empty:
        issues = validation_df[validation_df["Resultado"].isin(["Diferencia", "Revisar"])]
        if not issues.empty:
            rows.append(
                {
                    "Nivel": "Revisar",
                    "Alerta": "Chequeos de consistencia",
                    "Detalle": f"{len(issues)} chequeo(s) no cuadran completamente.",
                    "Acción sugerida": "Comparar totales oficiales con detalles y documentar si es diferencia de fuente.",
                }
            )

    if not onpe_change.get("Cambió", False):
        rows.append(
            {
                "Nivel": "Info",
                "Alerta": "ONPE sin cambio visible",
                "Detalle": onpe_change.get("Detalle", "-"),
                "Acción sugerida": "Distinguir captura exitosa de actualización real de la fuente.",
            }
        )
    if not jne_change.get("Cambió", False):
        rows.append(
            {
                "Nivel": "Info",
                "Alerta": "JNE sin cambio visible",
                "Detalle": jne_change.get("Detalle", "-"),
                "Acción sugerida": "Esperar movimiento de actas observadas después del flujo inicial ONPE.",
            }
        )

    in_progress = safe_int(kpi_value(jne_kpis, "ActasObservadas.ActasEnTramite"))
    pending = safe_int(kpi_value(jne_kpis, "ActasObservadas.ExpedientesFaltantes"))
    if in_progress or pending:
        rows.append(
            {
                "Nivel": "Atención",
                "Alerta": "JNE con expedientes pendientes",
                "Detalle": f"{fmt_num(in_progress)} en trámite y {fmt_num(pending)} faltante(s).",
                "Acción sugerida": "Priorizar seguimiento de actas observadas, recuentos y pronunciamientos.",
            }
        )

    if not rows:
        rows.append(
            {
                "Nivel": "OK",
                "Alerta": "Sin alertas críticas",
                "Detalle": "Fuentes, consistencia y margen están dentro de los umbrales configurados.",
                "Acción sugerida": "Mantener monitoreo cada 15 minutos.",
            }
        )
    return pd.DataFrame(rows)


def build_event_log():
    events = []
    totals_hist = get_onpe_totals_history()
    if totals_hist:
        df_onpe = pd.DataFrame([dict(r) for r in totals_hist]).sort_values("run_id")
        for idx, row in df_onpe.iterrows():
            fecha = pd.to_datetime(row["scraped_at"])
            if idx == df_onpe.index[0]:
                event = "Primera captura ONPE"
                detail = f"Actas contabilizadas: {fmt_num(row.get('contabilizadas'))}; votos emitidos: {fmt_num(row.get('votos_emitidos'))}."
                level = "Info"
            else:
                prev = df_onpe.loc[df_onpe.index[df_onpe.index.get_loc(idx) - 1]]
                actas_delta = safe_float(row.get("contabilizadas"), 0) - safe_float(prev.get("contabilizadas"), 0)
                votos_delta = safe_float(row.get("votos_emitidos"), 0) - safe_float(prev.get("votos_emitidos"), 0)
                changed = abs(actas_delta) > 0.0001 or abs(votos_delta) > 0.0001
                event = "ONPE actualizó datos" if changed else "ONPE capturado sin cambio visible"
                detail = f"Actas {fmt_delta(actas_delta)}; votos emitidos {fmt_delta(votos_delta)}."
                level = "Cambio" if changed else "Sin cambio"
            events.append({"Fecha": fecha, "Fuente": "ONPE", "Nivel": level, "Evento": event, "Detalle": detail})

    jne_hist = kpi_history_df("ActasObservadas.ActasProcesadas")
    if not jne_hist.empty:
        for idx, row in jne_hist.iterrows():
            fecha = row["Fecha"]
            if idx == jne_hist.index[0]:
                event = "Primera captura JNE"
                detail = f"Actas procesadas: {fmt_num(row.get('Valor'))}."
                level = "Info"
            else:
                prev = jne_hist.loc[jne_hist.index[jne_hist.index.get_loc(idx) - 1]]
                delta = safe_float(row.get("Valor"), 0) - safe_float(prev.get("Valor"), 0)
                changed = abs(delta) > 0.0001
                event = "JNE actualizó actas procesadas" if changed else "JNE capturado sin cambio visible"
                detail = f"Actas procesadas {fmt_delta(delta)}."
                level = "Cambio" if changed else "Sin cambio"
            events.append({"Fecha": fecha, "Fuente": "JNE", "Nivel": level, "Evento": event, "Detalle": detail})

    if not events:
        return pd.DataFrame(columns=["Fecha", "Fuente", "Nivel", "Evento", "Detalle"])
    df = pd.DataFrame(events).sort_values("Fecha", ascending=False)
    df["Fecha"] = df["Fecha"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def electoral_readout(totals, top_candidates, validation_df, onpe_health, jne_health):
    rows = []
    if len(top_candidates) >= 2:
        leader = top_candidates[0]
        second = top_candidates[1]
        margin_votes = safe_int(leader.get("votos_validos")) - safe_int(second.get("votos_validos"))
        margin_pp = (normalize_pct(leader.get("pct_validos")) or 0) - (normalize_pct(second.get("pct_validos")) or 0)
        rows.append(
            {
                "Lectura": "Margen presidencial",
                "Estado": "Amplio" if margin_pp >= 5 else "Competitivo",
                "Detalle": (
                    f"{candidate_label(leader)} supera a {candidate_label(second)} por "
                    f"{fmt_num(margin_votes)} votos ({margin_pp:.2f} pp de votos válidos)."
                ),
            }
        )

    participation = normalize_pct(totals.get("participacion"))
    if participation is not None:
        rows.append(
            {
                "Lectura": "Participación ciudadana",
                "Estado": "Alta" if participation >= 70 else "Media",
                "Detalle": f"ONPE reporta {participation:.1f}% de participación sobre votos emitidos registrados.",
            }
        )

    active_sources = [
        source
        for source, health in [("ONPE", onpe_health), ("JNE", jne_health)]
        if health["status"] == "En cadencia"
    ]
    rows.append(
        {
            "Lectura": "Frescura de fuentes",
            "Estado": "En vivo" if len(active_sources) == 2 else "Histórico",
            "Detalle": (
                "Ambas fuentes están dentro de la cadencia de 15 minutos."
                if len(active_sources) == 2
                else "Los datos actuales son históricos/de prueba; el monitoreo activo deberá moverse cada 15 minutos."
            ),
        }
    )

    issue_count = 0
    if not validation_df.empty:
        issue_count = len(validation_df[validation_df["Resultado"].isin(["Diferencia", "Revisar"])])
    rows.append(
        {
            "Lectura": "Consistencia de datos",
            "Estado": "Revisar" if issue_count else "Sin alertas",
            "Detalle": (
                f"{issue_count} chequeo(s) requieren revisión entre totales y detalles."
                if issue_count
                else "Los chequeos principales cuadran dentro de la tolerancia configurada."
            ),
        }
    )

    onpe_runs = source_counts.get("onpe", 0)
    jne_runs = source_counts.get("jne", 0)
    rows.append(
        {
            "Lectura": "Profundidad histórica",
            "Estado": "Inicial" if min(onpe_runs, jne_runs) < 8 else "Suficiente",
            "Detalle": (
                f"Hay {onpe_runs} capturas ONPE y {jne_runs} JNE. "
                "El 7 de junio de 2026 conviene acumular al menos 8-12 puntos para leer tendencia real."
            ),
        }
    )

    return pd.DataFrame(rows)


runs_raw = get_run_timestamps()
if not runs_raw:
    st.warning("No hay datos. Ejecuta los scrapers con `--db` primero.")
    st.stop()

runs_df = pd.DataFrame(runs_raw)
runs_df["Fecha"] = pd.to_datetime(runs_df["scraped_at"])
source_counts = runs_df.groupby("source").size().to_dict()
latest_by_source = runs_df.sort_values("Fecha").groupby("source").tail(1)
latest_jne = max((r["id"] for r in runs_raw if r.get("source", "jne") == "jne"), default=None)
latest_onpe = max((r["id"] for r in runs_raw if r.get("source") == "onpe"), default=None)
onpe_data = get_onpe_latest() if latest_onpe else {}
jne_kpis = kpi_map_for(latest_jne)
global_totals = onpe_data.get("totals", {})
global_candidates = onpe_data.get("candidates", [])
global_top_candidates = top_real_candidates(global_candidates)
global_validation_df = validation_table(onpe_data, jne_kpis, latest_jne)
global_onpe_health = source_health(runs_df, "onpe")
global_jne_health = source_health(runs_df, "jne")
global_onpe_change = detect_onpe_change()
global_jne_change = detect_jne_change()
global_alerts_df = build_alerts(
    global_totals,
    global_top_candidates,
    global_validation_df,
    global_onpe_health,
    global_jne_health,
    global_onpe_change,
    global_jne_change,
    jne_kpis,
)
global_events_df = build_event_log()


st.title("Segunda vuelta de la Elección Presidencial Perú 2026")
st.caption(
    "Seguimiento de los datos electorales publicados por la ONPE y el JNE, "
    "con capturas periódicas para analizar avance y evolución temporal."
)

tabs = st.tabs(
    [
        "Resumen",
        "ONPE",
        "JNE",
        "Monitoreo",
        "Actualización",
    ]
)


with tabs[0]:
    st.subheader("Estado global de fuentes")
    totals = onpe_data.get("totals", {})
    candidates = onpe_data.get("candidates", [])
    jee_rows = get_jje_detail(latest_jne) if latest_jne else []

    last_onpe = latest_by_source.loc[latest_by_source["source"] == "onpe", "Fecha"]
    last_jne = latest_by_source.loc[latest_by_source["source"] == "jne", "Fecha"]

    top_candidates = [c for c in sorted(candidates, key=lambda x: safe_int(x.get("votos_validos")), reverse=True) if not is_blank_or_null(c)]
    leader = top_candidates[0] if top_candidates else {}
    second = top_candidates[1] if len(top_candidates) > 1 else {}
    lead_votes = safe_int(leader.get("votos_validos")) - safe_int(second.get("votos_validos")) if leader and second else 0

    cols = st.columns(4)
    with cols[0]:
        metric_card(
            "ONPE actas contabilizadas",
            fmt_pct(totals.get("actas_contabilizadas")),
            f"{fmt_num(totals.get('contabilizadas'))} de {fmt_num(totals.get('total_actas'))} actas",
            pill=f"{source_counts.get('onpe', 0)} corridas",
            pill_kind="info",
        )
    with cols[1]:
        metric_card(
            "ONPE liderazgo",
            fmt_num(lead_votes),
            f"{leader.get('nombre_partido', '-').title()} sobre {second.get('nombre_partido', '-').title()}",
            pill=fmt_pct(leader.get("pct_validos"), 2),
            pill_kind="ok",
        )
    with cols[2]:
        metric_card(
            "JNE avance",
            fmt_pct(kpi_value(jne_kpis, "ActasObservadas.PorcentajeAvance"), 2),
            f"{fmt_num(kpi_value(jne_kpis, 'ActasObservadas.ActasProcesadas'))} actas procesadas",
            pill=f"{source_counts.get('jne', 0)} corridas",
            pill_kind="info",
        )
    with cols[3]:
        metric_card(
            "JNE pendientes críticos",
            fmt_num(kpi_value(jne_kpis, "ActasObservadas.ExpedientesFaltantes")),
            f"{fmt_num(kpi_value(jne_kpis, 'ActasObservadas.ActasEnTramite'))} expedientes en trámite",
            pill="seguimiento",
            pill_kind="warn",
        )

    st.subheader("Lectura electoral rápida")
    st.dataframe(
        electoral_readout(totals, top_candidates, global_validation_df, global_onpe_health, global_jne_health),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Alertas activas")
    st.dataframe(global_alerts_df.head(5), hide_index=True, width="stretch")

    cols = st.columns([1, 1, 1])
    with cols[0]:
        st.plotly_chart(
            gauge(
                "ONPE contabilización",
                totals.get("actas_contabilizadas"),
                ONPE_BLUE,
                f"Última captura: {last_onpe.iloc[0].strftime('%Y-%m-%d %H:%M') if len(last_onpe) else '-'}",
            ),
            width="stretch",
        )
    with cols[1]:
        st.plotly_chart(
            gauge(
                "JNE avance general",
                kpi_value(jne_kpis, "ActasObservadas.PorcentajeAvance"),
                JNE_RED,
                f"Última captura: {last_jne.iloc[0].strftime('%Y-%m-%d %H:%M') if len(last_jne) else '-'}",
            ),
            width="stretch",
        )
    with cols[2]:
        st.plotly_chart(
            gauge(
                "Participación ONPE",
                totals.get("participacion"),
                GREEN,
                f"Votos emitidos: {fmt_num(totals.get('votos_emitidos'))}",
            ),
            width="stretch",
        )

    st.divider()
    cols = st.columns([1.15, 1.2, 1])
    with cols[0]:
        if top_candidates:
            df_top = pd.DataFrame(top_candidates[:8])
            df_top["Etiqueta"] = df_top.apply(candidate_label, axis=1)
            df_top["Color"] = df_top.apply(party_color, axis=1)
            df_top["Votos texto"] = df_top["votos_validos"].map(lambda x: f"{safe_int(x) / 1_000_000:.2f}M")
            fig = px.bar(
                df_top.sort_values("votos_validos"),
                x="votos_validos",
                y="Etiqueta",
                orientation="h",
                title="ONPE: candidaturas principales por votos",
                text="Votos texto",
                color="Etiqueta",
                color_discrete_sequence=df_top.sort_values("votos_validos")["Color"].tolist(),
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_xaxes(tickformat=".2s", title="Votos")
            fig.update_layout(showlegend=False)
            st.plotly_chart(apply_fig_style(fig, height=420, legend=False), width="stretch")
    with cols[1]:
        actas = get_actas_by_type(latest_jne) if latest_jne else []
        if actas:
            df_actas = pd.DataFrame([dict(r) for r in actas])
            df_actas["Tipo"] = df_actas["tipo_eleccion"].map(short_election_type)
            fig = px.pie(
                df_actas,
                values="actas_completas",
                names="Tipo",
                hole=0.55,
                title="JNE: distribución por tipo",
                color_discrete_sequence=[JNE_RED, "#6B7280", "#A3A3A3", "#404040", "#D1D5DB", "#991B1B"],
            )
            st.plotly_chart(style_donut(fig, height=455), width="stretch")
    with cols[2]:
        if not runs_df.empty:
            runs_count = runs_df.groupby("source", as_index=False).size().rename(columns={"size": "corridas"})
            fig = px.bar(
                runs_count,
                x="source",
                y="corridas",
                color="source",
                text="corridas",
                title="Capturas almacenadas",
                color_discrete_map={"onpe": ONPE_BLUE, "jne": JNE_RED},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False)
            st.plotly_chart(apply_fig_style(fig, height=420, legend=False), width="stretch")

    st.subheader("Chequeos de consistencia")
    st.table(global_validation_df)


with tabs[1]:
    onpe_tabs = st.tabs(["Actual", "Evolución"])
    with onpe_tabs[0]:
        st.subheader("ONPE actual")
        if not onpe_data:
            st.warning("No hay datos ONPE en la base.")
        else:
            totals = onpe_data.get("totals", {})
            mesas = onpe_data.get("mesas", {})
            candidates = onpe_data.get("candidates", [])
            blank = next((c for c in candidates if "BLANCO" in c.get("nombre_partido", "").upper()), {})
            null = next((c for c in candidates if "NULO" in c.get("nombre_partido", "").upper()), {})
            real_candidates = [c for c in sorted(candidates, key=lambda x: safe_int(x.get("votos_validos")), reverse=True) if not is_blank_or_null(c)]

            onpe_metrics = [
                ("Total actas", fmt_num(totals.get("total_actas")), None),
                ("Contabilizadas", fmt_num(totals.get("contabilizadas")), fmt_pct(totals.get("actas_contabilizadas"))),
                ("Envío al JEE", fmt_num(totals.get("enviadas_jee")), fmt_pct(totals.get("actas_enviadas_jee"))),
                ("Pendientes", fmt_num(totals.get("pendientes_jee")), fmt_pct(totals.get("actas_pendientes_jee"))),
                ("Participación", fmt_pct(totals.get("participacion")), None),
                ("Mesas instaladas", fmt_num(mesas.get("instaladas")), f"No instaladas: {fmt_num(mesas.get('no_instaladas'))}"),
            ]
            for metric_row in [onpe_metrics[:3], onpe_metrics[3:]]:
                cols = st.columns(3)
                for col, (label, value, delta) in zip(cols, metric_row):
                    with col:
                        st.metric(label, value, delta)

            col_status, col_gauge = st.columns([1.45, 1])
            with col_status:
                status_df = pd.DataFrame(
                    [
                        {"Estado": "Contabilizadas", "Actas": safe_int(totals.get("contabilizadas")), "Color": ONPE_BLUE},
                        {"Estado": "Envío al JEE", "Actas": safe_int(totals.get("enviadas_jee")), "Color": ONPE_LIGHT},
                        {"Estado": "Pendientes", "Actas": safe_int(totals.get("pendientes_jee")), "Color": "#E5E7EB"},
                    ]
                )
                fig = go.Figure()
                for _, row in status_df.iterrows():
                    fig.add_trace(
                        go.Bar(
                            x=[row["Actas"]],
                            y=["Actas"],
                            orientation="h",
                            name=row["Estado"],
                            marker_color=row["Color"],
                            text=[f"{row['Estado']}: {row['Actas']:,.0f}"],
                            hovertemplate="%{text}<extra></extra>",
                        )
                    )
                fig.update_layout(barmode="stack", title="Estado de actas ONPE")
                st.plotly_chart(apply_fig_style(fig, height=260), width="stretch")
            with col_gauge:
                st.plotly_chart(gauge("Actas contabilizadas", totals.get("actas_contabilizadas"), ONPE_BLUE), width="stretch")

            st.caption(f"Actualización ONPE: {fmt_time(totals.get('fec_actualizacion'))}")
            st.divider()

            col_bar, col_table = st.columns([1.35, 1])
            with col_bar:
                if real_candidates:
                    df_candidates = pd.DataFrame(real_candidates[:12])
                    df_candidates["Etiqueta"] = df_candidates.apply(candidate_label, axis=1)
                    df_candidates["Color"] = df_candidates.apply(party_color, axis=1)
                    df_candidates["Votos texto"] = df_candidates["votos_validos"].map(lambda x: f"{safe_int(x) / 1_000_000:.2f}M")
                    fig = px.bar(
                        df_candidates.sort_values("votos_validos"),
                        x="votos_validos",
                        y="Etiqueta",
                        orientation="h",
                        color="Etiqueta",
                        color_discrete_sequence=df_candidates.sort_values("votos_validos")["Color"].tolist(),
                        text="Votos texto",
                        title="Votos válidos por candidatura",
                    )
                    fig.update_traces(textposition="outside", cliponaxis=False)
                    fig.update_xaxes(tickformat=".2s", title="Votos")
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(apply_fig_style(fig, height=560, legend=False), width="stretch")
            with col_table:
                if candidates:
                    display = pd.DataFrame(candidates)
                    display["Candidatura"] = display.apply(candidate_label, axis=1)
                    display = display[["Candidatura", "votos_validos", "pct_validos", "pct_emitidos"]].rename(
                        columns={
                            "votos_validos": "Votos",
                            "pct_validos": "% válidos",
                            "pct_emitidos": "% emitidos",
                        }
                    )
                    display["Votos"] = display["Votos"].map(fmt_num)
                    display["% válidos"] = display["% válidos"].map(lambda x: fmt_pct(x, 3))
                    display["% emitidos"] = display["% emitidos"].map(lambda x: fmt_pct(x, 3))
                    st.dataframe(display.head(14), hide_index=True, width="stretch", height=560)

            st.divider()
            cols = st.columns(4)
            with cols[0]:
                st.metric("Votos válidos", fmt_num(totals.get("votos_validos")), fmt_pct(totals.get("porcentaje_votos_validos")))
            with cols[1]:
                st.metric("Votos emitidos", fmt_num(totals.get("votos_emitidos")), fmt_pct(totals.get("porcentaje_votos_emitidos")))
            with cols[2]:
                st.metric("Votos en blanco", fmt_num(blank.get("votos_validos")), fmt_pct(blank.get("pct_emitidos")))
            with cols[3]:
                st.metric("Votos nulos", fmt_num(null.get("votos_validos")), fmt_pct(null.get("pct_emitidos")))

            mix_df = pd.DataFrame(
                [
                    {"Tipo": "Válidos por candidaturas", "Votos": safe_int(totals.get("votos_validos"))},
                    {"Tipo": "Blanco", "Votos": safe_int(blank.get("votos_validos"))},
                    {"Tipo": "Nulo", "Votos": safe_int(null.get("votos_validos"))},
                ]
            )
            fig = px.pie(
                mix_df,
                values="Votos",
                names="Tipo",
                hole=0.55,
                title="Composición de votos emitidos",
                color="Tipo",
                color_discrete_map={"Válidos por candidaturas": ONPE_BLUE, "Blanco": "#9CA3AF", "Nulo": "#4B5563"},
            )
            st.plotly_chart(style_donut(fig, height=430), width="stretch")

            st.subheader("Composición y relaciones ONPE")
            rel_cols = st.columns([1, 1])
            with rel_cols[0]:
                if candidates:
                    tree_rows = []
                    for c in candidates:
                        tree_rows.append(
                            {
                                "Grupo": "Blanco / nulo" if is_blank_or_null(c) else "Candidaturas",
                                "Etiqueta": candidate_label(c),
                                "Votos": safe_int(c.get("votos_validos")),
                                "% emitidos": normalize_pct(c.get("pct_emitidos")) or 0,
                            }
                        )
                    df_tree = pd.DataFrame(tree_rows)
                    fig = px.treemap(
                        df_tree[df_tree["Votos"] > 0],
                        path=["Grupo", "Etiqueta"],
                        values="Votos",
                        color="Grupo",
                        title="Treemap de votos emitidos",
                        color_discrete_map={"Candidaturas": ONPE_BLUE, "Blanco / nulo": "#9CA3AF"},
                    )
                    fig.update_traces(texttemplate="%{label}<br>%{value:,.0f}")
                    st.plotly_chart(apply_fig_style(fig, height=420), width="stretch", key="onpe_votes_treemap")
            with rel_cols[1]:
                if real_candidates:
                    df_relation = pd.DataFrame(real_candidates[:12])
                    df_relation["Etiqueta"] = df_relation.apply(candidate_label, axis=1)
                    df_relation["% emitidos"] = df_relation["pct_emitidos"].map(lambda x: normalize_pct(x) or 0)
                    df_relation["% válidos"] = df_relation["pct_validos"].map(lambda x: normalize_pct(x) or 0)
                    fig = px.scatter(
                        df_relation,
                        x="% emitidos",
                        y="votos_validos",
                        size="votos_validos",
                        color="Etiqueta",
                        hover_name="Etiqueta",
                        title="Relación entre votos y peso sobre emitidos",
                    )
                    fig.update_traces(marker=dict(opacity=0.82, line=dict(width=1, color="white")))
                    fig.update_xaxes(title="% de votos emitidos")
                    fig.update_yaxes(title="Votos válidos", tickformat=".2s")
                    st.plotly_chart(apply_fig_style(fig, height=420), width="stretch", key="onpe_vote_share_scatter")


    with onpe_tabs[1]:
        st.subheader("ONPE evolución")
        summary_hist = get_onpe_run_summary_history()
        if not summary_hist:
            st.info("Todavía no hay capturas ONPE guardadas para construir evolución.")
        else:
            df = pd.DataFrame([dict(r) for r in summary_hist])
            df["Fecha"] = pd.to_datetime(df["scraped_at"])
            df = df.sort_values("Fecha")
            df["Votos válidos"] = df["votos_validos"].fillna(df["votos_validos_fallback"])
            df["Votos emitidos"] = df["votos_emitidos"].fillna(
                df["Votos válidos"].fillna(0) + df["votos_blancos"].fillna(0) + df["votos_nulos"].fillna(0)
            )
            df["Tiene totales"] = df["actas_contabilizadas"].notna()

            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) > 1 else None

            cols = st.columns(4)
            for col, metric, label, pct_like in [
                (cols[0], "contabilizadas", "Actas contabilizadas", False),
                (cols[1], "actas_contabilizadas", "% actas", True),
                (cols[2], "participacion", "Participación", True),
                (cols[3], "Votos emitidos", "Votos emitidos", False),
            ]:
                value = latest.get(metric)
                delta = safe_float(latest.get(metric), 0) - safe_float(previous.get(metric), 0) if previous is not None else None
                with col:
                    st.metric(label, fmt_pct(value) if pct_like else fmt_num(value), fmt_delta(delta, pct_like) if delta is not None else "-")

            if len(df) > 1:
                tracked = ["contabilizadas", "actas_contabilizadas", "participacion", "Votos emitidos"]
                changed = any(
                    abs(safe_float(latest.get(metric), 0) - safe_float(previous.get(metric), 0)) > 0.0001
                    for metric in tracked
                )
                if changed:
                    st.success("La última captura ONPE muestra variación respecto de la captura anterior.")
                else:
                    st.info(
                        "Las capturas ONPE están entrando, pero la fuente no muestra variación visible. "
                        "Esto es esperable si el conteo oficial ya está estabilizado."
                    )

                cols = st.columns(2)
                with cols[0]:
                    fig = go.Figure()
                    if df["actas_contabilizadas"].notna().any():
                        add_line_trace(fig, df, "Fecha", "actas_contabilizadas", "Actas contabilizadas", ONPE_BLUE)
                        fig.update_yaxes(range=[0, 100])
                    else:
                        add_line_trace(fig, df, "Fecha", "filas_candidaturas", "Filas capturadas", ONPE_BLUE)
                    fig.update_layout(title="Avance de contabilización ONPE", yaxis_title="% de actas")
                    st.plotly_chart(apply_fig_style(fig, height=330, legend=False), width="stretch")
                with cols[1]:
                    fig = go.Figure()
                    add_line_trace(fig, df, "Fecha", "Votos válidos", "Votos válidos", ONPE_BLUE)
                    add_line_trace(fig, df, "Fecha", "Votos emitidos", "Votos emitidos", GREEN)
                    fig.update_layout(title="Volumen de votos acumulados", yaxis_title="Votos")
                    st.plotly_chart(apply_fig_style(fig, height=330), width="stretch")

                cols = st.columns(2)
                with cols[0]:
                    fig = go.Figure()
                    add_line_trace(fig, df, "Fecha", "votos_blancos", "Votos en blanco", "#9CA3AF")
                    add_line_trace(fig, df, "Fecha", "votos_nulos", "Votos nulos", "#4B5563")
                    fig.update_layout(title="Votos blancos y nulos", yaxis_title="Votos")
                    st.plotly_chart(apply_fig_style(fig, height=310), width="stretch")
                with cols[1]:
                    capture_df = df.copy()
                    capture_df["Captura registrada"] = 1
                    fig = go.Figure()
                    add_line_trace(fig, capture_df, "Fecha", "Captura registrada", "Capturas ONPE", ONPE_LIGHT)
                    fig.update_yaxes(range=[0, 1.2], tickvals=[0, 1], title="Captura registrada")
                    fig.update_layout(title="Cadencia de capturas ONPE")
                    st.plotly_chart(apply_fig_style(fig, height=310, legend=False), width="stretch")
            else:
                st.info("Hay 1 captura ONPE guardada. La siguiente captura permitirá dibujar variación temporal.")

            all_hist = get_onpe_candidate_history_by_run()
            if all_hist:
                cand_hist = pd.DataFrame([dict(r) for r in all_hist])
                cand_hist["Fecha"] = pd.to_datetime(cand_hist["scraped_at"])
                cand_hist["Etiqueta"] = cand_hist.apply(candidate_label, axis=1)
                cand_hist["Color"] = cand_hist.apply(party_color, axis=1)
                latest_candidates = cand_hist.sort_values("Fecha").groupby("Etiqueta").tail(1)
                latest_candidates = latest_candidates.sort_values("votos_validos", ascending=False)
                candidate_labels = latest_candidates[~latest_candidates.apply(is_blank_or_null, axis=1)].head(6)["Etiqueta"].tolist()
                vote_type_labels = [label for label in ["Votos en blanco", "Votos nulos"] if label in latest_candidates["Etiqueta"].tolist()]
                top_labels = candidate_labels + vote_type_labels
                cand_hist = cand_hist[cand_hist["Etiqueta"].isin(top_labels)].sort_values(["Etiqueta", "Fecha"])
                color_map = latest_candidates.set_index("Etiqueta")["Color"].to_dict()
                if len(cand_hist["Fecha"].drop_duplicates()) > 1:
                    fig = px.line(
                        cand_hist,
                        x="Fecha",
                        y="votos_validos",
                        color="Etiqueta",
                        markers=True,
                        title="Evolución de votos por candidatura y tipo de voto",
                        color_discrete_map=color_map,
                    )
                    fig.update_traces(line=dict(width=3), marker=dict(size=7))
                    fig.update_yaxes(tickformat=".2s", title="Votos")
                    st.plotly_chart(apply_fig_style(fig, height=520), width="stretch")
                else:
                    st.caption("Hay resultados ONPE por candidatura, pero todavía no hay dos capturas para trazar líneas por candidatura.")

                pct_hist = cand_hist[cand_hist["pct_validos"].notna()]
                if not pct_hist.empty and len(pct_hist["Fecha"].drop_duplicates()) > 1:
                    fig = px.line(
                        pct_hist,
                        x="Fecha",
                        y="pct_validos",
                        color="Etiqueta",
                        markers=True,
                        title="Evolución del porcentaje de votos válidos",
                        color_discrete_map=color_map,
                    )
                    fig.update_traces(line=dict(width=3), marker=dict(size=7))
                    fig.update_yaxes(title="% de votos válidos")
                    st.plotly_chart(apply_fig_style(fig, height=420), width="stretch")

                last_changes = []
                for label, group in cand_hist.groupby("Etiqueta"):
                    ordered = group.sort_values("Fecha")
                    if len(ordered) < 2:
                        continue
                    last_changes.append(
                        {
                            "Indicador": label,
                            "Último valor": fmt_num(ordered["votos_validos"].iloc[-1]),
                            "Variación anterior": fmt_delta(ordered["votos_validos"].iloc[-1] - ordered["votos_validos"].iloc[-2]),
                        }
                    )
                if last_changes:
                    st.subheader("Última variación detectada")
                    st.dataframe(pd.DataFrame(last_changes), hide_index=True, width="stretch")
                    if all(row["Variación anterior"] in ["+0", "-0"] for row in last_changes):
                        st.caption("Las capturas actuales no muestran variación visible porque la fuente está estable.")

            st.dataframe(
                df[["Fecha", "contabilizadas", "actas_contabilizadas", "participacion", "Votos válidos", "Votos emitidos", "Tiene totales"]].rename(
                    columns={
                        "contabilizadas": "Actas contabilizadas",
                        "actas_contabilizadas": "% actas",
                        "participacion": "% participación",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
            st.caption(f"Corridas ONPE almacenadas: {source_counts.get('onpe', 0)}. Capturas con totales ONPE: {int(df['Tiene totales'].sum())}.")


with tabs[2]:
    jne_tabs = st.tabs(["Actual", "Evolución"])
    with jne_tabs[0]:
        st.subheader("JNE actual")
        if latest_jne is None:
            st.warning("No hay datos JNE en la base.")
        else:
            jne_metrics = [
                ("% avance", fmt_pct(kpi_value(jne_kpis, "ActasObservadas.PorcentajeAvance"), 2), None),
                ("% pronunc.", fmt_pct(kpi_value(jne_kpis, "ActasObservadas.PorcentajePronunciamientos"), 2), None),
                ("Actas observadas", fmt_num(kpi_value(jne_kpis, "ActasObservadas.ActasObservadas")), None),
                ("Procesadas", fmt_num(kpi_value(jne_kpis, "ActasObservadas.ActasProcesadas")), None),
                ("Recuento de votos", fmt_num(kpi_value(jne_kpis, "ActasObservadas.ActasRecuento")), None),
                ("Exp. faltantes", fmt_num(kpi_value(jne_kpis, "ActasObservadas.ExpedientesFaltantes")), None),
            ]
            for metric_row in [jne_metrics[:3], jne_metrics[3:]]:
                cols = st.columns(3)
                for col, (label, value, delta) in zip(cols, metric_row):
                    with col:
                        st.metric(label, value, delta)

            st.caption(str(kpi_value(jne_kpis, "ActasObservadas.FechaActualizacion", "Sin fecha oficial JNE")))

            cols = st.columns([1, 1, 1])
            with cols[0]:
                st.plotly_chart(gauge("Avance JNE", kpi_value(jne_kpis, "ActasObservadas.PorcentajeAvance"), JNE_RED), width="stretch")
            with cols[1]:
                st.plotly_chart(gauge("Audiencias realizadas", kpi_value(jne_kpis, "ActasObservadas.%audienciasRealizadas"), GREEN), width="stretch")
            with cols[2]:
                st.plotly_chart(gauge("Audiencias pendientes", kpi_value(jne_kpis, "ActasObservadas.%audienciasPendientes"), AMBER), width="stretch")

            cols = st.columns(4)
            for col, label, value, pct in [
                (cols[0], "Audiencias realizadas", "ActasObservadas.MedidaAudienciasRealizadas", "ActasObservadas.%audienciasRealizadas"),
                (cols[1], "Resuelto sin recuento", "ActasObservadas.MedidaAudienciasRealizadasSinReconteo", "ActasObservadas.%audienciasRealizadasSinReconteo"),
                (cols[2], "Audiencias programadas", "ActasObservadas.MedidaAudienciasProgramadas", "ActasObservadas.%audienciasProgramadas"),
                (cols[3], "Audiencias pendientes", "ActasObservadas.MedidaAudienciasNoProgramadas", "ActasObservadas.%audienciasPendientes"),
            ]:
                with col:
                    st.metric(label, fmt_num(kpi_value(jne_kpis, value)), fmt_pct(kpi_value(jne_kpis, pct), 2))

            st.divider()
            col_type, col_jee = st.columns([1, 1.25])
            with col_type:
                actas = get_actas_by_type(latest_jne)
                if actas:
                    df_actas = pd.DataFrame([dict(r) for r in actas])
                    df_actas["Tipo"] = df_actas["tipo_eleccion"].map(short_election_type)
                    fig = px.pie(
                        df_actas,
                        values="actas_completas",
                        names="Tipo",
                        hole=0.55,
                        title="Por tipo de elección",
                        color_discrete_sequence=[JNE_RED, "#6B7280", "#A3A3A3", "#404040", "#D1D5DB", "#991B1B"],
                    )
                    st.plotly_chart(style_donut(fig, height=500), width="stretch")
                    df_actas["Actas"] = df_actas["actas_completas"].map(fmt_num)
                    st.dataframe(
                        df_actas[["tipo_eleccion", "Actas"]].rename(columns={"tipo_eleccion": "Tipo de elección"}),
                        hide_index=True,
                        width="stretch",
                    )
            with col_jee:
                jee_detail = get_jje_detail(latest_jne)
                jee_pct = get_jee_porcentaje(latest_jne)
                if jee_detail:
                    pct_map = {r["jee_name"]: r["porcentaje"] for r in jee_pct} if jee_pct else {}
                    rows = []
                    for d in jee_detail:
                        pct = d["pct_pronunciamientos_sin_total"]
                        if pct is None:
                            pct = pct_map.get(d["jee_name"], 0) or 0
                        rows.append(
                            {
                                "JEE": d["jee_name"],
                                "Expedientes": d["expedientes_completos"] or 0,
                                "Atendidas": d["cantidad_actas_atendidas"] or 0,
                                "% avance": normalize_pct(pct) or 0,
                            }
                        )
                    df_jee = pd.DataFrame(rows)
                    fig = px.bar(
                        df_jee.sort_values("% avance").head(30),
                        x="% avance",
                        y="JEE",
                        orientation="h",
                        color="% avance",
                        color_continuous_scale=["#FCA5A5", "#FDE68A", "#86EFAC"],
                        range_color=[0, 100],
                        title="Avance por JEE",
                        text="% avance",
                    )
                    fig.update_traces(texttemplate="%{text:.1f}%", textposition="inside")
                    st.plotly_chart(apply_fig_style(fig, height=620, legend=False), width="stretch")
                    st.dataframe(df_jee.sort_values(["% avance", "Expedientes"], ascending=[True, False]), hide_index=True, width="stretch", height=360)

            st.subheader("Composición y relaciones JNE")
            rel_cols = st.columns([1, 1])
            with rel_cols[0]:
                if actas:
                    df_actas_tree = pd.DataFrame([dict(r) for r in actas])
                    fig = px.treemap(
                        df_actas_tree,
                        path=[px.Constant("Actas observadas"), "tipo_eleccion"],
                        values="actas_completas",
                        title="Treemap de actas por tipo de elección",
                        color="actas_completas",
                        color_continuous_scale=["#FEE2E2", JNE_RED],
                    )
                    fig.update_traces(texttemplate="%{label}<br>%{value:,.0f}")
                    st.plotly_chart(apply_fig_style(fig, height=430), width="stretch", key="jne_type_treemap")
            with rel_cols[1]:
                if jee_detail:
                    fig = px.scatter(
                        df_jee,
                        x="Expedientes",
                        y="% avance",
                        size="Atendidas",
                        color="% avance",
                        hover_name="JEE",
                        title="Relación entre carga de expedientes y avance por JEE",
                        color_continuous_scale=["#FCA5A5", "#FDE68A", "#86EFAC"],
                        range_color=[0, 100],
                    )
                    fig.update_traces(marker=dict(opacity=0.82, line=dict(width=1, color="white")))
                    fig.update_xaxes(title="Expedientes")
                    fig.update_yaxes(title="% de avance", range=[0, 105])
                    st.plotly_chart(apply_fig_style(fig, height=430), width="stretch", key="jne_load_progress_scatter")


    with jne_tabs[1]:
        st.subheader("JNE evolución")
        if latest_jne is None:
            st.warning("No hay datos JNE en la base.")
        else:
            kpis = get_kpis(latest_jne)
            kpi_names = list(dict.fromkeys(k["measure_name"] for k in kpis))

            priority_kpis = [
                ("ActasObservadas.ActasProcesadas", "Actas procesadas", JNE_RED, False),
                ("ActasObservadas.ActasRecuento", "Actas enviadas a recuento", AMBER, False),
                ("ActasObservadas.MedidaAudienciasRealizadas", "Audiencias realizadas", GREEN, False),
                ("ActasObservadas.ExpedientesFaltantes", "Expedientes faltantes", "#6B7280", False),
            ]
            metric_cols = st.columns(4)
            for col, (name, label, _, pct_like) in zip(metric_cols, priority_kpis):
                hist_df = kpi_history_df(name)
                latest = hist_df["Valor"].iloc[-1] if not hist_df.empty else kpi_value(jne_kpis, name)
                delta = hist_df["Valor"].iloc[-1] - hist_df["Valor"].iloc[-2] if len(hist_df) > 1 else None
                with col:
                    st.metric(label, fmt_pct(latest, 2) if pct_like else fmt_num(latest), fmt_delta(delta, pct_like) if delta is not None else "-")

            chart_cols = st.columns(2)
            for idx, (name, label, color, _) in enumerate(priority_kpis):
                hist_df = kpi_history_df(name)
                with chart_cols[idx % 2]:
                    if len(hist_df) > 1:
                        fig = go.Figure()
                        add_line_trace(fig, hist_df, "Fecha", "Valor", label, color)
                        fig.update_layout(title=label, yaxis_title="Cantidad")
                        st.plotly_chart(apply_fig_style(fig, height=310, legend=False), width="stretch")
                    else:
                        st.info(f"Se necesitan al menos 2 corridas para {label.lower()}.")

            totals_history = get_jee_totals_history()
            if totals_history and len(totals_history) > 1:
                df_total = pd.DataFrame([dict(r) for r in totals_history])
                df_total["Fecha"] = pd.to_datetime(df_total["scraped_at"])
                fig = go.Figure()
                for col_name, label, color in [
                    ("total_expedientes", "Expedientes completos", JNE_RED),
                    ("total_ajustado", "Expedientes ajustados", "#6B7280"),
                    ("total_atendidas", "Actas atendidas", GREEN),
                ]:
                    add_line_trace(fig, df_total, "Fecha", col_name, label, color)
                fig.update_layout(title="Totales JEE acumulados", yaxis_title="Expedientes / actas")
                st.plotly_chart(apply_fig_style(fig, height=380), width="stretch")
                if all(df_total[col].iloc[-1] == df_total[col].iloc[-2] for col in ["total_expedientes", "total_ajustado", "total_atendidas"]):
                    st.caption("Las últimas capturas del JNE no muestran variación; esto es esperable con datos de ensayo ya estabilizados.")
            else:
                st.info("Se necesitan al menos 2 corridas JNE para totales.")

            jee_detail = get_jje_detail(latest_jne)
            if jee_detail:
                latest_jee_rows = []
                for d in jee_detail:
                    latest_jee_rows.append(
                        {
                            "JEE": d["jee_name"],
                            "Expedientes": d["expedientes_completos"] or 0,
                            "Actas atendidas": d["cantidad_actas_atendidas"] or 0,
                        }
                    )
                df_latest_jee = pd.DataFrame(latest_jee_rows)
                col_load, col_selector = st.columns([1.15, 1])
                with col_load:
                    fig = px.bar(
                        df_latest_jee.sort_values("Expedientes", ascending=False).head(20).sort_values("Expedientes"),
                        x="Expedientes",
                        y="JEE",
                        orientation="h",
                        title="JEE con mayor carga de expedientes",
                        color_discrete_sequence=[JNE_RED],
                        text="Expedientes",
                    )
                    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
                    st.plotly_chart(apply_fig_style(fig, height=520, legend=False), width="stretch")
                with col_selector:
                    jee_names = ["Seleccionar JEE"] + [d["jee_name"] for d in jee_detail]
                    jee_sel = st.selectbox("Evolución por Jurado Electoral Especial", jee_names)
                if jee_sel != "Seleccionar JEE":
                    jee_hist = get_jee_detail_history(jee_sel)
                    if jee_hist and len(jee_hist) > 1:
                        df_jee = pd.DataFrame([dict(r) for r in jee_hist])
                        df_jee["Fecha"] = pd.to_datetime(df_jee["scraped_at"])
                        fig = go.Figure()
                        for col_name, label, color in [
                            ("expedientes_completos", "Expedientes completos", JNE_RED),
                            ("expedientes_ajustado", "Expedientes ajustados", "#6B7280"),
                            ("cantidad_actas_atendidas", "Actas atendidas", GREEN),
                        ]:
                            add_line_trace(fig, df_jee, "Fecha", col_name, label, color)
                        fig.update_layout(title=f"{jee_sel}: evolución", yaxis_title="Cantidad")
                        st.plotly_chart(apply_fig_style(fig, height=420), width="stretch")
                    else:
                        st.info("Se necesitan al menos 2 corridas para ese JEE.")

            st.caption(f"Corridas JNE almacenadas: {source_counts.get('jne', 0)}")


with tabs[3]:
    st.subheader("Monitoreo")
    st.caption("Seguimiento operativo de los agentes que consultan ONPE y JNE. Cadencia objetivo: una captura cada 15 minutos.")

    onpe_health = source_health(runs_df, "onpe")
    jne_health = source_health(runs_df, "jne")
    cols = st.columns(4)
    with cols[0]:
        metric_card(
            "Agente ONPE",
            onpe_health["status"],
            f"Última captura: {onpe_health['latest'].strftime('%Y-%m-%d %H:%M') if onpe_health['latest'] is not None else '-'}",
            pill=f"{onpe_health['count']} capturas",
            pill_kind=onpe_health["pill_kind"],
        )
    with cols[1]:
        metric_card(
            "Brecha ONPE",
            fmt_age(onpe_health["age_minutes"]),
            "Tiempo desde la última captura registrada",
            pill="15 min objetivo",
            pill_kind="info",
        )
    with cols[2]:
        metric_card(
            "Agente JNE",
            jne_health["status"],
            f"Última captura: {jne_health['latest'].strftime('%Y-%m-%d %H:%M') if jne_health['latest'] is not None else '-'}",
            pill=f"{jne_health['count']} capturas",
            pill_kind=jne_health["pill_kind"],
        )
    with cols[3]:
        metric_card(
            "Brecha JNE",
            fmt_age(jne_health["age_minutes"]),
            "Tiempo desde la última captura registrada",
            pill="15 min objetivo",
            pill_kind="info",
        )

    st.info(
        "Para el 7 de junio de 2026 desde las 17:00, la lectura esperada es: primero movimiento en ONPE; "
        "luego ingreso progresivo del JNE para actas observadas, expedientes, recuentos y pronunciamientos."
    )

    st.subheader("Alertas automáticas")
    st.dataframe(global_alerts_df, hide_index=True, width="stretch")

    st.subheader("Detector de cambios reales")
    change_cols = st.columns(2)
    for col, change in zip(change_cols, [global_onpe_change, global_jne_change]):
        with col:
            metric_card(
                change["Fuente"],
                change["Estado"],
                change["Detalle"],
                pill="fuente cambió" if change["Cambió"] else "sin cambio",
                pill_kind="ok" if change["Cambió"] else "warn",
            )

    monitor_df = runs_df.copy()
    monitor_df["Fuente"] = monitor_df["source"].map(source_label)
    monitor_df["Captura"] = monitor_df.groupby("source").cumcount() + 1

    cols = st.columns([1.2, 1])
    with cols[0]:
        fig = px.scatter(
            monitor_df,
            x="Fecha",
            y="Fuente",
            color="Fuente",
            size="Captura",
            title="Línea de tiempo de capturas",
            color_discrete_map={"ONPE": ONPE_BLUE, "JNE": JNE_RED},
            hover_data={"Captura": True, "source": False},
        )
        fig.update_traces(marker=dict(opacity=0.9, line=dict(width=1, color="white")))
        st.plotly_chart(apply_fig_style(fig, height=340), width="stretch")
    with cols[1]:
        runs_count = monitor_df.groupby("Fuente", as_index=False).size().rename(columns={"size": "Capturas"})
        fig = px.bar(
            runs_count,
            x="Fuente",
            y="Capturas",
            color="Fuente",
            text="Capturas",
            title="Capturas almacenadas por fuente",
            color_discrete_map={"ONPE": ONPE_BLUE, "JNE": JNE_RED},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False)
        st.plotly_chart(apply_fig_style(fig, height=340, legend=False), width="stretch")

    gaps_df = monitor_df.sort_values(["source", "Fecha"]).copy()
    gaps_df["Minutos entre capturas"] = gaps_df.groupby("source")["Fecha"].diff().dt.total_seconds() / 60
    gaps_df = gaps_df.dropna(subset=["Minutos entre capturas"])
    if not gaps_df.empty:
        fig = px.bar(
            gaps_df,
            x="Fecha",
            y="Minutos entre capturas",
            color="Fuente",
            barmode="group",
            title="Brecha entre capturas consecutivas",
            color_discrete_map={"ONPE": ONPE_BLUE, "JNE": JNE_RED},
        )
        fig.add_hline(y=15, line_dash="dash", line_color=AMBER, annotation_text="Cadencia objetivo")
        st.plotly_chart(apply_fig_style(fig, height=360), width="stretch")
    else:
        st.info("Aún no hay suficientes capturas por fuente para calcular brechas.")

    st.subheader("Variación detectada por los agentes")
    variation_cols = st.columns(2)
    with variation_cols[0]:
        totals_hist = get_onpe_totals_history()
        if totals_hist and len(totals_hist) > 1:
            df_onpe_var = pd.DataFrame([dict(r) for r in totals_hist]).sort_values("run_id")
            onpe_rows = []
            for col_name, label, pct_like in [
                ("contabilizadas", "Actas contabilizadas", False),
                ("participacion", "Participación", True),
                ("votos_validos", "Votos válidos", False),
                ("votos_emitidos", "Votos emitidos", False),
            ]:
                latest = df_onpe_var[col_name].iloc[-1]
                delta = df_onpe_var[col_name].iloc[-1] - df_onpe_var[col_name].iloc[-2]
                onpe_rows.append(
                    {
                        "Indicador ONPE": label,
                        "Último valor": fmt_pct(latest) if pct_like else fmt_num(latest),
                        "Variación anterior": fmt_delta(delta, pct_like),
                    }
                )
            st.dataframe(pd.DataFrame(onpe_rows), hide_index=True, width="stretch")
        else:
            st.info("ONPE necesita al menos 2 capturas para calcular variación.")
    with variation_cols[1]:
        jne_rows = []
        for name in [
            "ActasObservadas.ActasProcesadas",
            "ActasObservadas.ActasRecuento",
            "ActasObservadas.ActasEnTramite",
            "ActasObservadas.ExpedientesFaltantes",
        ]:
            hist_df = kpi_history_df(name)
            if len(hist_df) > 1:
                latest = hist_df["Valor"].iloc[-1]
                delta = hist_df["Valor"].iloc[-1] - hist_df["Valor"].iloc[-2]
                jne_rows.append(
                    {
                        "Indicador JNE": kpi_label(name),
                        "Último valor": fmt_num(latest),
                        "Variación anterior": fmt_delta(delta),
                    }
                )
        if jne_rows:
            st.dataframe(pd.DataFrame(jne_rows), hide_index=True, width="stretch")
        else:
            st.info("JNE necesita al menos 2 capturas con KPIs numéricos para calcular variación.")

    st.subheader("Bitácora de eventos electorales")
    if not global_events_df.empty:
        st.dataframe(global_events_df.head(20), hide_index=True, width="stretch", height=360)
    else:
        st.info("Todavía no hay eventos suficientes para construir la bitácora.")

    st.subheader("Últimas capturas")
    display_runs = monitor_df.sort_values("Fecha", ascending=False).copy()
    display_runs["Fecha"] = display_runs["Fecha"].dt.strftime("%Y-%m-%d %H:%M:%S")
    display_runs = display_runs.rename(columns={"id": "Run ID"})
    st.dataframe(display_runs[["Run ID", "Fuente", "Fecha"]], hide_index=True, width="stretch", height=260)


with tabs[4]:
    st.subheader("Actualización")
    st.caption("Vista compacta para seguimiento continuo: margen, participación, frescura, alertas y últimos eventos.")

    night_margin = margin_summary(global_top_candidates)
    night_leader = night_margin["leader"]
    night_second = night_margin["second"]
    alert_count = len(global_alerts_df[global_alerts_df["Nivel"].isin(["Alerta", "Atención", "Revisar"])])

    cols = st.columns(3)
    with cols[0]:
        metric_card(
            "Estado general",
            "Atención" if alert_count else "OK",
            f"{alert_count} alerta(s) operativas activas",
            pill="actualización",
            pill_kind="warn" if alert_count else "ok",
        )
    with cols[1]:
        metric_card(
            "Lidera ONPE",
            candidate_label(night_leader).split()[0] if night_leader else "-",
            f"{candidate_label(night_leader)} · {night_leader.get('nombre_partido', '-').title() if night_leader else '-'}",
            pill=fmt_pct(night_leader.get("pct_validos"), 2) if night_leader else "-",
            pill_kind="ok",
        )
    with cols[2]:
        metric_card(
            "Margen",
            fmt_num(night_margin["votes"]),
            f"{night_margin['pp']:.2f} pp sobre {candidate_label(night_second)}" if night_margin["pp"] is not None else "-",
            pill="votos válidos",
            pill_kind="info",
        )

    cols = st.columns(2)
    with cols[0]:
        metric_card(
            "ONPE",
            short_health_status(global_onpe_health["status"]),
            f"Última captura: {global_onpe_health['latest'].strftime('%H:%M') if global_onpe_health['latest'] is not None else '-'}",
            pill=fmt_age(global_onpe_health["age_minutes"]),
            pill_kind=global_onpe_health["pill_kind"],
        )
    with cols[1]:
        metric_card(
            "JNE",
            short_health_status(global_jne_health["status"]),
            f"Última captura: {global_jne_health['latest'].strftime('%H:%M') if global_jne_health['latest'] is not None else '-'}",
            pill=fmt_age(global_jne_health["age_minutes"]),
            pill_kind=global_jne_health["pill_kind"],
        )

    st.subheader("Panel de decisión rápida")
    decision_cols = st.columns([1.05, 1])
    with decision_cols[0]:
        st.dataframe(global_alerts_df.head(6), hide_index=True, width="stretch", height=250)
        st.dataframe(
            pd.DataFrame([global_onpe_change, global_jne_change])[["Fuente", "Estado", "Detalle"]],
            hide_index=True,
            width="stretch",
        )
    with decision_cols[1]:
        if global_top_candidates:
            night_df = pd.DataFrame(global_top_candidates[:5])
            night_df["Etiqueta"] = night_df.apply(candidate_label, axis=1)
            night_df["Color"] = night_df.apply(party_color, axis=1)
            night_df["Votos texto"] = night_df["votos_validos"].map(lambda x: f"{safe_int(x) / 1_000_000:.2f}M")
            fig = px.bar(
                night_df.sort_values("votos_validos"),
                x="votos_validos",
                y="Etiqueta",
                orientation="h",
                title="Primeras candidaturas por votos",
                text="Votos texto",
                color="Etiqueta",
                color_discrete_sequence=night_df.sort_values("votos_validos")["Color"].tolist(),
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_xaxes(tickformat=".2s", title="Votos")
            fig.update_layout(showlegend=False)
            st.plotly_chart(apply_fig_style(fig, height=360, legend=False), width="stretch", key="night_top_candidates")

    cols = st.columns([1, 1, 1])
    with cols[0]:
        st.plotly_chart(gauge("Actas ONPE", global_totals.get("actas_contabilizadas"), ONPE_BLUE), width="stretch", key="night_onpe_gauge")
    with cols[1]:
        st.plotly_chart(gauge("Participación", global_totals.get("participacion"), GREEN), width="stretch", key="night_participation_gauge")
    with cols[2]:
        st.plotly_chart(gauge("Avance JNE", kpi_value(jne_kpis, "ActasObservadas.PorcentajeAvance"), JNE_RED), width="stretch", key="night_jne_gauge")

    st.subheader("Últimos eventos")
    if not global_events_df.empty:
        st.dataframe(global_events_df.head(10), hide_index=True, width="stretch", height=260)
    else:
        st.info("Todavía no hay eventos registrados.")
