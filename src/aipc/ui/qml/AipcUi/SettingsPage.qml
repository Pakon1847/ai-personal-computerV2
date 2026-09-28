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

    Item { Layout.fillHeight: true }
}
