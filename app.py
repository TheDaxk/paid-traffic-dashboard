import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from db import fetch_df

load_dotenv()

st.set_page_config(
    page_title=os.getenv("APP_TITLE", "Dashboard"),
    page_icon="📊",
    layout="wide",
)

# ---------- DB cache ----------
@st.cache_data(ttl=60)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    return fetch_df(sql, params)

# ---------- Helpers ----------
def brl(x: float) -> str:
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def intfmt(x: int) -> str:
    return f"{x:,}".replace(",", ".")

def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0

def compute_kpis(df: pd.DataFrame) -> dict:
    spend = float(df["spend"].sum()) if not df.empty else 0.0
    imps = int(df["impressions"].sum()) if not df.empty else 0
    clicks = int(df["clicks"].sum()) if not df.empty else 0
    convos = int(df["conversations"].sum()) if not df.empty else 0
    leads = int(df["leads"].sum()) if not df.empty else 0
    conversions = int(df["conversions"].sum()) if not df.empty else 0

    cpc = safe_div(spend, clicks)
    ctr = safe_div(clicks, imps) * 100
    cpm = safe_div(spend, imps) * 1000
    total_actions = convos + leads + conversions
    cpa = safe_div(spend, total_actions)
    cpconv = safe_div(spend, convos)

    return dict(
        spend=spend,
        impressions=imps,
        clicks=clicks,
        conversations=convos,
        leads=leads,
        conversions=conversions,
        cpc=cpc,
        ctr=ctr,
        cpm=cpm,
        cpa=cpa,
        cpconv=cpconv,
    )

def delta_pct(curr: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return (curr - prev) / prev * 100

# ---------- CSS ----------
st.markdown(
    """
<style>
header, footer {visibility: hidden;}
div[data-testid="metric-container"]{
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  padding: 14px 14px 10px 14px;
  border-radius: 14px;
}
div[data-testid="metric-container"]{
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  padding: 14px 14px 10px 14px;
  border-radius: 14px;

  opacity: 0;
  transform: translateY(12px);
  animation: fadeUp .45s ease-out forwards;
}

div[data-testid="metric-container"]:nth-child(1){animation-delay:.00s;}
div[data-testid="metric-container"]:nth-child(2){animation-delay:.05s;}
div[data-testid="metric-container"]:nth-child(3){animation-delay:.10s;}
div[data-testid="metric-container"]:nth-child(4){animation-delay:.15s;}
div[data-testid="metric-container"]:nth-child(5){animation-delay:.20s;}
div[data-testid="metric-container"]:nth-child(6){animation-delay:.25s;}

@keyframes fadeUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

</style>
""",
    unsafe_allow_html=True,
)

st.title(os.getenv("APP_TITLE", "Vivendas Do Joia"))

# ---------- Clients (precisa vir ANTES do período, pra descobrir min/max) ----------
clients = q("select id, name from clients order by name asc")
if clients.empty:
    st.info("Nenhum cliente cadastrado. Crie uma linha na tabela `clients` no Supabase.")
    st.stop()

client_name_to_id = dict(zip(clients["name"], clients["id"].astype(str)))

# ---------- Sidebar filters ----------
st.sidebar.header("Filtros")
client_name = st.sidebar.selectbox("Cliente", list(client_name_to_id.keys()))
client_id = client_name_to_id[client_name]

minmax = q(
    "select min(date) as min_date, max(date) as max_date from daily_metrics where client_id = :client_id",
    {"client_id": client_id},
)
if minmax.empty or pd.isna(minmax.iloc[0]["min_date"]):
    st.warning("Esse cliente ainda não tem dados em `daily_metrics`. Rode o ETL para popular.")
    st.stop()

min_date = minmax.iloc[0]["min_date"]
max_date = minmax.iloc[0]["max_date"]

platforms = st.sidebar.multiselect("Plataformas", ["meta", "google"], default=["meta", "google"])
search_campaign = st.sidebar.text_input("Buscar campanha (contém)", placeholder="ex: Mensagens")

# ---------- Período no topo (mobile-friendly) ----------
st.markdown("### 📅 Período")

preset = st.radio(
    "Atalho rápido",
    ["7 dias", "15 dias", "30 dias", "Todo período", "Personalizado"],
    horizontal=True,
    index=0,
    key="preset_choice",
)

# Defaults por preset (sempre em date)
_min = pd.to_datetime(min_date).date()
_max = pd.to_datetime(max_date).date()

default_start, default_end = _min, _max
if preset == "7 dias":
    default_start, default_end = (pd.to_datetime(_max) - pd.Timedelta(days=6)).date(), _max
elif preset == "15 dias":
    default_start, default_end = (pd.to_datetime(_max) - pd.Timedelta(days=14)).date(), _max
elif preset == "30 dias":
    default_start, default_end = (pd.to_datetime(_max) - pd.Timedelta(days=29)).date(), _max
elif preset == "Todo período":
    default_start, default_end = _min, _max

# Se o usuário mudou o preset, atualiza as datas no session_state (evita "não muda" no mobile)
if st.session_state.get("_last_preset") != preset:
    st.session_state["start_date"] = default_start
    st.session_state["end_date"] = default_end
    st.session_state["_last_preset"] = preset

col_p1, col_p2 = st.columns([1, 1])
with col_p1:
    start = st.date_input(
        "Data inicial",
        value=st.session_state.get("start_date", default_start),
        min_value=_min,
        max_value=_max,
        key="start_date",
    )

with col_p2:
    end = st.date_input(
        "Data final",
        value=st.session_state.get("end_date", default_end),
        min_value=_min,
        max_value=_max,
        key="end_date",
    )

if start > end:
    st.error("⚠️ A data inicial não pode ser maior que a final.")
    st.stop()

# ---------- Build filters ----------
platform_filter = ""
params = {"client_id": client_id, "start": start, "end": end}
if platforms:
    platform_filter = "and platform = any(:platforms)"
    params["platforms"] = platforms

campaign_filter = ""
if search_campaign.strip():
    campaign_filter = "and lower(coalesce(campaign_name,'')) like :q"
    params["q"] = f"%{search_campaign.strip().lower()}%"
# ---------- Data query ----------
df = q(
    f"""
    select
      date,
      platform,
      campaign_id,
      campaign_name,
      spend,
      impressions,
      clicks,
      leads,
      conversations,
      conversions
    from daily_metrics
    where client_id = :client_id
      and date between :start and :end
      {platform_filter}
      {campaign_filter}
    order by date asc
    """,
    params,
)

# Pre-compute heavy aggregations ONCE per rerun (used in multiple tabs)
daily_agg = (
    df.groupby(["date", "platform"], as_index=False)[["spend", "impressions", "clicks", "conversations"]].sum()
    if not df.empty
    else df
)

camp_agg = None
if not df.empty:
    df2 = df.copy()
    df2["campaign_name"] = df2["campaign_name"].fillna("(sem nome)")
    camp_agg = df2.groupby(["platform", "campaign_name"], as_index=False)[
        ["spend", "impressions", "clicks", "leads", "conversations", "conversions"]
    ].sum()

# ---------- Previous period for deltas ----------
period_days = (pd.to_datetime(end) - pd.to_datetime(start)).days + 1
prev_end = pd.to_datetime(start) - pd.Timedelta(days=1)
prev_start = prev_end - pd.Timedelta(days=period_days - 1)

params_prev = {"client_id": client_id, "start": prev_start.date(), "end": prev_end.date()}
if platforms:
    params_prev["platforms"] = platforms

df_prev = q(
    f"""
    select spend, impressions, clicks, leads, conversations, conversions
    from daily_metrics
    where client_id = :client_id
      and date between :start and :end
      {platform_filter}
    """,
    params_prev,
)

k = compute_kpis(df)
k_prev = compute_kpis(df_prev)

# ---------- Tabs ----------
tab1, tab2, tab3 = st.tabs(["📌 Visão Geral", "🎯 Campanhas", "🧾 Dados"])

with tab1:
    # ---------- KPIs (grid mobile-first) ----------
    d_spend = delta_pct(k["spend"], k_prev["spend"])
    d_clicks = delta_pct(k["clicks"], k_prev["clicks"])
    d_imps = delta_pct(k["impressions"], k_prev["impressions"])
    d_cpc = delta_pct(k["cpc"], k_prev["cpc"])
    d_convos = delta_pct(k["conversations"], k_prev["conversations"])
    d_cpconv = delta_pct(k["cpconv"], k_prev["cpconv"])

    kpis = [
        ("Investimento", brl(k["spend"]), d_spend),
        ("Impressões", intfmt(k["impressions"]), d_imps),
        ("Cliques", intfmt(k["clicks"]), d_clicks),
        ("CPC", brl(k["cpc"]), d_cpc),
        ("Conversas", intfmt(k["conversations"]), d_convos),
        ("Custo / Conversa", brl(k["cpconv"]), d_cpconv),
    ]

    def fmt_delta(d):
        return f"{d:+.1f}%" if d is not None else None

    # 2 KPIs por linha (mobile perfeito)
    cols_per_row = 2

    for i in range(0, len(kpis), cols_per_row):
        row = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx < len(kpis):
                label, value, delta = kpis[idx]
                row[j].metric(label, value, fmt_delta(delta))

    st.divider()

    left, right = st.columns([2, 2])

    with left:
        st.subheader("Evolução no período")

        metric_choice = st.selectbox(
            "Métrica",
            ["Investimento", "Cliques", "Impressões", "Conversas", "CPC", "Custo/Conversa"],
            index=0,
        )
        grouping = st.radio("Quebra", ["Total", "Por plataforma"], horizontal=True)

        if df.empty:
            st.info("Sem dados no período selecionado.")
        else:
            daily = daily_agg.copy()

            if metric_choice == "Investimento":
                daily["value"] = daily["spend"]
            elif metric_choice == "Cliques":
                daily["value"] = daily["clicks"]
            elif metric_choice == "Impressões":
                daily["value"] = daily["impressions"]
            elif metric_choice == "Conversas":
                daily["value"] = daily["conversations"]
            elif metric_choice == "CPC":
                daily["value"] = (daily["spend"] / daily["clicks"].replace(0, pd.NA)).fillna(0)
            elif metric_choice == "Custo/Conversa":
                daily["value"] = (daily["spend"] / daily["conversations"].replace(0, pd.NA)).fillna(0)

            if grouping == "Total":
                chart_df = daily.groupby("date", as_index=False)[["value"]].sum()
                st.line_chart(chart_df.set_index("date"))
            else:
                pivot = (
                    daily.pivot_table(index="date", columns="platform", values="value", aggfunc="sum")
                    .fillna(0)
                    .sort_index()
                )
                st.line_chart(pivot)

    with right:
        st.subheader("Investimento por plataforma")
        if df.empty:
            st.info("Sem dados no período selecionado.")
        else:
            by_plat = df.groupby("platform", as_index=False)[["spend", "clicks", "impressions", "conversations"]].sum()
            st.dataframe(by_plat.sort_values("spend", ascending=False), use_container_width=True)

with tab2:
    st.subheader("Resumo por campanha (ordenado por investimento)")

    if df.empty or camp_agg is None or camp_agg.empty:
        st.info("Sem dados no período/filtros selecionados.")
        st.stop()

    camp = camp_agg.copy()

    # métricas derivadas (vetorizadas)
    camp["CTR_%"] = (camp["clicks"] / camp["impressions"].replace(0, pd.NA) * 100).fillna(0)
    camp["CPC"] = (camp["spend"] / camp["clicks"].replace(0, pd.NA)).fillna(0)
    camp["Ações"] = camp["leads"] + camp["conversations"] + camp["conversions"]
    camp["CPA"] = (camp["spend"] / camp["Ações"].replace(0, pd.NA)).fillna(0)
    camp["Custo_Conv"] = (camp["spend"] / camp["conversations"].replace(0, pd.NA)).fillna(0)

    camp = camp.sort_values("spend", ascending=False)

    show = camp.copy()
    show.rename(columns={"spend": "Investimento"}, inplace=True)
    show["Investimento"] = show["Investimento"].map(brl)
    show["CPC"] = show["CPC"].map(brl)
    show["CPA"] = show["CPA"].map(brl)
    show["Custo_Conv"] = show["Custo_Conv"].map(brl)
    show["CTR_%"] = show["CTR_%"].map(lambda x: f"{x:.2f}%")

    st.dataframe(show, use_container_width=True)

with tab3:
    st.subheader("Dados brutos (para auditoria/exports)")
    st.dataframe(df, use_container_width=True)

    st.download_button(
        "Baixar CSV (filtros aplicados)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="metrics_filtered.csv",
        mime="text/csv",
    )
