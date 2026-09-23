// หน้าหลักหลังเข้าสู่ระบบ: แถบสถานะบน + แถบนำทางซ้าย + หน้าที่เลือก
import QtQuick
import QtQuick.Layouts

Rectangle {
    color: Theme.bg

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        StatusBar { Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Sidebar { Layout.fillHeight: true }
            StackLayout {
                id: pages
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                readonly property var order: ["workspace", "files", "skills", "privacy", "health", "settings"]
                currentIndex: Math.max(0, order.indexOf(AppState.page))

                WorkspacePage {}
                Item {
                    FilesPage { anchors.fill: parent; anchors.margins: 24; anchors.leftMargin: 32; anchors.rightMargin: 32 }
                }
                Item {
                    SkillsPage { anchors.fill: parent; anchors.margins: 24; anchors.leftMargin: 32; anchors.rightMargin: 32 }
                }
                Item {
                    PlannedPage {
                        anchors.fill: parent; anchors.margins: 24; anchors.leftMargin: 32; anchors.rightMargin: 32
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
                Item {
                    HealthPage { anchors.fill: parent; anchors.margins: 24; anchors.leftMargin: 32; anchors.rightMargin: 32 }
                }
                Item {
                    SettingsPage { anchors.fill: parent; anchors.margins: 24; anchors.leftMargin: 32; anchors.rightMargin: 32 }
                }
            }
        }
    }
}
