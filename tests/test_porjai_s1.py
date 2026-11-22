"""เสียงยาวจากชุด Porjai สำหรับ S1 ของการ์ด 0082 · ไม่ต่อเน็ต (ตัวดึงและ ffmpeg เป็นของปลอม)."""

import array
import json
import tempfile
import unittest
import wave
from pathlib import Path

from aipc.spikes import porjai_s1


def tone(path: Path, seconds: float, value: int = 1000) -> None:
    n = int(porjai_s1.RATE * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(porjai_s1.RATE)
        w.writeframes(array.array("h", [value] * n).tobytes())


class PickTest(unittest.TestCase):
    def test_offsets_are_fixed_and_spread(self):
        a = porjai_s1.offsets(total=335674, groups=30, per_group=10)
        self.assertEqual(a, porjai_s1.offsets(total=335674, groups=30, per_group=10), "ชุดเดิมทุกครั้ง")
        self.assertEqual(len(a), 30)
        self.assertEqual(a[0], 0)
        self.assertLess(a[-1] + 10, 335674)
        self.assertGreater(a[1] - a[0], 10_000, "กระจายทั้งชุด (คนพูดหลายคน)")


class BuildTest(unittest.TestCase):
    def test_build_joins_audio_with_silence_and_writes_reference(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        out = Path(d.name)
        rows = {0: [("ก ข", "u0"), ("ค ง", "u1")], 500: [("จ ฉ", "u2")]}
        fetched = []

        def fetch(offset, length):
            fetched.append((offset, length))
            return [
                {"sentence": s, "utterance": u, "src": f"https://x/{u}.mp3"}
                for s, u in rows[offset]
            ]

        def convert(src, dest):  # ffmpeg ปลอม: เสียง 1 วิ ต่อไฟล์
            tone(dest, 1.0)

        info = porjai_s1.build([0, 500], per_group=2, out=out, fetch=fetch, convert=convert)
        self.assertEqual(fetched, [(0, 2), (500, 2)])
        with wave.open(str(out / "porjai-s1.wav"), "rb") as w:
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (16000, 1, 2))
            seconds = w.getnframes() / w.getframerate()
        self.assertAlmostEqual(seconds, 3 + 3 * porjai_s1.GAP_S, places=2)
        self.assertEqual((out / "porjai-s1.txt").read_text(encoding="utf-8").split("\n"),
                         ["ก ข", "ค ง", "จ ฉ"])  # fmt: skip
        meta = json.loads((out / "porjai-s1.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["utterances"], ["u0", "u1", "u2"])
        self.assertIn("CC BY-SA 4.0", meta["license"])
        self.assertEqual(info["count"], 3)

    def test_bad_clip_is_skipped_not_fatal(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        out = Path(d.name)

        def fetch(offset, length):
            return [{"sentence": "ก", "utterance": "ok", "src": "a"},
                    {"sentence": "ข", "utterance": "bad", "src": "b"}]  # fmt: skip

        def convert(src, dest):
            if src == "b":
                raise RuntimeError("ffmpeg ล้ม")
            tone(dest, 1.0)

        info = porjai_s1.build([0], per_group=2, out=out, fetch=fetch, convert=convert)
        self.assertEqual(info["count"], 1)
        self.assertEqual(info["skipped"], ["bad"])
        self.assertEqual((out / "porjai-s1.txt").read_text(encoding="utf-8"), "ก")


if __name__ == "__main__":
    unittest.main()
