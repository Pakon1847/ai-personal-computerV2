// ปุ่มชอบ/ไม่ชอบใต้ผลของ AI ในเครื่อง (การ์ด 0085 · อาจารย์ขอ 2026-11-20) · ขึ้นช่วงสั้น ๆ แล้วหายเอง
// ชอบ / ไม่กด = ไม่มีงานเพิ่ม · ไม่ชอบ = ส่งรอบนี้ให้ Claude ตรวจ (Python ตัดสินว่าส่งได้ไหม · หน้าจอส่งแค่ turnId)
// เวลาหมดเก็บเป็นเวลาจริง (until) ไม่ใช่ตัวนับในแถว: ListView สร้างแถวใหม่ตอนเลื่อน/เพิ่มข้อความ ตัวนับจะเริ่มใหม่ทุกครั้ง
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

RowLayout {
    id: bar
    property string turnId: ""
    property real until: 0        // มิลลิวินาทีแบบ Date.now() ที่ปุ่มหาย
    property bool done: false     // กดไปแล้ว (หน้าแชทจำไว้ ไม่ให้กดซ้ำ)
    property bool expired: false
    signal rated(bool liked)

    visible: turnId !== "" && !done && !expired
    spacing: 4

    function check() { expired = until <= Date.now() }
    onUntilChanged: check()
    Component.onCompleted: check()
    Timer {   // ตรวจทุก 0.25 วิ เฉพาะตอนปุ่มยังเห็นอยู่
        running: bar.visible
        repeat: true
        interval: 250
        onTriggered: bar.check()
    }

    AppText { text: Tr.t("ผลนี้ตรงใจไหม"); size: Theme.fontSmall; color: Theme.inkMuted }
    AppButton {
        objectName: "likeResult"
        text: Tr.t("ชอบ"); kind: "ghost"
        onClicked: bar.rated(true)
    }
    AppButton {
        objectName: "dislikeResult"
        text: Tr.t("ไม่ชอบ"); kind: "ghost"
        ToolTip.visible: hovered
        ToolTip.text: Tr.t("ส่งรอบนี้ให้ Claude ตรวจและแก้สกิล")
        onClicked: bar.rated(false)
    }
}
