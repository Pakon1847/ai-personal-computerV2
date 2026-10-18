// ช่องกรอกพร้อมป้ายชื่อและข้อความช่วย · hintKind: normal | ok | warn | error
// ช่องรหัสผ่านที่มีตัวอักษรไทย = อาจลืมสลับแป้น (ช่องนี้ซ่อนตัวอักษร จึงมองไม่เห็นเอง) → เตือนแทนข้อความช่วย ไม่ห้ามส่ง
// ไม่นับเลขไทย ๐–๙ เพราะช่อง PIN รับได้ (พบ 2026-09-29: หน้า Login เคยมีแต่แป้นอังกฤษ ตอนนี้สลับไทยได้แล้ว)
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
    readonly property bool thaiInPassword: password && /[\u0E01-\u0E4F\u0E5A-\u0E7F]/.test(input.text)
    readonly property string shownHint: thaiInPassword ? Tr.t("มีตัวอักษรไทย · ถ้าไม่ได้ตั้งใจ กด ~ สลับเป็นอังกฤษ") : hint
    readonly property string shownKind: thaiInPassword ? "warn" : hintKind
    spacing: 6

    AppText { text: root.label; strong: true; visible: root.label !== "" }

    TextField {
        id: input
        Layout.fillWidth: true
        // สูงอย่างน้อย 48 และสูงตามตัวอักษรเมื่อขยาย 150–200% ไม่ให้ตัวอักษรชนขอบ (BRIEF 5.7)
        implicitHeight: Math.max(48, Math.ceil(font.pixelSize * 1.9))
        echoMode: root.password ? TextInput.Password : TextInput.Normal
        font.family: root.mono ? Theme.mono : Theme.family
        font.pixelSize: Theme.px(17)
        color: Theme.ink
        placeholderTextColor: Theme.inkFaint
        leftPadding: 20
        rightPadding: 20
        Accessible.name: root.label !== "" ? root.label : root.placeholder
        background: Rectangle {
            radius: height / 2
            color: Theme.surface
            border.width: (root.emphasis || input.activeFocus) ? 2 : 1
            border.color: (root.emphasis || input.activeFocus) ? Theme.accent : Theme.lineStrong
        }
    }

    AppText {
        visible: root.shownHint !== ""
        text: root.shownHint
        size: Theme.fontCaption
        color: root.shownKind === "ok" ? Theme.okInk : root.shownKind === "error" ? Theme.danger
             : root.shownKind === "warn" ? Theme.warnInk : Theme.inkMuted
        Layout.fillWidth: true
    }
}
