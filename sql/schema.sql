create table if not exists observations (
    id bigserial primary key,
    observed_at timestamptz not null default now(),
    source text not null,
    source_url text,
    entity text,
    observation_type text not null,
    metric text,
    value numeric,
    text_evidence text,
    reliability numeric,
    raw_metadata jsonb
);

create table if not exists trends (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    first_detected_at timestamptz,
    status text not null default 'developing',
    created_at timestamptz not null default now()
);

create table if not exists companies (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    ticker text,
    exchange text,
    market_cap numeric,
    created_at timestamptz not null default now()
);

create table if not exists theses (
    id uuid primary key default gen_random_uuid(),
    trend_id uuid references trends(id),
    company_id uuid references companies(id),
    level int not null check (level between 1 and 4),
    score numeric not null check (score between 0 and 100),
    score_delta numeric default 0,
    thesis_text text,
    catalyst text,
    bear_case text,
    invalidation text,
    would_consider_buying boolean default false,
    as_of timestamptz not null default now(),
    status text not null default 'active'
);

create table if not exists thesis_evidence (
    id bigserial primary key,
    thesis_id uuid references theses(id) on delete cascade,
    observation_id bigint references observations(id),
    direction text not null check (direction in ('supports','contradicts')),
    points numeric not null,
    created_at timestamptz not null default now()
);

create table if not exists thesis_snapshots (
    id bigserial primary key,
    thesis_id uuid references theses(id) on delete cascade,
    captured_at timestamptz not null default now(),
    score numeric not null,
    stock_price numeric,
    notes text
);

create table if not exists outcomes (
    id bigserial primary key,
    thesis_id uuid references theses(id) on delete cascade,
    horizon_days int not null,
    measured_at timestamptz not null default now(),
    stock_return_pct numeric,
    benchmark_return_pct numeric,
    max_drawdown_pct numeric,
    thesis_status text,
    notes text
);

create index if not exists observations_entity_time_idx
    on observations(entity, observed_at desc);

create index if not exists theses_score_idx
    on theses(score desc, as_of desc);
