// ป้ายสถานะเล็ก ๆ · kind: neutral | accent | ok | warn | danger
// compact = เหลือแค่ไอคอน (ข้อความย้ายไปอยู่ใน tooltip) ใช้ตอนตัวอักษรใหญ่จนแถบสถานะไม่พอ
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root
    property string text: ""
    property string kind: "neutral"
    property string iconPath: ""
    property bool dot: false
    property bool compact: false

    readonly property color bgColor: ({
        neutral: Theme.surface2, accent: Theme.accentSoft, ok: Theme.okSoft,
        warn: Theme.warnSoft, danger: Theme.dangerSoft
    })[kind]
    readonly property color fgColor: ({
        neutral: Theme.inkMuted, accent: Theme.accentInk, ok: Theme.okInk,
        warn: Theme.warnInk, danger: Theme.danger
    })[kind]
    readonly property color dotColor: ({
        neutral: Theme.inkFaint, accent: Theme.accent, ok: Theme.ok, warn: Theme.warn, danger: Theme.danger
    })[kind]

    radius: height / 2
    color: bgColor
    implicitHeight: Math.max(28, label.implicitHeight + 8)
    implicitWidth: row.implicitWidth + 20
    Accessible.name: text
    Accessible.role: Accessible.StaticText

    HoverHandler { id: hover }
    ToolTip.visible: compact && hover.hovered
    ToolTip.text: text

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Rectangle { visible: root.dot; width: 8; height: 8; radius: 4; color: root.dotColor }
        Icon { visible: root.iconPath !== ""; path: root.iconPath; color: root.fgColor; Layout.preferredWidth: 16; Layout.preferredHeight: 16 }
        AppText { id: label; visible: !root.compact || root.iconPath === ""; text: root.text; size: Theme.fontSmall; color: root.fgColor; oneLine: true }
    }
}
