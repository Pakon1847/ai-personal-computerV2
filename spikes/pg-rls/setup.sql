-- Spike 0.6 (ADR-004): PostgreSQL + peer auth + FORCE ROW LEVEL SECURITY
-- รันด้วย superuser postgres ผ่าน run.sh เท่านั้น · ชื่อทุกอย่างขึ้นต้นด้วย aipc_spike_ ลบทิ้งได้ด้วย cleanup.sql
--
-- แนวคิด (BRIEF 5.9 ข้อ 2): Linux user หนึ่งคน = DB role หนึ่งตัวชื่อเดียวกัน
-- ต่อเข้า DB ผ่าน Unix socket แบบ peer = PostgreSQL ถามเคอร์เนลว่าโปรเซสที่ต่อเข้ามาเป็นใคร
-- จึงปลอมตัวเป็นคนอื่นไม่ได้ ต่อให้แก้โค้ดแอปหรือยิง SQL ตรงจาก Terminal

\set ON_ERROR_STOP on

-- เจ้าของตาราง: ไม่ใช่ผู้ใช้คนไหน และล็อกอินไม่ได้ (BRIEF: แอปห้ามใช้ superuser)
CREATE ROLE aipc_spike_owner NOLOGIN;
-- ผู้ใช้สองคน · CONNECTION LIMIT กันคนที่มี Terminal เปิดการเชื่อมต่อค้างจน DB เต็ม
CREATE ROLE aipc_spike_a LOGIN CONNECTION LIMIT 5;
CREATE ROLE aipc_spike_b LOGIN CONNECTION LIMIT 5;
-- statement_timeout กัน query ที่ยิงตรงแล้วค้างนาน (ตั้งสั้นไว้เพื่อทดสอบ)
ALTER ROLE aipc_spike_b SET statement_timeout = '2s';

CREATE DATABASE aipc_spike OWNER aipc_spike_owner;
\connect aipc_spike

CREATE TABLE public.chats (
    id    bigserial PRIMARY KEY,
    owner name NOT NULL DEFAULT current_user,  -- ใครเป็นเจ้าของแถว เติมเองจากตัวตนที่ต่อเข้ามา
    body  text NOT NULL
);
ALTER TABLE public.chats OWNER TO aipc_spike_owner;

-- ENABLE = เปิด RLS · FORCE = บังคับกับเจ้าของตารางด้วย (ไม่งั้นเจ้าของตารางเห็นทุกแถว)
ALTER TABLE public.chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chats FORCE ROW LEVEL SECURITY;

-- USING = กรองแถวที่อ่าน/แก้/ลบได้ · WITH CHECK = กรองแถวที่เขียนลงไป
CREATE POLICY own_rows ON public.chats
    USING (owner = current_user)
    WITH CHECK (owner = current_user);

GRANT USAGE ON SCHEMA public TO aipc_spike_a, aipc_spike_b;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.chats TO aipc_spike_a, aipc_spike_b;
GRANT USAGE ON SEQUENCE public.chats_id_seq TO aipc_spike_a, aipc_spike_b;

-- view สองแบบ เพื่อสังเกตว่าทำไม BRIEF สั่งให้ใช้ security_invoker
CREATE VIEW public.chats_invoker WITH (security_invoker = true) AS SELECT * FROM public.chats;
CREATE VIEW public.chats_definer AS SELECT * FROM public.chats;
ALTER VIEW public.chats_invoker OWNER TO aipc_spike_owner;
ALTER VIEW public.chats_definer OWNER TO aipc_spike_owner;
GRANT SELECT ON public.chats_invoker, public.chats_definer TO aipc_spike_a, aipc_spike_b;
