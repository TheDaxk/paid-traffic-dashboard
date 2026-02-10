import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from db import fetch_df

@st.cache_data(ttl=60)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    return fetch_df(sql, params)


load_dotenv()
st.set_page_config(
    page_title=os.getenv("APP_TITLE", "Dashboard"),
    page_icon="📊",
    layout="wide",
)

@st.cache_data(ttl=60)
def q(sql: str, params: dict | None = None):
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
    cpconv = safe_div(spend, convos)


    cpc = safe_div(spend, clicks)
    ctr = safe_div(clicks, imps) * 100
    cpm = safe_div(spend, imps) * 1000
    total_actions = convos + leads + conversions
    cpa = safe_div(spend, total_actions)

    return dict(
        spend=spend, impressions=imps, clicks=clicks, conversations=convos,
        leads=leads, conversions=conversions, cpc=cpc, ctr=ctr, cpm=cpm, cpa=cpa,
        cpconv=cpconv
    )

def delta_pct(curr: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return (curr - prev) / prev * 100

# ---------- CSS leve ----------
st.markdown("""
<style>
/* reduzir ruído */
header, footer {visibility: hidden;}
/* cards mais “clean” */
div[data-testid="metric-container"]{
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  padding: 14px 14px 10px 14px;
  border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)

st.title(os.getenv("APP_TITLE", "Relatório de Tráfego Pago"))

# ---------- Carregar clientes ----------
clients = q("select id, name from clients order by name asc")
if clients.empty:
    st.info("Nenhum cliente cadastrado. Crie uma linha na tabela `clients` no Supabase.")
    st.stop()

client_name_to_id = dict(zip(clients["name"], clients["id"].astype(str)))

# ---------- Sidebar filtros ----------
st.sidebar.header("Filtros")
client_name = st.sidebar.selectbox("Cliente", list(client_name_to_id.keys()))
client_id = client_name_to_id[client_name]

minmax = q(
    "select min(date) as min_date, max(date) as max_date from daily_metrics where client_id = :client_id",
    {"client_id": client_id}
)
if minmax.empty or pd.isna(minmax.iloc[0]["min_date"]):
    st.warning("Esse cliente ainda não tem dados em `daily_metrics`. Rode o ETL para popular.")
    st.stop()

min_date = minmax.iloc[0]["min_date"]
max_date = minmax.iloc[0]["max_date"]

start, end = st.sidebar.date_input(
    "Período",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

platforms = st.sidebar.multiselect("Plataformas", ["meta", "google"], default=["meta", "google"])
platform_filter = ""
params = {"client_id": client_id, "start": start, "end": end}
if platforms:
    platform_filter = "and platform = any(:platforms)"
    params["platforms"] = platforms

search_campaign = st.sidebar.text_input("Buscar campanha (contém)", placeholder="ex: Mensagens")

campaign_filter = ""
if search_campaign.strip():
    campaign_filter = "and lower(coalesce(campaign_name,'')) like :q"
    params["q"] = f"%{search_campaign.strip().lower()}%"

# ---------- Query dados ----------
df = q(f"""
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
""", params)

# ---------- Período anterior para deltas ----------
period_days = (pd.to_datetime(end) - pd.to_datetime(start)).days + 1
prev_end = pd.to_datetime(start) - pd.Timedelta(days=1)
prev_start = prev_end - pd.Timedelta(days=period_days - 1)

params_prev = {"client_id": client_id, "start": prev_start.date(), "end": prev_end.date()}
if platforms:
    params_prev["platforms"] = platforms

df_prev = q(f"""
    select spend, impressions, clicks, leads, conversations, conversions
    from daily_metrics
    where client_id = :client_id
      and date between :start and :end
      {platform_filter}
""", params_prev)

k = compute_kpis(df)
k_prev = compute_kpis(df_prev)

# ---------- Tabs ----------
tab1, tab2, tab3 = st.tabs(["📌 Visão Geral", "🎯 Campanhas", "🧾 Dados"])

with tab1:
    # KPIs + deltas
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    d_spend = delta_pct(k["spend"], k_prev["spend"])
    d_clicks = delta_pct(k["clicks"], k_prev["clicks"])
    d_imps = delta_pct(k["impressions"], k_prev["impressions"])
    d_cpc = delta_pct(k["cpc"], k_prev["cpc"])
    d_convos = delta_pct(k["conversations"], k_prev["conversations"])
    d_cpconv = delta_pct(k["cpconv"], k_prev["cpconv"])

    c1.metric("Investimento", brl(k["spend"]), (f"{d_spend:+.1f}%" if d_spend is not None else None))
    c2.metric("Impressões", intfmt(k["impressions"]), (f"{d_imps:+.1f}%" if d_imps is not None else None))
    c3.metric("Cliques", intfmt(k["clicks"]), (f"{d_clicks:+.1f}%" if d_clicks is not None else None))
    c4.metric("CPC", brl(k["cpc"]), (f"{d_cpc:+.1f}%" if d_cpc is not None else None))
    c5.metric("Conversas", intfmt(k["conversations"]), (f"{d_convos:+.1f}%" if d_convos is not None else None))
    c6.metric("Custo / Conversa", brl(k["cpconv"]), (f"{d_cpconv:+.1f}%" if d_cpconv is not None else None))

    st.divider()

    left, right = st.columns([2, 2])

    with left:
        st.subheader("Evolução no período")

        metric_choice = st.selectbox(
            "Métrica",
            ["Investimento", "Cliques", "Impressões", "Conversas", "CPC", "Custo/Conversa"],
            index=0
        )
        grouping = st.radio("Quebra", ["Total", "Por plataforma"], horizontal=True)

        # Agrega por dia e plataforma
        daily = df.groupby(["date", "platform"], as_index=False)[
            ["spend", "impressions", "clicks", "conversations"]
        ].sum()

        # Define qual série será plotada (sem apply pesado quando der)
        if metric_choice == "Investimento":
            daily["value"] = daily["spend"]
        elif metric_choice == "Cliques":
            daily["value"] = daily["clicks"]
        elif metric_choice == "Impressões":
            daily["value"] = daily["impressions"]
        elif metric_choice == "Conversas":
            daily["value"] = daily["conversations"]
        elif metric_choice == "CPC":
            daily["value"] = daily["spend"] / daily["clicks"].replace(0, pd.NA)
            daily["value"] = daily["value"].fillna(0)
        elif metric_choice == "Custo/Conversa":
            daily["value"] = daily["spend"] / daily["conversations"].replace(0, pd.NA)
            daily["value"] = daily["value"].fillna(0)

        # Render
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
        by_plat = df.groupby("platform", as_index=False)[["spend", "clicks", "impressions", "conversations"]].sum()
        if by_plat.empty:
            st.info("Sem dados no período selecionado.")
        else:
            st.dataframe(by_plat.sort_values("spend", ascending=False), use_container_width=True)

with tab2:
    st.subheader("Resumo por campanha (ordenado por investimento)")

    if df.empty:
        st.info("Sem dados no período/filtros selecionados.")
        st.stop()

    df2 = df.copy()
    df2["campaign_name"] = df2["campaign_name"].fillna("(sem nome)")

    camp = df2.groupby(["platform", "campaign_name"], as_index=False)[
        ["spend", "impressions", "clicks", "leads", "conversations", "conversions"]
    ].sum()

    camp["CTR_%"] = camp.apply(lambda r: safe_div(r["clicks"], r["impressions"]) * 100, axis=1)
    camp["CPC"] = camp.apply(lambda r: safe_div(r["spend"], r["clicks"]), axis=1)
    camp["Ações"] = camp["leads"] + camp["conversations"] + camp["conversions"]
    camp["CPA"] = camp.apply(lambda r: safe_div(r["spend"], r["Ações"]), axis=1)
    camp["Custo_Conv"] = camp.apply(lambda r: safe_div(r["spend"], r["conversations"]), axis=1)

    camp = camp.sort_values("spend", ascending=False)

    # Formatação amigável
    show = camp.copy()
    show["spend"] = show["spend"].map(brl)
    show["CPC"] = show["CPC"].map(brl)
    show["CPA"] = show["CPA"].map(brl)
    show["CTR_%"] = show["CTR_%"].map(lambda x: f"{x:.2f}%")
    show["Custo_Conv"] = show["Custo_Conv"].map(brl)
    show.rename(columns={"spend": "Investimento"}, inplace=True)

    st.dataframe(show, use_container_width=True)

with tab3:
    st.subheader("Dados brutos (para auditoria/exports)")
    st.dataframe(df, use_container_width=True)

    st.download_button(
        "Baixar CSV (filtros aplicados)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="metrics_filtered.csv",
        mime="text/csv"
    )
