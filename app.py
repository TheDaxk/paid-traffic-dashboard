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

/* ---------- KPI GRID (força 2 colunas no mobile) ---------- */
.kpi-grid{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 6px;
}

@media (max-width: 640px){
  .kpi-grid{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.kpi-card{
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
  padding: 12px 12px 10px 12px;

  opacity: 0;
  transform: translateY(10px);
  animation: fadeUp .45s ease-out forwards;
}

.kpi-title{
  font-size: 12px;
  opacity: .75;
  margin-bottom: 4px;
}

.kpi-value{
  font-size: 20px;
  font-weight: 700;
  line-height: 1.1;
}

.kpi-delta{
  font-size: 12px;
  margin-top: 6px;
  opacity: .85;
}

.kpi-delta.pos{ color: #30c48d; }
.kpi-delta.neg{ color: #ff5c5c; }
.kpi-delta.neu{ color: rgba(255,255,255,0.55); }

@keyframes fadeUp {
  to { opacity: 1; transform: translateY(0); }
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
(tab1,) = st.tabs(["📌 Visão Geral"])
with tab1:
    # ---------- KPIs (HTML grid: 2 cols mobile / 3 cols desktop + fade up) ----------
    d_spend  = delta_pct(k["spend"], k_prev["spend"])
    d_imps   = delta_pct(k["impressions"], k_prev["impressions"])
    d_clicks = delta_pct(k["clicks"], k_prev["clicks"])
    d_cpc    = delta_pct(k["cpc"], k_prev["cpc"])
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

    def _delta_html(d):
        if d is None:
            return '<div class="kpi-delta neu">—</div>'
        cls = "pos" if d > 0 else ("neg" if d < 0 else "neu")
        return f'<div class="kpi-delta {cls}">{d:+.1f}%</div>'

    cards = []
    for i, (title, value, d) in enumerate(kpis):
        delay = i * 0.06
        cards.append(f'''
          <div class="kpi-card" style="animation-delay:{delay:.2f}s">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            {_delta_html(d)}
          </div>
        ''')

    st.markdown(f"""
    <div class="kpi-grid">
      {''.join(cards)}
    </div>
    """, unsafe_allow_html=True)

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


