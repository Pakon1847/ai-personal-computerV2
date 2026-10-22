"""visiond: บริการใบหน้าของระบบ (การ์ด 0015 หัวข้อ 12) · รันเป็นผู้ใช้ `_aipcvision` (กลุ่ม video) ผ่าน systemd.

    python -m aipc.vision.daemon            (systemd เรียก · ดู scripts/pi/install-visiond.sh)

socket 2 ตัว · ข้อความ JSON บรรทัดละ 1 ก้อน:
- `/run/aipc-vision/visiond.sock` (0666 · ใครก็ต่อได้ แต่ตรวจ uid ของผู้ต่อด้วย SO_PEERCRED ทุกคำขอ):
    identify {timeout_s}                      หน้า Login (`_greetd`) เท่านั้น · ตอบสถานะทีละบรรทัด
    enroll {username, password, consent_at}   หน้า Login (ตอนสมัคร) หรือเจ้าของบัญชีเอง (หน้าตั้งค่า)
    remove {username, password}               เหมือน enroll
    enabled {username}                        เจ้าของบัญชีหรือหน้า Login · บอกว่าเปิดเข้าด้วยใบหน้าไหม
    watch {username, seconds}                 เจ้าของบัญชีเท่านั้น (ไม่ใช่หน้า Login) · ดูว่าเจ้าของยังนั่งอยู่
    unlock {username}                         เจ้าของบัญชีเท่านั้น · ปลดจอล็อกด้วยใบหน้า (การ์ด 0055)
                                              (การ์ด 0051 ก) ทุก 2 วิ: กี่หน้า/ใช่เจ้าของไหม · ไม่ส่งภาพ
- `/run/aipc-vision/visiond-root.sock` (0600 · เฉพาะ uid 0 = `aipc-face-pass` ที่ PAM เรียก):
    consume {username}    ใช้ตั๋ว → {"ok": true} = เข้าระบบได้เลย
    login-ok {}           เข้าระบบสำเร็จ (ด้วยวิธีใดก็ได้) → ปลดล็อกการสแกน

กล้องเปิดเฉพาะระหว่าง identify/enroll และทำได้ทีละงาน (งานที่สอง = busy) · รหัสผ่านไม่ลง log ไม่เก็บ
"""

from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from aipc.vision import service

PUBLIC = Path("/run/aipc-vision/visiond.sock")
ROOT = Path("/run/aipc-vision/visiond-root.sock")
GREETER = "_greetd"
REQUEST_MAX = 4096
HELPER = ["sudo", "-n", "/usr/local/sbin/aipc-accounts"]
ENROLL_SECONDS = 40.0  # เท่าการลงทะเบียนในหน้าตั้งค่า (การ์ด 0010)
IDENTIFY_MAX_S = 15.0
WATCH_MAX_S = 60.0  # ตัวตรวจขอใหม่ทุก ≤ 60 วิ (กล้องไม่ค้างถ้าตัวตรวจตาย)
UNLOCK_SECONDS = 5.0  # ปลดจอล็อกด้วยใบหน้า (การ์ด 0055) · สั้นกว่าหน้า Login (คนนั่งหน้าจออยู่แล้ว)


def peer_uid(conn: socket.socket) -> int:
    creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", creds)[1]


def uid_of(name: str) -> int | None:
    import pwd  # Linux เท่านั้น

    try:
        return pwd.getpwnam(name).pw_uid
    except KeyError:
        return None


def check_password_via_helper(user: str, password: str) -> bool:
    """ให้ตัวช่วย root ตรวจด้วย PAM (visiond ไม่ใช่ root จึงตรวจรหัสของคนอื่นเองไม่ได้)."""
    req = json.dumps({"op": "check-password", "username": user, "password": password})
    try:
        r = subprocess.run(HELPER, input=req.encode(), capture_output=True, timeout=30, check=False)
        return json.loads(r.stdout or b"{}").get("ok") is True
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def _tap(frames, last: dict):
    """จำเฟรมล่าสุดไว้ทำภาพย่อ (เฟรมเดียวกับที่วิเคราะห์ ไม่อ่านกล้องซ้ำ)."""
    for f in frames:
        last["frame"] = f
        yield f


def _with_preview(msg: dict, r, frame, preview) -> dict:
    import base64

    if preview is not None and frame is not None:
        jpeg, box = preview(frame, getattr(r, "box", None))
        msg["jpeg"], msg["box"] = base64.b64encode(jpeg).decode("ascii"), box
    return msg


def scan_status(r, counts: dict, frame, preview) -> dict:
    """สถานะระหว่างสแกนที่หน้า Login: คำแนะนำ + ภาพย่อแบบกระจกให้คนหน้ากล้องเห็นตัวเอง (Pakon ขอ 2026-09-30).

    ภาพไปที่หน้า Login เท่านั้น (ผู้ขอ identify ต้องเป็น _greetd) · ไม่เขียนดิสก์ ไม่ลง log
    """
    msg = {"state": "scanning", "hint": r.advice, "good": counts.get("good", 0), "box": []}
    return _with_preview(msg, r, frame, preview)


def enroll_status(r, counts: dict, frame, preview) -> dict:
    """สถานะระหว่างลงทะเบียน 1 เฟรม: คำแนะนำ ท่าที่ได้ ท่าถัดไป หันถึงแค่ไหน + ภาพย่อแบบกระจก (base64 JPEG).

    ภาพส่งเฉพาะผู้ที่ขอลงทะเบียน (หน้าสมัคร/เจ้าของบัญชีที่อยู่หน้ากล้อง) · ไม่เขียนดิสก์ ไม่ลง log
    """
    from aipc.vision import guide

    target = guide.next_pose(counts)
    msg = {"state": "enrolling", "hint": guide.advice(r, counts), "poses": dict(counts),
           "pose": target, "reach": 0.0, "box": []}  # fmt: skip
    _with_preview(msg, r, frame, preview)
    q = getattr(r, "quality", None)
    if q is not None and msg["box"]:
        msg["reach"] = guide.pose_reach(target, q.yaw, q.pitch)
    return msg


class Handler:
    """ตัดสินคำขอ 1 ก้อนจาก uid ของผู้ต่อ · ไม่แตะ socket (เทสต์ได้ทุกระบบ).

    frames(seconds) → iterator ของภาพ (เปิด/ปิดกล้องเอง) · send(dict) = ส่งสถานะระหว่างทาง
    """

    def __init__(
        self,
        face: service.FaceLogin,
        frames: Callable,
        greeter_uid: int | None,
        uid_of: Callable[[str], int | None] = uid_of,
        preview: Callable | None = None,
    ):
        self.face, self.frames, self.greeter_uid, self._uid_of = face, frames, greeter_uid, uid_of
        # preview(frame, box) → (jpeg, กรอบหน้า) · ให้ผู้ใช้เห็นหน้าตัวเองตอนลงทะเบียน (Pakon 2026-09-30)
        self.preview = preview
        self._camera = threading.Lock()

    def _may_manage(self, uid: int, user: str) -> bool:
        return uid == self.greeter_uid or (uid != 0 and uid == self._uid_of(user))

    def _with_camera(self, work):
        if not self._camera.acquire(blocking=False):
            return {"ok": False, "state": "busy", "message": "กล้องกำลังใช้อยู่ · ลองใหม่อีกครั้ง"}
        try:
            return work()
        except RuntimeError as e:  # เปิดกล้องไม่ได้ / ถอดกล้องกลางคัน
            return {
                "ok": False,
                "state": "no-camera",
                "message": f"ใช้กล้องไม่ได้ · ใช้รหัสผ่านได้เลย ({e})",
            }
        finally:
            self._camera.release()

    def public(self, req: dict, uid: int, send: Callable[[dict], None]) -> dict:
        op, user = req.get("op"), req.get("username")
        if op == "identify":
            if uid != self.greeter_uid:
                return {"ok": False, "state": "error", "message": "ใช้ได้ที่หน้า Login เท่านั้น"}
            secs = min(float(req.get("timeout_s", 8)), IDENTIFY_MAX_S)

            last: dict = {}

            def progress(r, counts):
                send(scan_status(r, counts, last.get("frame"), self.preview))

            return self._with_camera(
                lambda: vars(self.face.identify(_tap(self.frames(secs), last), progress))
            )
        if op in ("watch", "unlock"):
            # เจ้าของบัญชีเท่านั้น · หน้า Login/root ขอไม่ได้ (ไม่มีเหตุให้ดูว่าใครนั่งอยู่หน้าเครื่อง ·
            # ปลดจอล็อกของคนอื่นไม่ได้)
            owner = isinstance(user, str) and uid not in (0, self.greeter_uid)
            if not owner or uid != self._uid_of(user):
                return {"ok": False, "state": "error", "message": "ทำได้เฉพาะบัญชีของตัวเอง"}
            if op == "unlock":
                return self._with_camera(
                    lambda: vars(self.face.unlock(user, self.frames(UNLOCK_SECONDS)))
                )
            try:
                secs = max(1.0, min(float(req.get("seconds", WATCH_MAX_S)), WATCH_MAX_S))
            except (TypeError, ValueError):
                secs = WATCH_MAX_S
            return self._with_camera(lambda: vars(self.face.watch(user, self.frames(secs), send)))
        if not isinstance(user, str) or not self._may_manage(uid, user):
            return {"ok": False, "state": "error", "message": "ทำได้เฉพาะบัญชีของตัวเอง"}
        if op == "enabled":
            try:
                on = self.face.gallery.path(user).exists()
            except ValueError:
                on = False
            return {"ok": True, "state": "enabled" if on else "disabled"}
        password = req.get("password")
        if not isinstance(password, str):
            return {"ok": False, "state": "error", "message": "คำขอไม่ครบ"}
        if op == "remove":
            return vars(self.face.remove(user, password))
        if op == "enroll":
            consent = req.get("consent_at") if isinstance(req.get("consent_at"), str) else ""
            last: dict = {}

            def progress(r, counts):
                send(enroll_status(r, counts, last.get("frame"), self.preview))

            return self._with_camera(
                lambda: vars(
                    self.face.enroll(
                        user, password, _tap(self.frames(ENROLL_SECONDS), last), consent, progress
                    )
                )
            )
        return {"ok": False, "state": "error", "message": "ไม่รู้จักคำขอนี้"}

    def root(self, req: dict, uid: int) -> dict:
        if uid != 0:
            return {"ok": False}
        if req.get("op") == "consume" and isinstance(req.get("username"), str):
            return {"ok": self.face.consume(req["username"])}
        if req.get("op") == "login-ok":
            self.face.password_login()
            return {"ok": True}
        return {"ok": False}


def _read_request(conn: socket.socket) -> dict | None:
    data = b""
    while b"\n" not in data and len(data) <= REQUEST_MAX:
        chunk = conn.recv(1024)
        if not chunk:
            break
        data += chunk
    try:
        req = json.loads(data.split(b"\n", 1)[0])
    except ValueError:
        return None
    return req if isinstance(req, dict) else None


def _send(conn: socket.socket, obj: dict) -> None:
    conn.sendall(json.dumps(obj, ensure_ascii=False).encode() + b"\n")


def serve(path: Path, mode: int, on_request: Callable, stop: threading.Event) -> threading.Thread:
    """socket 1 ตัว · 1 thread ต่อการเชื่อมต่อ · คำขอเดียวต่อการเชื่อมต่อ."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    os.chmod(path, mode)
    srv.listen(8)
    srv.settimeout(1.0)

    def one(conn):
        with conn:
            conn.settimeout(120)
            try:
                req = _read_request(conn)
                if req is None:
                    _send(conn, {"ok": False, "state": "error", "message": "คำขออ่านไม่ได้"})
                    return
                _send(conn, on_request(req, peer_uid(conn), lambda o: _send(conn, o)))
            except OSError:
                pass  # ผู้ต่อปิดไปก่อน

    def loop():
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except TimeoutError:
                continue
            threading.Thread(target=one, args=(conn,), daemon=True).start()
        srv.close()

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t


def camera_frames(seconds: float):
    """เปิดกล้องตัวแรก อ่านภาพ seconds วิ แล้วปิด (โค้ดเดิมของ aipc.vision.camera)."""
    from aipc.vision import camera

    cap = camera.open_camera()
    try:
        yield from camera.frames(cap, seconds)
    finally:
        cap.release()


def main() -> int:
    import syslog

    from aipc.vision import camera, config

    syslog.openlog("aipc-visiond")

    def log(text: str) -> None:
        syslog.syslog(syslog.LOG_AUTH | syslog.LOG_NOTICE, text)

    cfg = config.load(Path("/etc/aipc/face.json"))
    face = service.FaceLogin(
        camera.build_scanner(cfg), service.Gallery(), check_password_via_helper, log=log
    )
    from aipc.vision import guide

    h = Handler(face, camera_frames, uid_of(GREETER), preview=guide.preview_jpeg)
    stop = threading.Event()
    serve(PUBLIC, 0o666, h.public, stop)
    serve(ROOT, 0o600, lambda req, uid, _send: h.root(req, uid), stop)
    log("visiond พร้อม")
    try:
        stop.wait()
    except KeyboardInterrupt:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
