// แถบสถานะด้านบน (BRIEF 5.7 ข้อ 3) · ทุกค่ามาจากเครื่องจริงผ่าน system (Python)
// ค่าที่ยังไม่มีระบบรองรับ (โมเดล ไมค์ backup) บอกว่า "ยังไม่เชื่อมต่อ" ไม่แต่งตัวเลขขึ้นมา
import QtQuick
import QtQuick.Layouts

Rectangle {
    implicitHeight: 44
    color: Theme.surface
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        spacing: 8

        AppText { text: system.clock + " · " + system.shortDate; strong: true; oneLine: true; Layout.preferredWidth: 150 }
        Chip { text: "โมเดล: ยังไม่เชื่อมต่อ"; iconPath: Icons.cpu }
        Chip { text: "งานเบื้องหลัง: ไม่มี" }
        Item { Layout.fillWidth: true }
        Chip {
            text: system.cameraPresent ? "พบกล้อง" : "ไม่พบกล้อง"
            iconPath: system.cameraPresent ? Icons.camera : Icons.cameraOff
            kind: "neutral"
        }
        Chip { text: "ไมค์ปิด"; iconPath: Icons.mic }
        Rectangle { width: 1; height: 20; color: Theme.line }
        RowLayout {
            spacing: 6
            Icon { path: Icons.hdd; color: Theme.inkMuted; width: 16; height: 16 }
            AppText { text: system.storageText; color: Theme.inkMuted; size: Theme.fontSmall; oneLine: true }
        }
        RowLayout {
            spacing: 6
            Icon { path: Icons.thermo; color: Theme.inkMuted; width: 16; height: 16 }
            AppText { text: system.tempText; color: Theme.inkMuted; size: Theme.fontSmall; oneLine: true }
        }
        RowLayout {
            spacing: 6
            Icon { path: Icons.archive; color: Theme.inkMuted; width: 16; height: 16 }
            AppText { text: "สำรอง: ยังไม่ตั้งค่า"; color: Theme.inkMuted; size: Theme.fontSmall; oneLine: true }
        }
    }
}
