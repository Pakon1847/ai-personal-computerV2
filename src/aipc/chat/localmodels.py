"""เลือก AI ในเครื่องได้ 3 ตัว (การ์ด 0076).

รายการโมเดลอยู่ที่ scripts/pi/session/llm-models.conf ที่เดียว · aipc-llm-start อ่านไฟล์เดียวกัน
ผู้ใช้เก็บแค่ "ชื่อ" ใน ~/.config/aipc/llm-model · สคริปต์เริ่ม AI เป็นคนตัดสินว่าใช้ได้ไหม (H7)
ไฟล์นี้ใช้แค่แสดงในหน้าตั้งค่า บันทึกชื่อ และสั่งเริ่ม AI ใหม่
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

LIST = Path(__file__).resolve().parents[3] / "scripts" / "pi" / "session" / "llm-models.conf"
MODELS_DIR = Path("/opt/aipc-models")

# คำบรรยายบนหน้าจอ · ตัวเลขจากผลวัดจริง (docs/benchmarks/2026-10-29-llm-compare · ตอน Pi ร้อน)
INFO = {
    "gemma4-e2b": ("Gemma 4 E2B", "ค่าเริ่มต้น · สมดุล", "แม่น 83/100 · 6.8 token/วิ · RAM 4.5 GB"),
    "qwen3.5-2b": ("Qwen3.5 2B", "เร็วและเบาที่สุด", "แม่น 77/100 · 7.4 token/วิ · RAM 2.7 GB"),
    "qwen3.5-4b": ("Qwen3.5 4B", "แม่นที่สุด แต่ช้า", "แม่น 88/100 · 3.3 token/วิ · RAM 5.6 GB"),
}


@dataclass(frozen=True)
class Model:
    key: str
    file: str
    template: str = ""


def load(path: Path = LIST) -> list[Model]:
    """อ่านรายการ · บรรทัด # และบรรทัดที่ไม่ครบ = ข้าม · อ่านไม่ได้ = รายการว่าง."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        parts = (line.split("|") + ["", ""])[:3]
        if parts[0] and parts[1]:
            out.append(Model(parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return out


def choice_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "aipc" / "llm-model"


def chosen(path: Path | None = None) -> str:
    """ชื่อที่ผู้ใช้เลือก · ไม่มีไฟล์ = "" (ใช้ค่าของเครื่อง)."""
    try:
        return (path or choice_path()).read_text(encoding="utf-8").strip()[:40]
    except OSError:
        return ""


def save(key: str, models: list[Model], path: Path | None = None) -> bool:
    """บันทึกชื่อ · ชื่อนอกรายการ = ไม่บันทึก (False)."""
    if key not in {m.key for m in models}:
        return False
    p = path or choice_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(key + "\n", encoding="utf-8")
    os.replace(tmp, p)  # atomic แบบเดียวกับ ui.json
    return True


def installed(model: Model, models_dir: Path = MODELS_DIR) -> bool:
    return (models_dir / model.file).is_file()


def machine_file(conf: Path = Path("/etc/aipc/llm.conf")) -> str:
    """ชื่อไฟล์โมเดลของเครื่อง (MODEL= ใน llm.conf) · อ่านไม่ได้ = ""."""
    try:
        for line in conf.read_text(encoding="utf-8").splitlines():
            if line.startswith("MODEL="):
                return Path(line.split("=", 1)[1].strip()).name
    except OSError:
        pass
    return ""


def effective(models: list[Model], choice: str, machine: str, models_dir: Path = MODELS_DIR) -> str:
    """ไฟล์โมเดลที่ aipc-llm-start จะใช้จริง (กติกาเดียวกับสคริปต์): ชื่อในรายการ + ไฟล์มีจริง ไม่งั้นค่าของเครื่อง."""
    for m in models:
        if m.key == choice and installed(m, models_dir):
            return m.file
    return machine


def restart() -> bool:
    """เริ่ม AI ของผู้ใช้คนนี้ใหม่ (systemd user service · ไม่ต้องใช้ sudo) · ไม่สำเร็จ = False."""
    try:
        r = subprocess.run(
            ["systemctl", "--user", "restart", "aipc-llm"], capture_output=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0
