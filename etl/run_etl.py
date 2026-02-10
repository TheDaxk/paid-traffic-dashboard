import os
from datetime import date, timedelta
from dotenv import load_dotenv
from db import exec_sql
from etl.meta_fetch import fetch_meta_daily
from etl.google_fetch import fetch_google_daily

load_dotenv()

def upsert_rows(rows):
    sql = """
    insert into daily_metrics
    (date, platform, client_id, account_id, campaign_id, campaign_name,
     spend, impressions, reach, clicks, leads, conversations, conversions, revenue, updated_at)
    values
    (:date, :platform, :client_id, :account_id, :campaign_id, :campaign_name,
     :spend, :impressions, :reach, :clicks, :leads, :conversations, :conversions, :revenue, now())
    on conflict (date, platform, client_id, account_id, campaign_id)
    do update set
      campaign_name = excluded.campaign_name,
      spend = excluded.spend,
      impressions = excluded.impressions,
      reach = excluded.reach,
      clicks = excluded.clicks,
      leads = excluded.leads,
      conversations = excluded.conversations,
      conversions = excluded.conversions,
      revenue = excluded.revenue,
      updated_at = now();
    """
    for r in rows:
        exec_sql(sql, r)

def main():
    end = date.today()
    start = end - timedelta(days=14)

    client_id = os.getenv("ETL_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Defina ETL_CLIENT_ID no .env para rodar o ETL para um cliente específico.")

    meta_rows = fetch_meta_daily(client_id, start, end)
    google_rows = fetch_google_daily(client_id, start, end)

    upsert_rows(meta_rows + google_rows)
    print(f"OK: gravou {len(meta_rows) + len(google_rows)} linhas")

if __name__ == "__main__":
    main()
