// ตัวเลือกแบบแถบแบ่งช่อง (segmented control) · เลือกได้ทีละ 1 จากกลุ่มเดียวกัน
// Pakon 2026-10-22: ปุ่มเลือกแชท/โมเดลเดิมหน้าตาเหมือนปุ่มเปิด-ปิดเสียงอ่าน → แยกไม่ออกว่าอันไหนคือ "เลือก 1 ใน n"
// จึงใช้ราง 1 อัน + ช่องข้างใน · ช่องที่เลือก = พื้นสีเน้น + เครื่องหมายถูก (ไม่ใช้สีอย่างเดียวบอกสถานะ) · ป้ายกำกับอยู่ซ้ายของราง
// กดง่าย: สูงอย่างน้อย 44 · ใช้คีย์บอร์ดได้ (Tab เข้า ลูกศรซ้าย/ขวาเลือก)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

RowLayout {
    id: seg
    property string label: ""
    property var options: []       // [{ value: "work", text: "แชทงาน", hint: "Claude" }]
    property string current: ""
    signal picked(string value)
    spacing: 10

    AppText {
        visible: seg.label !== ""
        text: seg.label
        size: Theme.fontSmall
        color: Theme.inkMuted
        Layout.alignment: Qt.AlignVCenter
    }
    Rectangle {
        id: track
        objectName: "segTrack"
        implicitWidth: row.implicitWidth + 8
        implicitHeight: row.implicitHeight + 8
        radius: height / 2
        color: Theme.surface2
        border.width: 1
        border.color: Theme.lineStrong
        activeFocusOnTab: true
        Accessible.role: Accessible.PageTabList
        Accessible.name: seg.label
        Keys.onLeftPressed: seg.step(-1)
        Keys.onRightPressed: seg.step(1)
        Rectangle {   // กรอบ focus ชัด ๆ เมื่อใช้คีย์บอร์ด (BRIEF 5.7)
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: track.activeFocus
        }
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 2
            Repeater {
                model: seg.options
                delegate: Rectangle {
                    id: cell
                    required property var modelData
                    readonly property bool on: seg.current === modelData.value
                    objectName: "seg_" + modelData.value
                    width: content.implicitWidth + 32
                    height: Math.max(Theme.touch - 8, content.implicitHeight + 12)
                    radius: height / 2
                    color: on ? Theme.accentFill : (hover.hovered ? Theme.surface : "transparent")
                    Behavior on color { ColorAnimation { duration: Theme.animMs } }
                    Accessible.role: Accessible.PageTab
                    Accessible.name: modelData.text + (on ? Tr.t(" · เลือกอยู่") : "")
                    RowLayout {
                        id: content
                        anchors.centerIn: parent
                        spacing: 6
                        Icon {
                            visible: cell.on
                            path: Icons.check
                            color: Theme.textOnAccent
                            stroke: 2.4
                            Layout.preferredWidth: Theme.px(16)
                            Layout.preferredHeight: Theme.px(16)
                        }
                        AppText {
                            text: cell.modelData.text
                            strong: cell.on
                            color: cell.on ? Theme.textOnAccent : Theme.ink
                            size: Theme.px(15)
                        }
                        AppText {
                            visible: !!cell.modelData.hint
                            text: cell.modelData.hint || ""
                            color: cell.on ? Theme.textOnAccent : Theme.inkFaint
                            size: Theme.fontCaption
                        }
                    }
                    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: if (!cell.on) seg.picked(cell.modelData.value) }
                }
            }
        }
    }
    function step(d) {
        const i = options.findIndex(o => o.value === current)
        const j = Math.max(0, Math.min(options.length - 1, i + d))
        if (j !== i) picked(options[j].value)
    }
}
