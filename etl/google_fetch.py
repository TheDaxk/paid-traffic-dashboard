import os
from datetime import date

def fetch_google_daily(client_id: str, start: date, end: date):
    dev_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    refresh = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")

    # Se não tiver credenciais, não quebra o ETL (retorna vazio)
    if not (dev_token and refresh and customer_id):
        return []

    # Implementação real (depois): google-ads client + GAQL por segments.date e campaign
    return []
