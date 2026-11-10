-- Supabase SQL Editor에서 한 번 실행
create table if not exists public.messages (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);
alter table public.messages enable row level security;
-- secret key는 RLS를 우회하므로 정책은 필요 없음 (anon 접근은 차단됨)

-- ─────────────── 장바구니 ───────────────
create table if not exists public.products (
  id bigint generated always as identity primary key,
  name text not null unique,
  description text not null default '',
  price integer not null check (price >= 0),   -- 원(KRW)
  emoji text not null default '🍊',
  created_at timestamptz not null default now()
);

create table if not exists public.cart_items (
  id bigint generated always as identity primary key,
  cart_id text not null,                        -- 브라우저가 만든 익명 장바구니 ID
  product_id bigint not null references public.products(id) on delete cascade,
  quantity integer not null check (quantity between 1 and 99),
  created_at timestamptz not null default now(),
  unique (cart_id, product_id)
);
create index if not exists cart_items_cart_id_idx on public.cart_items (cart_id);

alter table public.products enable row level security;
alter table public.cart_items enable row level security;

-- 샘플 상품 (여러 번 실행해도 중복되지 않음)
insert into public.products (name, description, price, emoji) values
  ('한라봉 3kg',        '새콤달콤 제주 한라봉 선물세트',       28000, '🍊'),
  ('감귤 초콜릿',       '제주 감귤을 품은 수제 초콜릿 12입',   12500, '🍫'),
  ('흑돼지 오겹살 600g','쫄깃하고 고소한 제주 흑돼지',          36000, '🥓'),
  ('옥돔 구이 세트',    '손질 완료, 구워 먹기만 하면 끝',       42000, '🐟'),
  ('제주 말차 롤케이크','제주 녹차밭 말차로 만든 롤케이크',      15800, '🍰'),
  ('오메기떡 10개입',   '팥고물을 묻힌 제주 전통 떡',           18000, '🍡'),
  ('돌하르방 키링',     '여행 기념 수제 키링',                   6500, '🗿'),
  ('감귤 에이드 6병',   '탄산 가득 제주 감귤 에이드',           14000, '🥤')
on conflict (name) do nothing;
