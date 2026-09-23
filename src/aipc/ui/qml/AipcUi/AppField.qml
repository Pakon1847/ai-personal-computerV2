// ช่องกรอกพร้อมป้ายชื่อและข้อความช่วย · hintKind: normal | ok | error
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string label: ""
    property string hint: ""
    property string hintKind: "normal"
    property alias text: input.text
    property alias placeholder: input.placeholderText
    property bool password: false
    property bool mono: false
    property bool emphasis: false
    property alias field: input
    spacing: 6

    AppText { text: root.label; strong: true; visible: root.label !== "" }

    TextField {
        id: input
        Layout.fillWidth: true
        implicitHeight: 48
        echoMode: root.password ? TextInput.Password : TextInput.Normal
        font.family: root.mono ? Theme.mono : Theme.family
        font.pixelSize: Theme.px(17)
        color: Theme.ink
        placeholderTextColor: Theme.inkFaint
        leftPadding: 14
        rightPadding: 14
        Accessible.name: root.label
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surface
            border.width: (root.emphasis || input.activeFocus) ? 2 : 1
            border.color: (root.emphasis || input.activeFocus) ? Theme.accent : Theme.lineStrong
        }
    }

    AppText {
        visible: root.hint !== ""
        text: root.hint
        size: Theme.fontCaption
        color: root.hintKind === "ok" ? Theme.okInk : root.hintKind === "error" ? Theme.danger : Theme.inkMuted
        Layout.fillWidth: true
    }
}
