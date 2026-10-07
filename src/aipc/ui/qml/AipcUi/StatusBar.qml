// แถบสถานะด้านบน (BRIEF 5.7 ข้อ 3) · ทุกค่ามาจากเครื่องจริงผ่าน system (Python)
// ต้องมีครบ: เครือข่าย · โมเดลและงานเบื้องหลัง · ไฟกล้อง/ไมค์ · พื้นที่ · ความร้อน · backup
// ค่าที่ยังไม่มีระบบรองรับ (โมเดล ไมค์ backup) บอกว่า "ยังไม่…" ไม่แต่งตัวเลขขึ้นมา (H5)
// ตัวอักษรใหญ่ (>125%) ป้ายรองเหลือแค่ไอคอน+tooltip · **กล้องกับไมค์แสดงข้อความเต็มเสมอ** (H3)
import QtQuick
import QtQuick.Layouts

Item {
    id: bar
    implicitHeight: Math.max(56, row.implicitHeight + 16)
    readonly property bool tight: Theme.fontScale > 1.25

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 16
        spacing: 6

        AppText { text: system.clock + " · " + system.shortDate; strong: true; oneLine: true }
        Item { Layout.fillWidth: true }
        Chip {
            objectName: "networkIndicator"
            text: ({ on: "เครือข่าย: ต่ออยู่", off: "ออฟไลน์", unknown: "เครือข่าย: ไม่รู้" })[system.networkState]
            kind: system.networkState === "off" ? "warn" : "neutral"
            iconPath: Icons.globe
            compact: bar.tight
        }
        Chip {
            objectName: "cameraIndicator"
            // H3: กำลังใช้กล้อง (ลงทะเบียน/ทดลองใบหน้า) ต้องเห็นชัดทุกหน้า
            text: face.busy ? "กล้องกำลังใช้" : system.cameraPresent ? "กล้องพร้อม · ไม่ได้ใช้" : "ไม่พบกล้อง"
            kind: face.busy ? "warn" : "neutral"
            iconPath: system.cameraPresent || face.busy ? Icons.camera : Icons.cameraOff
        }
        // H3: ไมค์เปิดเฉพาะตอนกดค้างเพื่อพูด (การ์ด 0019 ข้อ 9) · ต้องเห็นชัดทุกหน้า
        Chip { objectName: "micIndicator"; text: voice.listening ? "ไมค์เปิด · กำลังฟัง" : "ไมค์ปิด"; iconPath: Icons.mic
               kind: voice.listening ? "warn" : "neutral" }
        // สถานะจริงจาก /health ของ llama-server (การ์ด 0013 · H5)
        Chip { objectName: "modelIndicator"; text: chat.statusText; iconPath: Icons.cpu; compact: bar.tight
               kind: chat.ready ? "ok" : (chat.status === "loading" || chat.status === "restarting") ? "accent" : "warn" }
        // แผงความเป็นส่วนตัวแบบสด (2026-10-07): AI ในเครื่องถูก OS ล็อกเน็ตไหม · ส่งออกวันนี้กี่ครั้ง (เปลี่ยนสีเมื่อมีข้อมูลออก)
        // ค่าจาก OS และบันทึกส่งออกจริง (aipc.ui.privacy) · แตะ = หน้าตั้งค่า (ดูข้อความที่ส่งจริง · ปิดสวิตช์)
        Chip {
            objectName: "privacyIndicator"
            visible: privacyStatus.visible
            text: privacyStatus.text
            kind: privacyStatus.kind
            iconPath: privacyStatus.llmState === "locked" ? Icons.lock : Icons.shield
            compact: bar.tight
            Accessible.name: privacyStatus.text
            TapHandler { onTapped: AppState.open("settings") }
        }
        Chip { text: system.storageText; iconPath: Icons.hdd; compact: bar.tight }
        Chip { text: system.tempText; iconPath: Icons.thermo; compact: bar.tight; Accessible.name: "อุณหภูมิ " + system.tempText }
    }
}
