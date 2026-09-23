// หน้าหลักหลังเข้าสู่ระบบ (การ์ด 0002): รางนำทางซ้าย + แถบสถานะบน + หน้าที่เลือก
import QtQuick
import QtQuick.Layouts

Rectangle {
    color: Theme.bg

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
                readonly property var order: ["workspace", "files", "skills", "privacy", "health", "settings"]
                currentIndex: Math.max(0, order.indexOf(AppState.page))

                WorkspacePage {}
                Item {
                    FilesPage { anchors.fill: parent; anchors.margins: 24; anchors.topMargin: 8; anchors.leftMargin: 32; anchors.rightMargin: 32 }
                }
                PageScroll {
                    contentHeight: skillsPage.implicitHeight + 40
                    SkillsPage { id: skillsPage; x: 32; y: 8; width: parent.width - 64 }
                }
                PageScroll {
                    contentHeight: privacyPage.implicitHeight + 40
                    PlannedPage {
                        id: privacyPage
                        x: 32; y: 8; width: parent.width - 64
                        title: "ความเป็นส่วนตัว"
                        subtitle: "ระบบเก็บอะไรของคุณ เก็บที่ไหน นานเท่าไร และใครเข้าถึงได้"
                        phase: "ต้องมีฐานข้อมูลและการเข้ารหัสรายบัญชีก่อน (เฟส 1–2, BRIEF 5.8 Privacy Center)"
                        plans: [
                            "แสดงข้อมูลแยกหมวด: โปรไฟล์ แม่แบบใบหน้า แชท ไฟล์ ข้อมูล Skill API Key ประวัติคำสั่ง",
                            "ส่งออกข้อมูลของคุณเป็นไฟล์ JSON/Markdown",
                            "ลบรายหมวด ถอนความยินยอมใช้ใบหน้า และดูประวัติการส่งข้อมูลไป Cloud"
                        ]
                    }
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
