// เทสต์ตัวฝากสกิล (การ์ด 0080 รอบ 2 · เกณฑ์ H3 R1) · ใช้ KV จำลอง ไม่แตะ Cloudflare จริง · รัน: node --test server/share-worker/worker.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import worker from "./worker.mjs";

const SKILL = "---\nid: fridge-menu\nname: คิดเมนูจากของในตู้เย็น\n---\nเนื้อหา";

class FakeKV {
  constructor() {
    this.items = new Map();
    this.writes = 0;
    this.quotaLeft = Infinity;
  }

  async get(key) {
    const item = this.items.get(key);
    if (!item || item.expires <= Date.now()) {
      return null;
    }
    return item.value;
  }

  async put(key, value, options = {}) {
    if (this.quotaLeft <= 0) {
      throw new Error("KV PUT failed: 429 Too Many Requests");
    }
    this.quotaLeft -= 1;
    this.writes += 1;
    const ttl = options.expirationTtl ?? 1e9;
    this.items.set(key, { value, ttl, expires: Date.now() + ttl * 1000 });
  }
}

function post(body, ip = "203.0.113.1", headers = {}) {
  return new Request("https://share.example/v1/skills", {
    method: "POST",
    body,
    headers: { "cf-connecting-ip": ip, ...headers },
  });
}

function get(code, ip = "203.0.113.1") {
  return new Request(`https://share.example/v1/skills/${code}`, {
    headers: { "cf-connecting-ip": ip },
  });
}

async function send(env, request) {
  return worker.fetch(request, env);
}

async function share(env, body = SKILL, ip = "203.0.113.1") {
  const reply = await send(env, post(body, ip));
  assert.equal(reply.status, 201);
  return (await reply.json()).code;
}

test("ฝากแล้วรับกลับได้ตรงทุกตัวอักษร และได้เลข 8 หลัก", async () => {
  const env = { SKILLS: new FakeKV() };
  const code = await share(env);
  assert.match(code, /^[0-9]{8}$/);
  const reply = await send(env, get(code, "198.51.100.7"));
  assert.equal(reply.status, 200);
  assert.equal(await reply.text(), SKILL);
  assert.equal(reply.headers.get("cache-control"), "no-store");
});

test("เก็บไฟล์ 24 ชั่วโมงพอดี แล้วรหัสเก่าใช้ไม่ได้ (H3)", async () => {
  const env = { SKILLS: new FakeKV() };
  const code = await share(env);
  const item = env.SKILLS.items.get(`skill:${code}`);
  assert.equal(item.ttl, 86400);
  item.expires = Date.now() - 1;
  assert.equal((await send(env, get(code, "198.51.100.7"))).status, 404);
});

test("เดารหัส 10,000 ครั้งจากเครื่องเดียว ถูกบล็อกก่อนเจอรหัสจริง (H3)", async () => {
  const env = { SKILLS: new FakeKV() };
  const real = await share(env, SKILL, "198.51.100.7");
  const statuses = [];
  for (let n = 0; n < 10_000; n += 1) {
    const guess = n === 5_000 ? real : String(n).padStart(8, "0");
    statuses.push((await send(env, get(guess))).status);
  }
  assert.equal(statuses.filter((s) => s === 404).length, 10);
  assert.equal(statuses.filter((s) => s === 200).length, 0, "ต้องไม่เจอรหัสจริง");
  assert.equal(statuses.filter((s) => s === 429).length, 9_990);
  assert.ok(env.SKILLS.writes < 20, "คำขอที่ถูกบล็อกต้องไม่กินโควตาเขียน");
});

test("โควตาเขียนหมด = ปฏิเสธ ไม่ปล่อยให้เดาต่อ (fail closed)", async () => {
  const env = { SKILLS: new FakeKV() };
  const code = await share(env, SKILL, "198.51.100.7");
  env.SKILLS.quotaLeft = 0;
  assert.equal((await send(env, get(code))).status, 429);
});

test("นับแยกตามเครื่อง · IPv6 ช่วง /64 เดียวกันนับรวมกัน", async () => {
  const env = { SKILLS: new FakeKV() };
  for (let n = 0; n < 10; n += 1) {
    assert.equal((await send(env, get("00000000", "2001:db8:1:2::1"))).status, 404);
  }
  assert.equal((await send(env, get("00000000", "2001:db8:1:2::99"))).status, 429);
  assert.equal((await send(env, get("00000000", "2001:db8:1:3::1"))).status, 404);
});

test("จำกัดการฝากต่อชั่วโมง", async () => {
  const env = { SKILLS: new FakeKV() };
  for (let n = 0; n < 10; n += 1) {
    await share(env);
  }
  assert.equal((await send(env, post(SKILL))).status, 429);
});

test("ไฟล์ใหญ่เกิน ว่าง ไม่ใช่ UTF-8 หรือไม่ใช่ไฟล์สกิล = ไม่รับ", async () => {
  const env = { SKILLS: new FakeKV() };
  const huge = `---\n${"ก".repeat(6000)}`;
  assert.equal((await send(env, post(huge, "192.0.2.1"))).status, 413);
  assert.equal((await send(env, post("", "192.0.2.2"))).status, 413);
  const invalid = new Uint8Array([0x2d, 0x2d, 0x2d, 0xff, 0xfe]);
  assert.equal((await send(env, post(invalid, "192.0.2.3"))).status, 400);
  assert.equal((await send(env, post("สวัสดี", "192.0.2.4"))).status, 400);
  assert.equal([...env.SKILLS.items.keys()].filter((k) => k.startsWith("skill:")).length, 0);
});

test("ทางอื่น เมธอดอื่น และเลขผิดรูปแบบ = 404", async () => {
  const env = { SKILLS: new FakeKV() };
  for (const code of ["1234567", "123456789", "abcdefgh", "../../etc"]) {
    assert.equal((await send(env, get(code))).status, 404);
  }
  const reply = await send(env, new Request("https://share.example/v1/skills/12345678", { method: "DELETE" }));
  assert.equal(reply.status, 404);
  assert.equal(env.SKILLS.writes, 0, "คำขอผิดรูปแบบต้องไม่กินโควตา");
});
