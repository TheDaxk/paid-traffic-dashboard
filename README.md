# Paid Traffic Dashboard (MVP) — AllPro

Este projeto entrega um dashboard simples em **Streamlit (Python)** lendo métricas salvas em **Postgres (ex: Supabase)**.
**Sem login/senha (por enquanto)**: você escolhe o cliente no sidebar.

## 1) Requisitos
- Python 3.10+
- Um Postgres (recomendado: Supabase)

## 2) Setup
1. Crie as tabelas no Supabase usando `schema.sql`
2. Copie `.env.example` para `.env` e preencha `DATABASE_URL`
3. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```

## 3) Rodar o dashboard
```bash
streamlit run app.py
```

## 4) Rodar ETL (opcional)
O ETL puxa dados e grava em `daily_metrics`.

1. No `.env`, defina `ETL_CLIENT_ID` e (opcional) variáveis de Meta/Google.
2. Rode:
   ```bash
   python etl/run_etl.py
   ```

> Nota: A integração de **Google Ads** está como stub para não travar o MVP hoje.
> Meta puxa spend/impressions/clicks/reach por campanha/dia.

## 5) Deploy rápido (Render)
- Build: `pip install -r requirements.txt`
- Start:
  ```bash
  streamlit run app.py --server.port $PORT --server.address 0.0.0.0
  ```
- Configure as mesmas variáveis do `.env` como env vars no Render.

## Próximas melhorias rápidas
- Multi-cliente automático no ETL (lendo `ad_accounts`)
- Métricas de conversas/leads (Meta actions)
- Google Ads GAQL completo
- Login por cliente (quando você quiser)
