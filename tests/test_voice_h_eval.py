"""ตัวนับผลชุด H (การ์ด 0026 หัวข้อ 8 · aipc.spikes.voice_h_eval) · ไม่ต้องมีเสียง/โมเดล."""

import unittest

from aipc.spikes.voice_h_eval import criteria, h_items, judge, summarize


class VoiceHEvalTest(unittest.TestCase):
    def test_h_set_is_120_with_locked_task_sentences(self):
        items = h_items()
        self.assertEqual(len(items), 120)
        self.assertEqual(sum(bool(i["expect"]) for i in items), 80)
        self.assertTrue(all(i["text"] and not i["text"].startswith("ให้") for i in items))

    def test_judge(self):
        search = [{"kind": "search", "has": ["ไอโฟน"]}]
        self.assertEqual(judge([{"kind": "search", "query": "ราคาไอโฟน"}], search), "ok")
        self.assertEqual(judge([{"kind": "search", "query": "ราคาไอโพน"}], search), "wrong")
        self.assertEqual(judge([{"kind": "open", "n": 3}], [{"kind": "open", "n": 4}]), "wrong")
        self.assertEqual(judge([], [{"kind": "back"}]), "miss")
        self.assertEqual(judge([{"kind": "back"}], []), "neg_do")
        self.assertEqual(judge([], []), "neg_ok")

    def test_criteria(self):
        def rows(verdicts, secs=0.2):
            return [
                {
                    "expect": [] if v.startswith("neg") else [{"kind": "back"}],
                    "x": {"verdict": v, "got": [], "seconds": secs},
                }
                for v in verdicts
            ]

        z = summarize(rows(["ok"] * 9 + ["miss"] + ["neg_ok"] * 4), "x")
        w = summarize(rows(["ok"] * 7 + ["wrong"] * 3 + ["neg_do"] + ["neg_ok"] * 3, 1.0), "x")
        self.assertEqual((z["ok_pct"], w["wrong"], w["neg_do"]), (90.0, 3, 1))
        self.assertTrue(all(criteria(z, w).values()))
        self.assertFalse(criteria(w, z)["1_wrong_le_2_and_neg_le_1"])


if __name__ == "__main__":
    unittest.main()
