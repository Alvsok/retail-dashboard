-- Запустить в Supabase → SQL Editor

CREATE TABLE IF NOT EXISTS orders (
  id          SERIAL PRIMARY KEY,
  crm_id      TEXT UNIQUE NOT NULL,
  crm_number  TEXT,
  customer_name TEXT,
  phone       TEXT,
  email       TEXT,
  total_sum   NUMERIC DEFAULT 0,
  status      TEXT,
  city        TEXT,
  utm_source  TEXT,
  created_at  TIMESTAMPTZ,
  synced_at   TIMESTAMPTZ DEFAULT NOW(),
  alert_sent  BOOLEAN DEFAULT FALSE
);

-- Разрешить публичное чтение для дашборда
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public_read" ON orders
  FOR SELECT USING (true);
