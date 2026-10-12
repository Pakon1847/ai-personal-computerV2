import os, subprocess, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication
app = QGuiApplication([])
from aipc.ui.backend import SkillsController
def vol():
    return subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True, text=True).stdout.strip()
s = SkillsController(reminders_path=Path(tempfile.mkdtemp()) / "r.json", run_timer=False)
print("before", vol())
for t in ["ปรับเสียงเป็น 40", "เพิ่มเสียง", "ปิดเสียง"]:
    c = s.handle(t)
    if c.get("confirmToken"):
        print("  ask:", c["title"]); c = s.confirm(c["confirmToken"], True)
    print(t, "→", c["title"], c.get("chips"), "| undo" if c.get("undoToken") else "", "|", vol())
    if c.get("undoToken"):
        u = s.undo(c["undoToken"]); print("   undo →", u["title"], "|", vol())
