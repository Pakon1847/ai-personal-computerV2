// แถบสถานะด้านบน (BRIEF 5.7 ข้อ 3) · ทุกค่ามาจากเครื่องจริงผ่าน system (Python)
// การ์ด 0041 (ไม่รก): ไมค์ · กล้อง · ส่งออกวันนี้ แสดงตลอด (ความเป็นส่วนตัว H3) ·
// เครือข่าย/โมเดล/พื้นที่/ความร้อน/ไฟเลี้ยง รวมเป็นป้ายเดียว "เครื่องปกติ" · มีปัญหา = ป้ายเป็นข้อความของปัญหานั้นเอง (+N เมื่อมีหลายเรื่อง) ·
// ปัญหาตัดสินในโค้ด (system.alerts · H6) · แตะป้าย = หน้าเครื่อง (ค่าทุกตัวอยู่ที่นั่น)
// ค่าที่ยังไม่มีระบบรองรับบอกว่า "ยังไม่…" ไม่แต่งตัวเลขขึ้นมา (H5)
// ตัวอักษรใหญ่ (>125%) ป้ายรองเหลือแค่ไอคอน+tooltip · **กล้องกับไมค์แสดงข้อความเต็มเสมอ** (H3)
import QtQuick
import QtQuick.Layouts

Item {
    id: bar
    implicitHeight: Math.max(56, row.implicitHeight + 16)
    readonly property bool tight: Theme.fontScale > 1.25
    // ปัญหาทั้งหมดเรียงตามความสำคัญ: ของเครื่อง (system.alerts) ก่อน แล้วโมเดลภาษาที่ยังไม่พร้อม
    readonly property var problems: {
        const out = system.alerts.slice()
        if (!chat.ready && chat.status !== "off")   // off = หน้านี้ไม่ใช้โมเดล ไม่ใช่ปัญหา
            out.push({ text: chat.statusText,
                       level: (chat.status === "loading" || chat.status === "restarting") ? "accent" : "warn" })
        return out
    }

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 16
        spacing: 8

        AppText { text: system.clock; strong: true; size: Theme.fontHeading; oneLine: true }
        AppText { text: system.shortDate; color: Theme.inkMuted; oneLine: true }
        Item { Layout.fillWidth: true }
        // H3: ไมค์เปิดเฉพาะตอนกดค้างเพื่อพูด (การ์ด 0019 ข้อ 9) · ต้องเห็นชัดทุกหน้า
        Chip { objectName: "micIndicator"; text: voice.listening ? Tr.t("ไมค์เปิด · กำลังฟัง") : Tr.t("ไมค์ปิด"); iconPath: Icons.mic
               kind: voice.listening ? "warn" : "neutral" }
        Chip {
            objectName: "cameraIndicator"
            // H3: กำลังใช้กล้อง (ลงทะเบียน/ทดลองใบหน้า) ต้องเห็นชัดทุกหน้า
            text: face.busy ? Tr.t("กล้องกำลังใช้") : system.cameraPresent ? Tr.t("กล้องพร้อม · ไม่ได้ใช้") : Tr.t("ไม่พบกล้อง")
            kind: face.busy ? "warn" : "neutral"
            iconPath: system.cameraPresent || face.busy ? Icons.camera : Icons.cameraOff
        }
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
        Chip {
            objectName: "machineIndicator"
            readonly property var first: bar.problems.length ? bar.problems[0] : null
            text: first ? first.text + (bar.problems.length > 1 ? "  +" + (bar.problems.length - 1) : "") : Tr.t("เครื่องปกติ")
            kind: first ? first.level : "neutral"
            iconPath: first ? Icons.alert : Icons.check
            compact: bar.tight && !first   // มีปัญหา = ข้อความเต็มเสมอ
            Accessible.name: bar.problems.length ? bar.problems.map(p => p.text).join(" · ") : text
            TapHandler { onTapped: AppState.open("health") }
        }
    }
}
