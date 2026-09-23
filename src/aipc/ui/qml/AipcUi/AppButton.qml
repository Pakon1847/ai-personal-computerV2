// ปุ่มมาตรฐาน · สร้างจาก Button ของ Qt Quick Controls เพื่อได้คีย์บอร์ด/focus/การกดครบ
// แล้วเปลี่ยนแค่หน้าตาให้ตรงระบบดีไซน์
// kind: primary | secondary | outline | warn | danger | ink | ghost
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Button {
    id: control
    property string kind: "primary"
    property string iconPath: ""
    property bool iconFilled: false

    readonly property color fillColor: ({
        primary: Theme.accentFill, warn: Theme.warnFill, danger: Theme.dangerFill,
        ink: Theme.inkFill, secondary: Theme.surface, outline: Theme.surface, ghost: "transparent"
    })[kind]
    readonly property color textColor: ({
        primary: Theme.textOnAccent, warn: Theme.textOnWarn, danger: Theme.textOnDanger, ink: Theme.textOnInk,
        secondary: Theme.ink, outline: Theme.accent, ghost: Theme.accent
    })[kind]

    implicitHeight: Theme.touch
    leftPadding: text === "" ? 12 : 18
    rightPadding: text === "" ? 12 : 18
    font.family: Theme.family
    font.pixelSize: Theme.px(15)
    font.weight: (kind === "secondary" || kind === "ghost") ? Font.Normal : Font.DemiBold
    hoverEnabled: true

    background: Rectangle {
        radius: Theme.radiusControl
        color: control.fillColor
        opacity: control.enabled ? (control.down ? 0.85 : 1.0) : 0.45
        border.width: control.kind === "outline" ? 2 : (control.kind === "secondary" ? 1 : 0)
        border.color: control.kind === "outline" ? Theme.accent : Theme.lineStrong
        // กรอบ focus ชัด ๆ เมื่อใช้คีย์บอร์ด (BRIEF 5.7: ใช้คีย์บอร์ดได้ทั้งระบบ เห็นตำแหน่ง focus ชัด)
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: control.visualFocus
        }
    }

    contentItem: RowLayout {
        spacing: 8
        Icon {
            visible: control.iconPath !== ""
            path: control.iconPath
            filled: control.iconFilled
            color: control.textColor
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            Layout.alignment: Qt.AlignVCenter
        }
        Text {
            visible: control.text !== ""
            text: control.text
            font: control.font
            color: control.textColor
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
