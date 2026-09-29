"""หาแอปที่ติดตั้งจริงจากไฟล์ .desktop (apps.py · งานข้อ ⑥) · ใช้โฟลเดอร์ชั่วคราว ไม่อ่านแอปจริงของเครื่อง."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from aipc.skills import actions, apps, command, mdskill

WRITER = """[Desktop Entry]
Type=Application
Name=LibreOffice Writer
Name[th]=ไรเตอร์
Exec=libreoffice --writer %U
Keywords=Text;Document;
"""


def desktop(folder: Path, name: str, text: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


class RegistryTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.system = Path(d.name) / "system"
        self.user = Path(d.name) / "user"
        self.reg = apps.Registry([self.system, self.user])
        old = apps.REGISTRY
        apps.REGISTRY = self.reg
        self.addCleanup(setattr, apps, "REGISTRY", old)

    def test_reads_names_and_skips_hidden_or_non_apps(self):
        desktop(self.system, "libreoffice-writer.desktop", WRITER)
        desktop(
            self.system,
            "hidden.desktop",
            "[Desktop Entry]\nType=Application\nName=Hidden\nExec=x\nNoDisplay=true\n",
        )
        desktop(
            self.system, "link.desktop", "[Desktop Entry]\nType=Link\nName=Site\nURL=https://x\n"
        )
        found = self.reg.apps()
        self.assertEqual(list(found), ["libreoffice-writer.desktop"])
        app = found["libreoffice-writer.desktop"]
        self.assertEqual(app.name, "ไรเตอร์")
        self.assertIn("libreofficewriter", app.aliases)
        self.assertIn("ไรเตอร์", app.aliases)

    def test_new_install_is_seen_without_restart(self):
        self.system.mkdir(parents=True)
        self.assertEqual(self.reg.apps(), {})
        time.sleep(0.02)  # ให้ mtime ของโฟลเดอร์ขยับแน่ ๆ
        desktop(self.system, "libreoffice-writer.desktop", WRITER)
        os.utime(self.system, None)
        self.assertIn("libreoffice-writer.desktop", self.reg.apps())

    def test_user_folder_overrides_system(self):
        desktop(self.system, "libreoffice-writer.desktop", WRITER)
        desktop(
            self.user,
            "libreoffice-writer.desktop",
            WRITER.replace("Name[th]=ไรเตอร์", "Name[th]=เขียนงาน"),
        )
        self.assertEqual(self.reg.apps()["libreoffice-writer.desktop"].name, "เขียนงาน")

    def test_command_opens_installed_app_with_gtk_launch_only(self):
        desktop(self.system, "libreoffice-writer.desktop", WRITER)
        cmd = command.parse("เปิดไรเตอร์")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.plan.params, {"app": "desk:libreoffice-writer.desktop"})
        self.assertEqual(cmd.plan.summary, "เปิดไรเตอร์")
        self.assertEqual(
            actions.command_for(cmd.plan), ["gtk-launch", "libreoffice-writer.desktop"]
        )
        self.assertEqual(command.parse("เปิด libreoffice writer").plan.params["app"],
                         "desk:libreoffice-writer.desktop")  # fmt: skip

    def test_static_thai_aliases_still_win(self):
        desktop(
            self.system,
            "chromium.desktop",
            "[Desktop Entry]\nType=Application\nName=Chromium\nExec=chromium\n",
        )
        self.assertEqual(command.parse("เปิดโครเมียม").plan.params, {"app": "browser"})

    def test_uninstalled_app_is_reported_not_crashed(self):
        desktop(self.system, "libreoffice-writer.desktop", WRITER)
        plan = command.parse("เปิดไรเตอร์").plan
        (self.system / "libreoffice-writer.desktop").unlink()
        os.utime(self.system, (time.time() + 5, time.time() + 5))
        out = actions.Executor(runner=lambda a: 0, dry_run=False).execute(plan)
        self.assertFalse(out.ok)
        self.assertIn("ไม่พบแอป", out.message)

    def test_md_skill_can_open_installed_app(self):
        desktop(self.system, "libreoffice-writer.desktop", WRITER)
        step, err = mdskill.parse_step("เปิดแอป ไรเตอร์")
        self.assertEqual(err, "")
        self.assertEqual(step.plan.params, {"app": "desk:libreoffice-writer.desktop"})
        step, err = mdskill.parse_step("เปิดแอป libreoffice-writer.desktop")
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
