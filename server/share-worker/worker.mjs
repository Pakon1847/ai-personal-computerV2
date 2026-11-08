// ฝากไฟล์สกิลไว้ 24 ชั่วโมง แลกเป็นเลข 8 หลัก (การ์ด 0080 รอบ 2) · รันบน Cloudflare Workers + KV
//
//   POST /v1/skills            ส่งตัวไฟล์สกิล → 201 {"code":"12345678","expires_in":86400}
//   GET  /v1/skills/12345678   ได้ตัวไฟล์สกิลกลับ · ไม่มีหรือหมดอายุ = 404 · ขอถี่เกิน = 429
//
// เก็บแค่ข้อความของไฟล์สกิล (เป็นข้อมูล ไม่ใช่โปรแกรม) · เครื่องผู้รับต้องตรวจด้วยด่านของตัวเองทุกครั้ง
// จำกัดต่อ IP ต่อชั่วโมง โดยจดตัวนับ "ก่อน" ค้นรหัส: โควตาเขียนของ KV หมด = ปฏิเสธ ไม่ปล่อยให้เดาต่อได้

const TTL_SECONDS = 24 * 60 * 60;
const MAX_BYTES = 16 * 1024;
const LIMIT_PER_HOUR = 10;
const CODE_SPACE = 100_000_000; // เลข 8 หลัก
const JSON_TYPE = "application/json; charset=utf-8";

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": JSON_TYPE, "cache-control": "no-store" },
  });
}

// เลข 8 หลักแบบสุ่ม · ตัดค่าส่วนเกินทิ้งเพื่อให้ทุกเลขมีโอกาสเท่ากัน
function newCode() {
  const limit = Math.floor(0x100000000 / CODE_SPACE) * CODE_SPACE;
  const value = new Uint32Array(1);
  do {
    crypto.getRandomValues(value);
  } while (value[0] >= limit);
  return String(value[0] % CODE_SPACE).padStart(8, "0");
}

// IPv6 หนึ่งบ้านมักได้ทั้งช่วง /64 จึงนับรวมเป็นเครื่องเดียว
function clientId(request) {
  const ip = request.headers.get("cf-connecting-ip") ?? "unknown";
  return ip.includes(":") ? ip.split(":").slice(0, 4).join(":") : ip;
}

async function allowed(request, env, kind) {
  const hour = Math.floor(Date.now() / 3_600_000);
  const key = `rate:${kind}:${clientId(request)}:${hour}`;
  const used = Number.parseInt((await env.SKILLS.get(key)) ?? "0", 10);
  if (used >= LIMIT_PER_HOUR) {
    return false;
  }
  try {
    await env.SKILLS.put(key, String(used + 1), { expirationTtl: 2 * 60 * 60 });
  } catch {
    return false; // โควตาเขียนหมด หรือเขียนถี่เกิน 1 ครั้ง/วินาที
  }
  return true;
}

async function upload(request, env) {
  if (!(await allowed(request, env, "put"))) {
    return json(429, { error: "too_many_requests" });
  }
  if (Number(request.headers.get("content-length") ?? "0") > MAX_BYTES) {
    return json(413, { error: "too_large" });
  }
  const bytes = new Uint8Array(await request.arrayBuffer());
  if (bytes.length === 0 || bytes.length > MAX_BYTES) {
    return json(413, { error: "too_large" });
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return json(400, { error: "not_utf8" });
  }
  if (!text.trimStart().startsWith("---")) {
    return json(400, { error: "not_a_skill" });
  }
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const code = newCode();
    if ((await env.SKILLS.get(`skill:${code}`)) === null) {
      await env.SKILLS.put(`skill:${code}`, text, { expirationTtl: TTL_SECONDS });
      return json(201, { code, expires_in: TTL_SECONDS });
    }
  }
  return json(503, { error: "no_free_code" });
}

async function download(code, request, env) {
  if (!(await allowed(request, env, "get"))) {
    return json(429, { error: "too_many_requests" });
  }
  const text = await env.SKILLS.get(`skill:${code}`);
  if (text === null) {
    return json(404, { error: "not_found" });
  }
  return new Response(text, {
    status: 200,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === "/v1/skills" && request.method === "POST") {
      return upload(request, env);
    }
    const match = path.match(/^\/v1\/skills\/([0-9]{8})$/);
    if (match && request.method === "GET") {
      return download(match[1], request, env);
    }
    return json(404, { error: "not_found" });
  },
};
