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
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                // หน้าความเป็นส่วนตัวตัดออกในขอบเขตรอบ 3 · ที่ลบข้อมูลใบหน้าอยู่ในหน้าตั้งค่า จึงพาไปหน้านั้นแทน
                readonly property var order: ["workspace", "files", "skills", "health", "settings"]
                currentIndex: Math.max(0, order.indexOf(AppState.page === "privacy" ? "settings" : AppState.page))

                WorkspacePage {}
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
