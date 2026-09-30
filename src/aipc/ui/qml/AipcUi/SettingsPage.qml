// หน้าตั้งค่า · ธีมและขนาดตัวอักษรทำงานจริงและบันทึกลง ~/.config/aipc/ui.json
// ใบหน้าของฉัน (การ์ด 0006) ลงทะเบียน/ทดลอง/ลบได้จริง · การตรวจเจ้าของ (ปิดบัง/ล็อก) ไม่มีในรุ่นนี้ (ขอบเขตรอบ 3)
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    spacing: 16

    PageHeader { title: "ตั้งค่า" }

    Card {
        Layout.fillWidth: true
        Layout.preferredHeight: themeCol.implicitHeight + 40
        radius: Theme.radiusCard
        ColumnLayout {
            id: themeCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    AppText { text: "ธีม"; strong: true }
                    AppText { text: "เปลี่ยนทั้งระบบทันที รวมหน้า Login"; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                }
                AppCheck { text: "สว่าง"; radio: true; autoExclusive: true; checked: uiSettings.theme === "light"; onClicked: uiSettings.setTheme("light") }
                AppCheck { text: "มืด"; radio: true; autoExclusive: true; checked: uiSettings.theme === "dark"; onClicked: uiSettings.setTheme("dark") }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.lineSoft }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    AppText { text: "ขนาดตัวอักษร"; strong: true }
                    AppText { text: "100–200% ตาม BRIEF 5.7"; size: Theme.fontSmall; color: Theme.inkMuted }
                }
                Repeater {
                    model: [1.0, 1.25, 1.5, 1.75, 2.0]
                    AppButton {
                        required property real modelData
                        text: Math.round(modelData * 100) + "%"
                        kind: uiSettings.fontScale === modelData ? "primary" : "secondary"
                        onClicked: uiSettings.setFontScale(modelData)
                    }
                }
            }
        }
    }

    FacePanel { Layout.fillWidth: true }
    LoginFacePanel { Layout.fillWidth: true }

    // ประวัติแชทอยู่ใน home ของคุณเท่านั้น · ลบทั้งหมดได้ทันที (การ์ด 0013 ข้อ 4)
    Card {
        Layout.fillWidth: true
        implicitHeight: chatRow.implicitHeight + 40
        RowLayout {
            id: chatRow
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                AppText { text: "ประวัติแชท"; strong: true }
                AppText { id: chatDeleted; Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                          text: "เก็บในเครื่องนี้ในโฟลเดอร์ของคุณ · " + chat.history.length + " บทสนทนา" }
            }
            AppButton {
                objectName: "deleteChats"
                text: "ลบประวัติแชททั้งหมด"; kind: "secondary"; iconPath: Icons.trash
                enabled: chat.history.length > 0 && !chat.busy
                onClicked: chatDeleted.text = "ลบแล้ว " + chat.deleteAll() + " บทสนทนา"
            }
        }
    }

    Item { Layout.fillHeight: true }
}
