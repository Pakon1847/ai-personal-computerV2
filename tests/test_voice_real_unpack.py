"""การ์ด 0026: แกะไฟล์ส่งออกจากหน้าอัดเสียง + ตัวเทียบผลแบบ has (เสียงในเทสต์ = ความเงียบที่สร้างเอง)."""

import base64
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path

from aipc.spikes.voice_models_analyze import matches, only_query_differs
from aipc.spikes.voice_real_unpack import unpack


def wav_b64(rate=16000, secs=0.1) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * secs))
    return base64.b64encode(buf.getvalue()).decode()


PROMPTS = {
    "items": [
        {"id": "d01", "set": "D", "mode": "say", "prompt": "ค้นหาราคาทอง",
         "expect": [{"kind": "search", "has": ["ราคาทอง"]}]},
        {"id": "d02", "set": "D", "mode": "say", "prompt": "ย้อนกลับ", "expect": [{"kind": "back"}]},
        {"id": "h01", "set": "H", "mode": "say", "prompt": "ปิดแท็บ", "expect": [{"kind": "close"}]},
    ]
}  # fmt: skip


class UnpackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "p.json").write_text(json.dumps(PROMPTS, ensure_ascii=False), encoding="utf-8")

    def export(self, name, items):
        p = self.tmp / name
        p.write_text(json.dumps({"items": items}), encoding="utf-8")
        return p

    def test_latest_take_wins_and_expect_from_prompts(self):
        a = self.export("a.json", [{"id": "d02", "wav": wav_b64(secs=0.1), "expect": "ปลอม"}])
        b = self.export(
            "b.json", [{"id": "d02", "wav": wav_b64(secs=0.2)}, {"id": "d01", "wav": wav_b64()}]
        )
        out = self.tmp / "audio"
        self.assertEqual(unpack([a, b], out, ["D"], self.tmp / "p.json"), {"D": 2})
        items = json.loads((out / "real_D.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([i["id"] for i in items], ["d01", "d02"])  # เรียงตามเลข → 00 01
        self.assertEqual(items[1]["expect"], [{"kind": "back"}])  # ไม่เชื่อค่าในไฟล์ส่งออก
        with wave.open(str(out / "real_D/01-16k.wav")) as w:
            self.assertAlmostEqual(w.getnframes() / w.getframerate(), 0.2, places=2)

    def test_held_out_not_unpacked_unless_asked(self):
        a = self.export("a.json", [{"id": "h01", "wav": wav_b64()}])
        out = self.tmp / "audio"
        self.assertEqual(unpack([a], out, ["D"], self.tmp / "p.json"), {"D": 0})
        self.assertFalse((out / "real_H").exists())

    def test_rejects_wrong_rate(self):
        a = self.export("a.json", [{"id": "d01", "wav": wav_b64(rate=48000)}])
        with self.assertRaises(ValueError):
            unpack([a], self.tmp / "audio", ["D"], self.tmp / "p.json")


class MatchesTest(unittest.TestCase):
    def test_has_ignores_spaces_and_extra_words(self):
        exp = [{"kind": "search", "has": ["ราคาทอง"]}]
        self.assertTrue(matches([{"kind": "search", "query": "ราคา ทอง วันนี้"}], exp))
        self.assertFalse(matches([{"kind": "search", "query": "ราคาน้ำมัน"}], exp))
        self.assertTrue(only_query_differs([{"kind": "search", "query": "ราคาน้ำมัน"}], exp))

    def test_wrong_link_is_not_query_diff(self):
        got, exp = [{"kind": "open", "n": 3}], [{"kind": "open", "n": 4}]
        self.assertFalse(matches(got, exp))
        self.assertFalse(only_query_differs(got, exp))

    def test_exact_query_for_synthetic_sets(self):
        exp = [{"kind": "search", "query": "แมว"}]
        self.assertTrue(matches([{"kind": "search", "query": "แมว"}], exp))
        self.assertFalse(matches([{"kind": "search", "query": "แมวน้ำ"}], exp))


if __name__ == "__main__":
    unittest.main()
