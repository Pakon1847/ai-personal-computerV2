// ไทล์กดได้ในหน้าแรก (การ์ด 0041) · ไอคอนในกรอบสีคราม + ชื่อใต้ไอคอน
// สร้างจาก Button เหมือน AppButton = ได้คีย์บอร์ด/focus/การกดครบ · ไอคอนเส้นชุดเดิม ไม่ใช้โลโก้ของบริษัท
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Button {
    id: control
    property string iconPath: ""
    property string glyph: ""   // ตัวอักษรแทนไอคอน (เช่น "31" ของปฏิทิน) ใช้เมื่อไม่มีไอคอนที่สื่อได้
    hoverEnabled: true
    padding: 10
    implicitWidth: 112
    implicitHeight: Math.max(96, col.implicitHeight + 2 * padding)
    Accessible.name: text
    Keys.onReturnPressed: (event) => { control.clicked(); event.accepted = true }
    Keys.onEnterPressed: (event) => { control.clicked(); event.accepted = true }

    background: Rectangle {
        radius: Theme.radiusLarge
        // ชี้/กด = พื้นคราม + เส้นขอบ (เปลี่ยนแค่สี ไม่ขยับขนาด · ไม่มีภาพเคลื่อนไหววน)
        color: control.down ? Theme.accentSoft : Theme.surface2
        border.width: control.hovered || control.down ? 1 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.animMs } }
        Rectangle {   // กรอบ focus เมื่อใช้คีย์บอร์ด (BRIEF 5.7)
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: control.visualFocus
        }
    }

    contentItem: ColumnLayout {
        id: col
        spacing: 8
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 44; implicitHeight: 44
            radius: 12
            color: Theme.accentSoft
            Icon {
                visible: control.glyph === ""
                anchors.centerIn: parent
                path: control.iconPath
                color: Theme.accentInk
                width: 22; height: 22
            }
            AppText {
                visible: control.glyph !== ""
                anchors.centerIn: parent
                text: control.glyph
                strong: true
                color: Theme.accentInk
                oneLine: true
            }
        }
        AppText {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: control.text
            size: Theme.fontSmall
            color: Theme.inkMuted
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Item { Layout.fillHeight: true }   // ไทล์สูงเท่ากัน: ไอคอนเริ่มที่บรรทัดเดียวกันทุกไทล์
    }
}
