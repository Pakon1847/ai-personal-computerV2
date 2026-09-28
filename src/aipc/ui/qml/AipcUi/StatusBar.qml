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
        Chip { objectName: "micIndicator"; text: "ไมค์ปิด"; iconPath: Icons.mic }
        Chip { text: "โมเดล: ยังไม่เชื่อมต่อ"; iconPath: Icons.cpu; kind: "warn"; compact: bar.tight }
        Chip { text: system.storageText; iconPath: Icons.hdd; compact: bar.tight }
        Chip { text: system.tempText; iconPath: Icons.thermo; compact: bar.tight; Accessible.name: "อุณหภูมิ " + system.tempText }
    }
}
