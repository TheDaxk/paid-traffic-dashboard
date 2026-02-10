-- ============================
-- Paid Traffic Dashboard (MVP)
-- Sem login (por enquanto)
-- Banco: Postgres (ex: Supabase)
-- ============================

-- CLIENTES
create table if not exists clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

-- CONTAS DE ANÚNCIO (por cliente, e por plataforma)
create table if not exists ad_accounts (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references clients(id) on delete cascade,
  platform text not null check (platform in ('meta','google')),
  account_id text not null,
  account_name text,
  created_at timestamptz not null default now(),
  unique (platform, account_id)
);

-- MÉTRICAS DIÁRIAS (agregado por dia + campanha)
create table if not exists daily_metrics (
  id bigint generated always as identity primary key,
  date date not null,
  platform text not null check (platform in ('meta','google')),
  client_id uuid not null references clients(id) on delete cascade,
  account_id text not null,
  campaign_id text,
  campaign_name text,

  spend numeric(12,2) default 0,
  impressions bigint default 0,
  reach bigint default 0,
  clicks bigint default 0,

  leads bigint default 0,
  conversations bigint default 0,
  conversions bigint default 0,
  revenue numeric(12,2) default 0,

  updated_at timestamptz not null default now(),
  unique (date, platform, client_id, account_id, campaign_id)
);

create index if not exists idx_daily_metrics_client_date
on daily_metrics (client_id, date);

create index if not exists idx_daily_metrics_platform_date
on daily_metrics (platform, date);
