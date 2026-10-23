"""เลือก Wi-Fi จากแถบบน (การ์ด 0063) · คุยกับ NetworkManager ผ่าน `nmcli`.

สิทธิ์ตัดสินโดย NetworkManager + polkit (H7): ผู้ใช้ที่นั่งหน้าจอค้นหา/ต่อได้ ·
แก้เครือข่ายของทั้งเครื่องต้องอยู่กลุ่ม netdev (scripts/pi/install-wifi-access.sh · ทาง ก)

รหัส Wi-Fi (H1): **ไม่ใส่ใน argv** (คนอื่นในเครื่องเห็นได้ใน ps) · เขียนลงไฟล์ชั่วคราวสิทธิ์ 600
แล้วให้ `nmcli connection up … passwd-file <ไฟล์>` อ่าน · ลบไฟล์ทันทีหลังคำสั่งจบ · ไม่ log ไม่เก็บในแอป
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from aipc.i18n import tr

WAIT_S = 30  # รอ NetworkManager ต่อให้เสร็จ (รหัสผิด = NetworkManager ตอบภายในเวลานี้)


def _split(line: str) -> list[str]:
    """แยกบรรทัดแบบ `nmcli -t` · ':' ในชื่อเครือข่ายถูกเขียนเป็น '\\:'."""
    out, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur, esc = cur + ch, False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _nmcli(args: list[str], run=subprocess.run, timeout: float = 15) -> tuple[int, str]:
    try:
        r = run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return 127, tr("เครื่องนี้ไม่มี NetworkManager (nmcli)")
    except subprocess.TimeoutExpired:
        return 124, tr("NetworkManager ไม่ตอบ")
    return r.returncode, (r.stdout if r.returncode == 0 else (r.stderr or r.stdout)).strip()


def known(run=subprocess.run) -> dict[str, str]:
    """Wi-Fi ที่เครื่องจำไว้: ชื่อเครือข่าย (SSID) → ชื่อโปรไฟล์.

    ชื่อโปรไฟล์อาจไม่ใช่ SSID (เช่น "preconfigured" ที่ Raspberry Pi Imager สร้าง)
    """
    code, text = _nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"], run)
    if code != 0:
        return {}
    out = {}
    for line in text.splitlines():
        parts = _split(line)
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            show = ["-g", "802-11-wireless.ssid", "connection", "show", "id", parts[0]]
            c, ssid = _nmcli(show, run)
            if c == 0 and ssid.strip():
                out[ssid.strip()] = parts[0]
    return out


def scan(rescan: bool = False, run=subprocess.run) -> tuple[list[dict], str]:
    """รายชื่อ Wi-Fi ที่เห็น (แรงสุดก่อน · ชื่อซ้ำเก็บอันแรงสุด · ไม่มีชื่อ = ข้าม) และข้อความเมื่อทำไม่ได้."""
    args = ["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
            "--rescan", "yes" if rescan else "auto"]  # fmt: skip
    code, text = _nmcli(args, run, timeout=20)
    if code != 0:
        return [], tr("ค้นหา Wi-Fi ไม่ได้") + (f" · {text}" if text else "")
    saved = known(run)
    seen: dict[str, dict] = {}
    for line in text.splitlines():
        parts = _split(line)
        if len(parts) < 4 or not parts[1]:
            continue
        ssid = parts[1]
        try:
            signal = int(parts[2])
        except ValueError:
            signal = 0
        item = {"ssid": ssid, "signal": signal, "bars": min(4, max(1, (signal + 24) // 25)),
                "secure": parts[3].strip() not in ("", "--"), "active": parts[0].strip() == "*",
                "known": ssid in saved}  # fmt: skip
        old = seen.get(ssid)
        if old is None or item["active"] or (signal > old["signal"] and not old["active"]):
            seen[ssid] = item
    nets = sorted(seen.values(), key=lambda n: (not n["active"], -n["signal"], n["ssid"]))
    return nets, ""


def _why(text: str) -> str:
    low = text.lower()
    if "secrets were required" in low or "no secrets" in low or "802-1x" in low or "psk" in low:
        return tr("รหัสไม่ถูก")
    if "not authorized" in low or "insufficient privileges" in low:
        return tr("บัญชีนี้ไม่มีสิทธิ์เปลี่ยน Wi-Fi ของเครื่อง")
    if "no network with ssid" in low or "not found" in low:
        return tr("ไม่เจอเครือข่ายนี้แล้ว (สัญญาณอาจหาย)")
    return tr("ต่อไม่ได้") + (f" · {text.splitlines()[-1]}" if text else "")


def connect(
    ssid: str, password: str = "", run=subprocess.run, tmpdir: str | None = None
) -> tuple[bool, str]:
    """ต่อ Wi-Fi · เคยต่อแล้ว = ใช้โปรไฟล์เดิม (ไม่ต้องใส่รหัส) · ใหม่ = สร้างโปรไฟล์แล้วส่งรหัสทางไฟล์ 600.

    ต่อเครือข่ายใหม่ไม่สำเร็จ = ลบโปรไฟล์ที่เพิ่งสร้าง (ไม่จำรหัสผิดไว้) · เครื่องกลับไปต่อเครือข่ายเดิมเอง
    """
    if password and (not 8 <= len(password) <= 63 or "\n" in password):
        return False, tr("รหัส Wi-Fi ต้องยาว 8–63 ตัวอักษร")  # กติกาของ WPA ส่วนบุคคล
    saved = known(run)
    if ssid in saved and not password:
        up = ["--wait", str(WAIT_S), "connection", "up", "id", saved[ssid]]
        code, text = _nmcli(up, run, WAIT_S + 5)
        return (True, tr("ต่อ {ssid} แล้ว", ssid=ssid)) if code == 0 else (False, _why(text))

    name = ssid if ssid not in saved else saved[ssid]
    created = ssid not in saved
    if created:
        args = ["connection", "add", "type", "wifi", "con-name", name, "ssid", ssid]
        if password:
            args += ["wifi-sec.key-mgmt", "wpa-psk"]
        code, text = _nmcli(args, run)
        if code != 0:
            return False, _why(text)
    up = ["--wait", str(WAIT_S), "connection", "up", "id", name]
    path = None
    try:
        if password:
            fd, path = tempfile.mkstemp(prefix="aipc-wifi-", dir=tmpdir)  # สร้างด้วยสิทธิ์ 600 เสมอ
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"802-11-wireless-security.psk:{password}\n")
            up += ["passwd-file", path]
        code, text = _nmcli(up, run, WAIT_S + 5)
    finally:
        if path is not None:
            os.unlink(path)
    if code == 0:
        return True, tr("ต่อ {ssid} แล้ว", ssid=ssid)
    if created:
        _nmcli(["connection", "delete", "id", name], run)
    return False, _why(text)


def forget(ssid: str, run=subprocess.run) -> tuple[bool, str]:
    """ลืมเครือข่าย = ลบโปรไฟล์ทุกอันของชื่อนี้ (รหัสที่จำไว้หายด้วย)."""
    saved = known(run)
    if ssid not in saved:
        return False, tr("เครื่องไม่ได้จำ {ssid} ไว้", ssid=ssid)
    code, text = _nmcli(["connection", "delete", "id", saved[ssid]], run)
    return (True, tr("ลืม {ssid} แล้ว", ssid=ssid)) if code == 0 else (False, _why(text))


class WifiController(QObject):
    """ตัวเชื่อม QML ของหน้าต่าง Wi-Fi · งาน nmcli ทำในเธรดแยก (หน้าจอไม่ค้างระหว่างค้นหา/ต่อ)."""

    changed = Signal()
    _done = Signal(str, "QVariant")

    def __init__(self, active: bool = True, run=subprocess.run):
        super().__init__()
        self._active = active
        self._run = run
        self._nets: list[dict] = []
        self._busy = ""  # "" | "scan" | ชื่อเครือข่ายที่กำลังต่อ/ลืม
        self._msg, self._ok = "", True
        self._done.connect(self._on_done)
        if active:  # ป้ายบนแถบรู้ชื่อเครือข่ายที่ต่ออยู่ตั้งแต่เปิด (ไม่สั่งค้นหาใหม่ · ใช้รายการที่ NetworkManager มีอยู่)
            QTimer.singleShot(3000, lambda: self.scan(False))

    def _start(self, what: str, work) -> bool:
        if not self._active or self._busy:
            return False
        self._busy = what
        self.changed.emit()

        def go():
            try:
                r = work()
            except Exception as e:  # noqa: BLE001 · เธรดเบื้องหลังห้ามล้มเงียบ (H2)
                r = ("error", f"{e}")
            self._done.emit(what, r)

        threading.Thread(target=go, daemon=True).start()
        return True

    @Slot(str, "QVariant")
    def _on_done(self, what: str, result) -> None:
        self._busy = ""
        kind, value = result
        if kind == "scan":
            self._nets, err = value
            if err:  # ค้นหาได้ = คงข้อความของการต่อ/ลืมครั้งล่าสุดไว้ให้อ่าน
                self._ok, self._msg = False, err
        elif kind == "error":
            self._ok, self._msg = False, tr("ทำไม่สำเร็จ") + f" · {value}"
        else:
            self._ok, self._msg = value
        self.changed.emit()
        if kind in ("connect", "forget"):
            self.scan(False)  # รายการใหม่: อันที่ต่ออยู่ / อันที่ลืมแล้ว

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._active

    @Property("QVariantList", notify=changed)
    def networks(self) -> list:
        return self._nets

    @Property(str, notify=changed)
    def current(self) -> str:
        return next((n["ssid"] for n in self._nets if n["active"]), "")

    @Property(str, notify=changed)
    def busy(self) -> str:
        return self._busy

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._msg

    @Property(bool, notify=changed)
    def messageOk(self) -> bool:  # noqa: N802
        return self._ok

    @Slot(bool, result=bool)
    def scan(self, rescan: bool = False) -> bool:
        return self._start("scan", lambda: ("scan", scan(rescan, self._run)))

    @Slot()
    def clearMessage(self) -> None:  # noqa: N802
        self._msg, self._ok = "", True
        self.changed.emit()

    @Slot(str, str, result=bool)
    def join(self, ssid: str, password: str = "") -> bool:  # ไม่ใช้ชื่อ connect (ชนกับของ QObject)
        return self._start(ssid, lambda: ("connect", connect(ssid, password, self._run)))

    @Slot(str, result=bool)
    def forget(self, ssid: str) -> bool:
        return self._start(ssid, lambda: ("forget", forget(ssid, self._run)))
