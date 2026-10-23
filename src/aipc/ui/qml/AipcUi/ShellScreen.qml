// หน้าหลักหลังเข้าสู่ระบบ (การ์ด 0002): รางนำทางซ้าย + แถบสถานะบน + หน้าที่เลือก
import QtQuick
import QtQuick.Layouts

Rectangle {
    color: Theme.bg
    // ออกจาก Shell (เช่นกด "ออก" ในหน้าต่างพัฒนา) = หยุดงานกล้องที่ค้างอยู่ ไม่ให้กล้องเปิดต่อหลังหน้าจอหายไป
    // (การ์ด 0006 ข้อ 6 · พบ 2026-09-28 ว่าไม่มีใครสั่งหยุด)
    Component.onDestruction: if (typeof face !== "undefined" && face) face.cancel()

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Sidebar { Layout.fillHeight: true }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            StatusBar { Layout.fillWidth: true }
            StackLayout {
                id: pages
                objectName: "shellPages"
                function goTo(name) { AppState.page = name }   // เทสต์/คำสั่งเสียงเปลี่ยนหน้าได้ทางเดียวกัน
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                // หน้าความเป็นส่วนตัวตัดออกในขอบเขตรอบ 3 · ที่ลบข้อมูลใบหน้าอยู่ในหน้าตั้งค่า จึงพาไปหน้านั้นแทน
                readonly property var order: ["workspace", "calendar", "files", "skills", "health", "settings"]
                currentIndex: Math.max(0, order.indexOf(AppState.page === "privacy" ? "settings" : AppState.page))
                // การ์ด 0062: เปลี่ยนหน้า = จางเข้า + เลื่อนขึ้น 12 px (200 ms) · ปิดภาพเคลื่อนไหว = เปลี่ยนทันที
                transform: Translate { id: pageShift }
                onCurrentIndexChanged: if (uiSettings.animations) pageEnter.restart()
                ParallelAnimation {
                    id: pageEnter
                    NumberAnimation { target: pages; property: "opacity"; from: 0; to: 1; duration: 200; easing.type: Easing.OutCubic }
                    NumberAnimation { target: pageShift; property: "y"; from: 12; to: 0; duration: 200; easing.type: Easing.OutCubic }
                }

                WorkspacePage {}
                // ปฏิทินตารางเดือน (การ์ด 0038) · อ่านอย่างเดียว · ข้อมูลชุดเดียวกับคำตอบนัด
                PageScroll {
                    contentHeight: calendarPage.implicitHeight + 40
                    CalendarPage { id: calendarPage; x: 32; y: 8; width: parent.width - 64 }
                }
                Item {
                    FilesPage { anchors.fill: parent; anchors.margins: 24; anchors.topMargin: 8; anchors.leftMargin: 32; anchors.rightMargin: 32 }
                }
                PageScroll {
                    contentHeight: skillsPage.implicitHeight + 40
                    SkillsPage { id: skillsPage; x: 32; y: 8; width: parent.width - 64 }
                }
                PageScroll {
                    contentHeight: healthPage.implicitHeight + 40
                    HealthPage { id: healthPage; x: 32; y: 8; width: parent.width - 64 }
                }
                PageScroll {
                    contentHeight: settingsPage.implicitHeight + 40
                    SettingsPage { id: settingsPage; x: 32; y: 8; width: parent.width - 64 }
                }
            }
        }
    }

    // การเตือนนัดหมายลอยอยู่มุมขวาบน ใต้แถบสถานะ เหนือทุกหน้า
    ReminderToast {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 120
        anchors.rightMargin: 24
        z: 10
    }
}
