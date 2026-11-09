# ตั้งเซิร์ฟเวอร์ฝากสกิล (เลข 8 หลัก · การ์ด 0080 รอบ 2)

ทำครั้งเดียวบนโน้ตบุ๊ก ไม่แตะ Pi · ใช้แค่เว็บเบราว์เซอร์ ไม่ต้องลงโปรแกรม · ชื่อเมนูของ Cloudflare อาจเปลี่ยนไปจากนี้

ยังไม่ทำขั้นตอนนี้ = หน้าจอซ่อนทางเลข 8 หลัก ส่วน QR ทั้งไฟล์ยังใช้ได้ตามปกติ

## ขั้นตอน

1. สมัครบัญชีฟรีที่ <https://dash.cloudflare.com/sign-up> (ไม่ต้องผูกบัตร)
2. สร้างที่เก็บข้อมูล: เมนู **Storage & Databases → KV → Create** ตั้งชื่อ `aipc-skill-share`
3. สร้างตัวรับฝาก: เมนู **Compute (Workers) → Create → Start with Hello World** ตั้งชื่อ `aipc-skill-share` แล้วกด Deploy
4. กด **Edit code** ลบของเดิมทั้งหมด วางเนื้อหาไฟล์ [`server/share-worker/worker.mjs`](../../server/share-worker/worker.mjs) แล้วกด Deploy
5. ผูกที่เก็บข้อมูล: หน้า Worker → **Settings → Bindings → Add → KV namespace** · Variable name = `SKILLS` (ตัวใหญ่ตามนี้) · เลือก `aipc-skill-share` · กด Deploy
6. คัดลอกที่อยู่ เช่น `https://aipc-skill-share.ชื่อบัญชี.workers.dev` ส่งให้ผู้ช่วยใส่ใน `SERVER_URL` ของ `src/aipc/skills/share.py`

## ทางที่ใช้จริง (2026-11-09 · wrangler)

ใช้แทนขั้นตอน 4–5 ได้ · ค่าทั้งหมดอยู่ใน [`server/share-worker/wrangler.toml`](../../server/share-worker/wrangler.toml)

1. สร้าง Worker เปล่าจากหน้าเว็บก่อน 1 ครั้ง (**Workers & Pages → Create application**) เพื่อให้บัญชีมี subdomain · ชื่อ Worker ต้องตรงกับ `name` ใน `wrangler.toml`
2. `npx --yes wrangler login` (Pakon ทำเอง · token เก็บในเครื่อง ห้าม commit)
3. `cd server/share-worker && npx --yes wrangler deploy`

subdomain ที่ Cloudflare ตั้งให้อัตโนมัติอาจมีชื่อบัญชี · เปลี่ยนได้ที่หน้า Workers & Pages แต่ที่อยู่เดิมและใหม่จะใช้ไม่ได้ชั่วครู่ (พบ TLS error ระหว่างรอ)

## ตรวจว่าใช้ได้

```bash
URL=https://aipc-skill-share.ชื่อบัญชี.workers.dev
printf -- '---\nid: test\n---\n' | curl -s -X POST --data-binary @- "$URL/v1/skills"   # ต้องได้ {"code":"########","expires_in":86400}
curl -i "$URL/v1/skills/00000000"                                                      # ต้องได้ 404
```

## สิ่งที่ต้องรู้

- โควตาฟรี (2026-11): 100,000 คำขอ/วัน · KV เขียนได้ 1,000 ครั้ง/วัน · เกินแล้วล้มเหลว ไม่เสียเงิน ·
  ทุกครั้งที่รับหรือฝาก = เขียน 1–2 ครั้ง
- จำกัด 10 ครั้ง/ชั่วโมง/IP แยกการฝากกับการรับ · ทั้งห้องใช้เน็ตวงเดียวกัน = นับรวมกัน
- ไฟล์สกิลหายเองใน 24 ชั่วโมง · เจ้าของบัญชี Cloudflare มองเห็นเนื้อไฟล์ที่ฝากอยู่ได้
- หลังจบโปรเจกต์ ถ้าปิดบริการ ทางเลขจะใช้ไม่ได้ แต่ QR ทั้งไฟล์ยังใช้ได้

## เทสต์โค้ดฝั่งเซิร์ฟเวอร์

`node --test server/share-worker/worker.test.mjs` (ใช้ KV จำลอง ไม่แตะ Cloudflare จริง)
