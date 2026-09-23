"""ไฟล์ที่ไม่ใช่ .py ต้องถูกติดตั้งไปกับแอปด้วย.

บั๊กที่เจอบน Pi 4 (2026-09-24): ติดตั้งแบบปกติไปที่ /opt/aipc-v2 แล้วไฟล์สกิล builtin/*.json หายหมด
เพราะไม่ได้อยู่ใน package-data · ตอนพัฒนา (pip install -e) ไม่เห็นบั๊กนี้ เพราะอ่านจากโฟลเดอร์โค้ดตรง ๆ
"""

import fnmatch
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "aipc"


class PackageDataTest(unittest.TestCase):
    def test_every_data_file_is_packaged(self):
        conf = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        patterns = conf["tool"]["setuptools"]["package-data"]["aipc"]
        missing = []
        for f in PKG.rglob("*"):
            if not f.is_file() or f.suffix in (".py", ".pyc") or "__pycache__" in f.parts:
                continue
            rel = f.relative_to(PKG).as_posix()
            if not any(fnmatch.fnmatch(rel, p) for p in patterns):
                missing.append(rel)
        self.assertEqual(missing, [], "เพิ่มใน [tool.setuptools.package-data] ของ pyproject.toml")


if __name__ == "__main__":
    unittest.main()
