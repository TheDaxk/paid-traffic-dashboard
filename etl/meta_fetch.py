import os
import requests
from datetime import date

GRAPH = "https://graph.facebook.com/v19.0"

# Action types mais comuns relacionados a mensagens/conversas
CONVERSATION_ACTION_TYPES = [
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.messaging_conversation_started",   # às vezes aparece sem janela
    "messaging_conversation_started_7d",                  # variações menos comuns
    "messaging_conversation_started",
]

# (Opcional) Se você quiser mapear "leads" ou "conversões" depois, dá pra adicionar aqui também.

def _get_action_value(actions, action_type: str) -> int:
    """Extrai o value de um action_type dentro da lista actions."""
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            try:
                return int(float(a.get("value", 0) or 0))
            except (ValueError, TypeError):
                return 0
    return 0

def _sum_actions(actions, action_types: list[str]) -> int:
    """Soma valores de múltiplos action_types (útil como fallback)."""
    total = 0
    for t in action_types:
        total += _get_action_value(actions, t)
    return total

def fetch_meta_daily(client_id: str, start: date, end: date):
    token = os.getenv("META_ACCESS_TOKEN")
    act = os.getenv("META_AD_ACCOUNT_ID")  # ex: act_123
    if not token or not act:
        return []

    url = f"{GRAPH}/{act}/insights"
    params = {
        "access_token": token,
        "level": "campaign",
        "time_increment": 1,
        "time_range[since]": start.isoformat(),
        "time_range[until]": end.isoformat(),
        "fields": "date_start,campaign_id,campaign_name,spend,impressions,reach,clicks,actions",
        "limit": 500
    }

    out = []
    while True:
        r = requests.get(url, params=params, timeout=60)

        # Se der erro, imprime o corpo da resposta para facilitar debug
        if r.status_code >= 400:
            raise requests.HTTPError(f"Meta API error {r.status_code}: {r.text}", response=r)

        data = r.json()

        for it in data.get("data", []):
            actions = it.get("actions") or []

            # Conversas iniciadas (somando variações para aumentar chance de capturar)
            conversations = _sum_actions(actions, CONVERSATION_ACTION_TYPES)

            out.append({
                "date": it.get("date_start"),
                "platform": "meta",
                "client_id": client_id,
                "account_id": act,
                "campaign_id": it.get("campaign_id"),
                "campaign_name": it.get("campaign_name"),
                "spend": float(it.get("spend", 0) or 0),
                "impressions": int(it.get("impressions", 0) or 0),
                "reach": int(it.get("reach", 0) or 0),
                "clicks": int(it.get("clicks", 0) or 0),
                "leads": 0,
                "conversations": conversations,
                "conversions": 0,
                "revenue": 0
            })

        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        url = next_url
        params = None  # next_url já inclui params

    return out
