// หน้าที่ยังไม่มีระบบรองรับ (Skill, ความเป็นส่วนตัว) · บอกว่ายังไม่พร้อม และจะทำอะไรเมื่อพร้อม
// รายการ "จะทำ" มาจาก BRIEF ตรง ๆ (เป็นข้อกำหนด ไม่ใช่ข้อมูลของผู้ใช้)
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string title: ""
    property string subtitle: ""
    property string phase: ""
    property var plans: []
    spacing: 16

    PageHeader { title: root.title; subtitle: root.subtitle }
    NotReady { Layout.fillWidth: true; title: root.title + " · ยังไม่พร้อม"; detail: root.phase }
    Card {
        Layout.fillWidth: true
        Layout.preferredHeight: planCol.implicitHeight + 40
        radius: Theme.radiusCard
        ColumnLayout {
            id: planCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 8
            AppText { text: "เมื่อพร้อม หน้านี้จะ"; strong: true }
            Repeater {
                model: root.plans
                RowLayout {
                    required property string modelData
                    Layout.fillWidth: true
                    spacing: 10
                    Icon { path: Icons.check; color: Theme.inkFaint; Layout.alignment: Qt.AlignTop }
                    AppText { text: parent.modelData; Layout.fillWidth: true }
                }
            }
        }
    }
    Item { Layout.fillHeight: true }
}
