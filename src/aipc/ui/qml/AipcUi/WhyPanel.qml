// "ทำไมได้คำตอบนี้" (ข้อเสนอ 2026-10-03) · ใครตอบ · ทำไมทางนี้ · ข้อมูลออกนอกเครื่องไหม · ใช้เวลาเท่าไหร่
// ข้อมูลมาจาก Python (สิ่งที่เกิดจริงในรอบนั้น) ไม่ใช่ให้ AI อธิบายตัวเอง · ปิดไว้ก่อน กดแล้วกาง
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property var rows: []
    property bool open: false
    visible: (rows || []).length > 0
    spacing: 2

    AppButton {
        objectName: "whyButton"
        text: root.open ? Tr.t("ซ่อนเหตุผล") : Tr.t("ทำไมได้คำตอบนี้")
        kind: "ghost"
        onClicked: root.open = !root.open
    }
    Repeater {
        model: root.open ? (root.rows || []) : []
        AppText {
            required property var modelData
            objectName: "whyRow"
            Layout.fillWidth: true
            textFormat: Text.PlainText
            text: modelData.k + ": " + modelData.v
            size: Theme.fontSmall
            color: Theme.inkMuted
        }
    }
}
