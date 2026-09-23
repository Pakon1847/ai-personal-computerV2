// หน้า Skill · รายการจากไฟล์สกิลจริง (src/aipc/skills/builtin/*.json) ผ่าน skills.skills
// บอกตรง ๆ ว่าสกิลไหนใช้ได้แล้ว และสกิลไหนยังขาดอะไร
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    spacing: 16

    PageHeader {
        title: "Skill"
        subtitle: "AI เลือกสกิลเองจากรายการนี้ · สกิลเป็นข้อมูล ไม่ใช่โปรแกรม · ใช้ได้แค่สิทธิ์ที่แสดงไว้"
        AppButton { text: "นำเข้าจากไฟล์"; kind: "secondary"; enabled: false; ToolTip.visible: hovered; ToolTip.text: "ยังไม่พร้อม (ADR-011)" }
        AppButton { text: "ให้ AI ช่วยสร้าง"; iconPath: Icons.plus; enabled: false; ToolTip.visible: hovered; ToolTip.text: "ต้องมีโมเดลภาษาก่อน" }
    }

    GridLayout {
        Layout.fillWidth: true
        columns: 2
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: skills.skills
            Card {
                id: sc
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: col.implicitHeight + 28
                radius: Theme.radiusCard
                ColumnLayout {
                    id: col
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        AppText { text: sc.modelData.name; strong: true; size: Theme.px(17); oneLine: true; Layout.fillWidth: true }
                        Chip { text: sc.modelData.ready ? "ใช้ได้แล้ว" : "ยังไม่พร้อม"; kind: sc.modelData.ready ? "ok" : "neutral"; dot: true }
                    }
                    AppText { text: sc.modelData.description; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Chip { text: sc.modelData.worker }
                        Repeater { model: sc.modelData.permissions; Chip { required property string modelData; text: modelData; kind: "warn" } }
                    }
                    Repeater {
                        model: sc.modelData.missing
                        AppText { required property string modelData; text: "ต้องมีก่อน: " + modelData; size: Theme.fontCaption; color: Theme.inkFaint; Layout.fillWidth: true }
                    }
                }
            }
        }
    }
    Item { Layout.fillHeight: true }
}
