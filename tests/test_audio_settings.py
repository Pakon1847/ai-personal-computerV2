"""ระดับเสียงในหน้าตั้งค่า (2026-10-27) · ไม่แตะเสียงจริง (runner/reader ปลอม)."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from aipc.ui.backend import AudioController
except ImportError:  # pragma: no cover
    AudioController = None

SINK = "@DEFAULT_AUDIO_SINK@"


@unittest.skipIf(AudioController is None, "ไม่มี PySide6")
class AudioControllerTest(unittest.TestCase):
    def make(self, volume="Volume: 0.60 [MUTED]\n", code=0):
        self.calls = []
        outputs = {
            "get-volume": volume,
            "inspect": '  * node.description = "Leviosa Max Analog Stereo"\n',
        }
        return AudioController(
            True,
            runner=lambda a: self.calls.append(a) or code,
            reader=lambda a: outputs[a[1]],
        )

    def test_shows_level_mute_and_where_sound_goes(self):
        """พบ 2026-10-27: หูฟังถูกปิดเสียงค้าง หาไม่เจอ → หน้าตั้งค่าต้องบอกทั้งสถานะและช่องที่เสียงออก."""
        a = self.make()
        a.refresh()
        self.assertEqual((a.percent, a.muted), (60, True))
        self.assertEqual(a.device, "Leviosa Max Analog Stereo")

    def test_buttons_use_the_same_commands_as_voice(self):
        a = self.make()
        a.step(1)
        a.step(-1)
        a.setMuted(False)
        self.assertEqual(
            self.calls,
            [
                ["wpctl", "set-volume", "-l", "1.0", SINK, "10%+"],
                ["wpctl", "set-volume", "-l", "1.0", SINK, "10%-"],
                ["wpctl", "set-mute", SINK, "0"],
            ],
        )

    def test_failure_is_shown(self):
        a = self.make(code=1)
        a.step(1)
        self.assertIn("ไม่สำเร็จ", a.error)
        b = self.make(volume=None)
        b.refresh()
        self.assertIn("อ่านระดับเสียงไม่ได้", b.error)

    def test_dev_window_and_login_screen_never_touch_sound(self):
        calls = []
        a = AudioController(False, runner=lambda x: calls.append(x) or 0, reader=lambda x: None)
        a.refresh()
        a.step(1)
        a.setMuted(True)
        self.assertEqual(calls, [])
        self.assertFalse(a.available)


if __name__ == "__main__":
    unittest.main()
