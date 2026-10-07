"""AI ในเครื่องต่อเน็ตไม่ได้ด้วยกลไกของ OS (Pakon เลือก 2026-10-07).

ล็อกกฎใน scripts/pi/session/aipc-llm.service ·
ผลบน Pi 5: docs/benchmarks/2026-10-07-llm-netsandbox-pi5
"""

import unittest
from pathlib import Path

UNIT = Path(__file__).resolve().parents[1] / "scripts" / "pi" / "session" / "aipc-llm.service"


def service_lines() -> list[str]:
    lines, inside = [], False
    for raw in UNIT.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("["):
            inside = line == "[Service]"
            continue
        if inside and line and not line.startswith("#"):
            lines.append(line)
    return lines


class LlmUnitSandboxTest(unittest.TestCase):
    def test_only_unix_sockets(self):
        """seccomp: llama-server สร้างได้แค่ Unix socket ·
        คุยกับหน้าจอผ่าน $XDG_RUNTIME_DIR/aipc/llm.sock."""
        self.assertIn("RestrictAddressFamilies=AF_UNIX", service_lines())

    def test_own_network_namespace(self):
        """ชั้นที่สอง: network namespace ที่มีแค่ loopback."""
        self.assertIn("PrivateNetwork=yes", service_lines())

    def test_no_ipaddressdeny(self):
        """IPAddressDeny= ไม่มีผลใน user service (ลองบน Pi 5 2026-10-07) →
        ห้ามใส่ ให้คนอ่านเข้าใจผิดว่ากันได้."""
        self.assertFalse([x for x in service_lines() if x.startswith("IPAddressDeny=")])

    def test_server_listens_on_unix_socket_only(self):
        """ตัวเริ่ม llama-server ต้องฟังที่ socket ไฟล์ (ถ้าเปลี่ยนเป็นพอร์ต จะเริ่มไม่ได้เพราะ seccomp)."""
        start = (UNIT.parent / "aipc-llm-start").read_text(encoding="utf-8")
        self.assertIn('--host "$DIR/llm.sock"', start)
        self.assertNotIn("--port", start)


if __name__ == "__main__":
    unittest.main()
