import copy
import sys
import time
import unittest
from unittest import mock

from aipc.doctor import hardware as hw
from aipc.skills import actions, command, machine, manifest, router, thainum


def ok_skill(**over):
    base = {
        "id": "demo-skill",
        "name": "ทดลอง",
        "description": "สกิลทดลอง",
        "examples": ["ก", "ข", "ค"],
        "worker": "code",
    }
    base.update(over)
    return base


class ManifestTest(unittest.TestCase):
    def test_all_builtin_skills_are_valid(self):
        skills = manifest.load_builtin()
        self.assertEqual(
            sorted(s.id for s in skills),
            # สกิล 2 (voice-note) และ 6 (what-is-this) ตัดออกในขอบเขตรอบ 3 (2026-09-28)
            # 2026-09-29: สรุปข้อความ + ร่างจดหมาย สร้างโดย Claude (forge.py) และผ่านการตรวจแล้ว
            [
                "letter-writer",
                "machine-status",
                "reminder",
                "summarize-text",
                "system-command",
                "translate",
            ],
        )

    def test_rejects_unknown_action_and_permission(self):
        errs = manifest.validate(
            ok_skill(actions=["delete_all_files"], permissions=["run_actions"])
        )
        self.assertTrue(any("delete_all_files" in e for e in errs))
        errs = manifest.validate(ok_skill(permissions=["root"]))
        self.assertTrue(any("root" in e for e in errs))

    def test_actions_require_run_actions_permission(self):
        self.assertTrue(manifest.validate(ok_skill(actions=["open_url"])))

    def test_rejects_too_broad_description(self):
        # BRIEF 5.8 ข้อ 3: กันสกิลเดียวยึดทุกบทสนทนา
        self.assertTrue(manifest.validate(ok_skill(description="ใช้กับทุกคำขอ")))

    def test_llm_skill_needs_prompt_and_prompt_has_limit(self):
        self.assertTrue(manifest.validate(ok_skill(worker="llm")))
        self.assertTrue(manifest.validate(ok_skill(worker="llm", prompt="x" * 5000)))
        self.assertEqual(manifest.validate(ok_skill(worker="llm", prompt="แปล")), [])

    def test_needs_examples(self):
        self.assertTrue(manifest.validate(ok_skill(examples=["ก"])))

    def test_from_dict_raises_with_all_errors(self):
        with self.assertRaises(manifest.InvalidSkill) as ctx:
            manifest.from_dict(ok_skill(id="X", worker="magic"))
        self.assertGreaterEqual(len(ctx.exception.errors), 2)


class ThaiNumberTest(unittest.TestCase):
    def test_words(self):
        cases = {"สี่สิบ": 40, "สี่สิบห้า": 45, "ยี่สิบ": 20, "สิบเอ็ด": 11, "สิบ": 10,
                 "ห้า": 5, "ร้อย": 100, "ร้อยห้าสิบ": 150, "เก้าสิบเก้า": 99}  # fmt: skip
        for words, n in cases.items():
            self.assertEqual(thainum.words_to_int(words), n, words)

    def test_find_in_sentence(self):
        self.assertEqual(thainum.find_number("ปรับเสียง 30"), 30)
        self.assertEqual(thainum.find_number("ปรับเสียง๔๐"), 40)
        self.assertEqual(thainum.find_number("ปรับเสียงหกสิบ"), 60)
        self.assertEqual(thainum.find_number("เสียงครึ่งหนึ่ง"), 50)
        self.assertIsNone(thainum.find_number("ปรับเสียง"))


class CommandTest(unittest.TestCase):
    def plan(self, text):
        c = command.parse(text)
        return (c.plan.action, c.plan.params) if c else None

    def test_open_sites_with_thai_names(self):
        for text in ("เปิดยูทูบ", "เปิด YouTube ครับ", "ช่วยเปิดยูทูปหน่อย", "ไปที่ youtube"):
            self.assertEqual(self.plan(text), ("open_url", {"site": "youtube"}), text)
        self.assertEqual(self.plan("เปิดจีเมล"), ("open_url", {"site": "gmail"}))

    def test_open_pages_and_apps(self):
        self.assertEqual(self.plan("เปิดหน้าตั้งค่า"), ("open_page", {"page": "settings"}))
        self.assertEqual(self.plan("เปิดสุขภาพเครื่อง"), ("open_page", {"page": "health"}))
        self.assertEqual(self.plan("เปิดเบราว์เซอร์"), ("open_app", {"app": "browser"}))

    def test_volume(self):
        self.assertEqual(self.plan("ปรับเสียงสี่สิบ"), ("set_volume", {"percent": 40}))
        self.assertEqual(self.plan("เสียง 70%"), ("set_volume", {"percent": 70}))
        self.assertEqual(self.plan("เสียงเบาลงหน่อย"), ("change_volume", {"step": -10}))
        self.assertEqual(self.plan("เพิ่มเสียง"), ("change_volume", {"step": 10}))
        self.assertEqual(self.plan("ปิดเสียง"), ("mute", {}))
        self.assertEqual(self.plan("เปิดเสียง"), ("unmute", {}))
        self.assertIsNone(self.plan("ปรับเสียง 250"))  # เกิน 100 ไม่ทำ

    def test_misspelling_asks_before_doing(self):
        c = command.parse("เปิดยูทิว")
        self.assertIsNotNone(c)
        self.assertTrue(c.needs_confirmation)

    def test_not_a_command(self):
        for text in ("สวัสดีครับ", "แปลคำว่า hello", "ทำไมเครื่องช้า", "", "เปิด"):
            self.assertIsNone(command.parse(text), text)

    def test_want_to_open(self):
        # สำรวจบน Pi 5 2026-10-12: "อยากดูไฟล์ของฉัน" ไม่เข้ากฎ → AI ตอบว่าเปิดให้ไม่ได้
        self.assertEqual(self.plan("อยากดูไฟล์ของฉัน"), ("open_page", {"page": "files"}))
        for text in ("อยากไปเที่ยวญี่ปุ่น", "อยากดูหนัง", "อยากได้สกิลโหมดเช้า เปิด Gmail"):
            self.assertIsNone(command.parse(text), text)

    def test_polite_words_only_cut_at_edges(self):
        # baseline การ์ด 0008: เคยตัด "ช่วย" ออกจากกลาง "ผู้ช่วย" จนเปิดหน้าผู้ช่วยไม่ได้
        self.assertEqual(command.normalize("ช่วยเปิดหน้าผู้ช่วยให้หน่อยครับ"), "เปิดหน้าผู้ช่วย")
        self.assertEqual(self.plan("เปิดหน้าผู้ช่วย"), ("open_page", {"page": "workspace"}))

    def test_longest_name_wins(self):
        # "ตัวจัดการไฟล์" ต้องไม่กลายเป็นหน้า "ไฟล์" · "กูเกิลแมพ" ต้องไม่กลายเป็น "กูเกิล"
        self.assertEqual(self.plan("เปิดตัวจัดการไฟล์"), ("open_app", {"app": "filemanager"}))
        self.assertEqual(self.plan("เปิดกูเกิลแมพ"), ("open_url", {"site": "maps"}))
        self.assertEqual(self.plan("เปิดไฟล์ของฉัน"), ("open_page", {"page": "files"}))

    def test_equal_length_names_for_different_targets_ask_first(self):
        c = command.parse("เปิดแผนที่กูเกิล")  # "แผนที่" กับ "กูเกิล" ยาวเท่ากัน
        self.assertTrue(c.needs_confirmation)

    def test_volume_needs_clear_direction(self):
        self.assertIsNone(self.plan("เสียงข้างบ้านดังมากเลย"))  # เล่าเรื่อง ไม่ใช่คำสั่ง
        self.assertEqual(self.plan("เสียงดังไป"), ("change_volume", {"step": -10}))  # "…ไป" = มากเกิน
        self.assertEqual(self.plan("เสียงเบาไป"), ("change_volume", {"step": 10}))

    def test_reminder_containing_a_command_is_not_run_now(self):
        for text in ("เตือนปิดเสียงตอนประชุมบ่ายสาม", "นัดเปิดยูทูบดูไลฟ์สองทุ่ม", "อย่าลืมปรับเสียง 50"):
            self.assertIsNone(command.parse(text), text)

    def test_cannot_smuggle_urls_or_shell(self):
        # ข้อความแบบ injection ต้องไม่กลายเป็นคำสั่ง (BRIEF 5.6 เกณฑ์ผ่าน)
        for text in ("เปิด https://evil.example/?data=secret", "เปิด rm -rf ~", "เปิด ; shutdown now"):
            self.assertIsNone(command.parse(text), text)


class ExecutorTest(unittest.TestCase):
    def test_commands_are_lists_and_never_shell(self):
        calls = []
        ex = actions.Executor(runner=lambda args: calls.append(args) or 0, dry_run=False)
        for text in ("เปิดยูทูบ", "ปรับเสียงสี่สิบ", "เสียงเบาลง", "ปิดเสียง", "เปิดเบราว์เซอร์"):
            out = ex.execute(command.parse(text).plan)
            self.assertTrue(out.ok, text)
        self.assertTrue(all(isinstance(a, list) for a in calls))
        self.assertIn(["xdg-open", "https://www.youtube.com"], calls)
        self.assertIn(["wpctl", "set-volume", actions.SINK, "40%"], calls)
        self.assertIn(["wpctl", "set-volume", "-l", "1.0", actions.SINK, "10%-"], calls)

    def test_dry_run_says_so(self):
        out = actions.Executor(dry_run=True).execute(command.parse("เปิดยูทูบ").plan)
        self.assertTrue(out.simulated)
        self.assertIn("จำลอง", out.message)

    def test_open_page_runs_nothing(self):
        calls = []
        ex = actions.Executor(runner=lambda a: calls.append(a) or 0, dry_run=False)
        out = ex.execute(command.parse("เปิดหน้าตั้งค่า").plan)
        self.assertEqual((out.page, calls), ("settings", []))

    def test_privacy_page_opens_settings(self):
        # หน้าความเป็นส่วนตัวตัดออก (รอบ 3) · คำสั่งยังเข้าใจเหมือนเดิม แต่หน้าจอพาไปหน้าตั้งค่า
        cmd = command.parse("เปิดหน้าความเป็นส่วนตัว")
        self.assertEqual(cmd.plan.params, {"page": "privacy"})
        out = actions.Executor(dry_run=False).execute(cmd.plan)
        self.assertEqual(out.page, "settings")
        self.assertIn("ตั้งค่า", out.message)

    def test_missing_app_is_reported(self):
        ex = actions.Executor(runner=lambda a: 1, dry_run=False)
        out = ex.execute(command.parse("เปิดเทอร์มินัล").plan)
        self.assertFalse(out.ok)
        self.assertIn("ไม่พบแอป", out.message)

    def test_unknown_action_refused(self):
        out = actions.Executor(dry_run=False).execute(actions.Plan("format_disk"))
        self.assertFalse(out.ok)


class AppCommandTest(unittest.TestCase):
    """พบ 2026-10-01: Pi 5 ไม่มี gtk-launch → เปิดแอปไม่ขึ้นเลย · ใช้ gio launch <ไฟล์ .desktop> แทน."""

    def test_gio_when_no_gtk_launch(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "lxterminal.desktop").write_text("[Desktop Entry]\n", encoding="utf-8")
            which = {"gio": "/usr/bin/gio"}.get
            with (
                mock.patch("shutil.which", which),
                mock.patch.object(actions, "DESKTOP_DIRS", (d,)),
            ):
                want = ["gio", "launch", str(Path(d) / "lxterminal.desktop")]
                self.assertEqual(actions._app_command("lxterminal.desktop"), want)
            with mock.patch("shutil.which", lambda n: "/usr/bin/" + n):  # มี gtk-launch = ใช้ตามเดิม
                self.assertEqual(
                    actions._app_command("lxterminal.desktop"), ["gtk-launch", "lxterminal.desktop"]
                )
        self.assertIn("gio", actions.LAUNCHERS)  # ไม่รอ output ของแอปที่เปิด


class LauncherTest(unittest.TestCase):
    """พบ 2026-09-28: รอ output ของแอปที่เปิด (capture_output) → แอปถือ pipe ค้าง หน้าจอค้าง 10 วิ
    แล้วบอกว่า "ทำไม่สำเร็จ" ทั้งที่แอปเปิดแล้ว · ตัวเปิดแอปต้องไม่รอแอป."""

    # "ตัวเปิด" ที่ปล่อยแอปลูกให้ทำงานต่อ 6 วิแล้วจบเอง (เหมือน gtk-launch)
    APP = (
        "import subprocess, sys; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(6)']); print('ok')"
    )

    def test_launcher_does_not_wait_for_the_app(self):
        with mock.patch.object(actions, "LAUNCHERS", (sys.executable,)):
            t0 = time.monotonic()
            code = actions.run_process([sys.executable, "-c", self.APP])
            elapsed = time.monotonic() - t0
        self.assertEqual(code, 0)
        self.assertLess(elapsed, 4, "ต้องไม่รอจนแอปปิด")

    def test_launcher_that_fails_at_once_is_reported(self):
        with mock.patch.object(actions, "LAUNCHERS", (sys.executable,)):
            code = actions.run_process([sys.executable, "-c", "raise SystemExit(3)"])
        self.assertNotEqual(code, 0)

    def test_missing_program(self):
        self.assertEqual(actions.run_process(["aipc-no-such-program-xyz"]), 127)


def checks(**status):
    base = {"power": hw.PASS, "cooling": hw.PASS, "storage": hw.PASS}
    base.update(status)
    return [hw.Check(k, k, v, "") for k, v in base.items()]


class MachineTest(unittest.TestCase):
    def test_healthy(self):
        d = machine.diagnose(checks(), 55.0, 4000)
        self.assertEqual(d.headline, "ไม่พบปัญหาจากค่าที่อ่านได้")
        self.assertEqual(d.advice, [])

    def test_storage_says_free_amount(self):
        # สำรวจบน Pi 5 2026-10-12: ถาม "พื้นที่เหลือเท่าไหร่" ได้แค่ "พอ" ไม่มีตัวเลข
        detail = "/dev/mmcblk0p2 · ทั้งหมด 60.9 GB · ใช้แล้ว 55% · ว่าง 24.6 GB"
        c = [hw.Check("storage", "s", hw.PASS, detail)]
        d = machine.diagnose(c, 55.0, 4000)
        self.assertIn("พื้นที่เก็บข้อมูลพอ · ว่าง 24.6 GB", [f.text for f in d.findings])

    def test_hot_and_low_memory(self):
        d = machine.diagnose(checks(), 83.0, 700)
        self.assertIn("ร้อนเกิน", d.headline)
        self.assertIn("หน่วยความจำ", d.headline)
        self.assertEqual(len(d.advice), 2)

    def test_undervoltage(self):
        d = machine.diagnose(checks(power=hw.FAIL), 50.0, 4000)
        self.assertIn("ไฟเลี้ยง", d.headline)
        self.assertTrue(any("27W" in a for a in d.advice))

    def test_unknowns_are_said_not_guessed(self):
        d = machine.diagnose(
            checks(power=hw.UNKNOWN, cooling=hw.UNKNOWN, storage=hw.UNKNOWN), None, None
        )
        self.assertIn("อ่านค่าสถานะของเครื่องนี้ไม่ได้", d.headline)
        self.assertEqual(set(d.unknown), {"ไฟเลี้ยง", "อุณหภูมิ", "พัดลม", "RAM ว่าง", "พื้นที่เก็บข้อมูล"})
        self.assertEqual(d.findings, [])  # ไม่มีข้อสรุปจากค่าที่ไม่มี

    def test_storage_full(self):
        d = machine.diagnose(checks(storage=hw.FAIL), 50.0, 4000)
        self.assertIn("พื้นที่", d.headline)


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.skills = manifest.load_builtin()

    def test_command_first(self):
        r = router.route("เปิดยูทูบ", self.skills, set())
        self.assertEqual((r.kind, r.skill.id), ("command", "system-command"))

    def test_machine_question_works_without_llm(self):
        r = router.route("ทำไมเครื่องช้าจัง", self.skills, set())
        self.assertEqual((r.kind, r.skill.id), ("skill", "machine-status"))

    def test_llm_skill_reports_what_is_missing(self):
        r = router.route("แปลเป็นอังกฤษให้หน่อย", self.skills, set())
        self.assertEqual((r.kind, r.skill.id, r.missing), ("needs", "translate", ["llm"]))
        r = router.route("แปลเป็นอังกฤษให้หน่อย", self.skills, {"llm"})
        self.assertEqual(r.kind, "skill")

    def test_other_skills(self):
        self.assertEqual(router.route("เตือนส่งงานพรุ่งนี้", self.skills, set()).skill.id, "reminder")
        # สกิล 2 และ 6 ตัดออกแล้ว → ไม่มีสกิลรับ ไปแชท
        self.assertEqual(router.route("นี่คืออะไร", self.skills, set()).kind, "chat")
        self.assertEqual(router.route("จดโน้ตประชุม", self.skills, set()).kind, "chat")

    def test_general_chat(self):
        self.assertEqual(router.route("เล่าเรื่องตลกให้ฟังหน่อย", self.skills, set()).kind, "chat")

    def test_at_most_three_candidates(self):
        many = [manifest.from_dict(ok_skill(id=f"s{i}xx", keywords=["คำ"])) for i in range(5)]
        r = router.route("คำ", copy.copy(many), set())
        self.assertLessEqual(len(r.candidates), 3)


if __name__ == "__main__":
    unittest.main()
