-- Supabase SQL Editor에서 한 번 실행
create table if not exists public.messages (
  id bigint generated always as identity primary key,
  content text not null,
  created_at timestamptz not null default now()
);
alter table public.messages enable row level security;
-- secret key는 RLS를 우회하므로 정책은 필요 없음 (anon 접근은 차단됨)
