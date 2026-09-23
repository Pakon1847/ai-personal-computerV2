// ช่องในแถบนำทางแบบราง (การ์ด 0002) · ไอคอน + คำสั้นใต้ไอคอนเสมอ (BRIEF 5.7 ข้อ 6)
// ชื่อเต็มอยู่ใน tooltip และ Accessible.name เพราะรางแคบ 76 px ใส่คำยาวไม่ได้
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AbstractButton {
    id: item
    property string iconPath: ""
    property string pageName: ""
    property string shortText: text
    readonly property bool active: AppState.page === pageName
    implicitWidth: Math.round(60 * Math.min(Theme.fontScale, 1.8))
    implicitHeight: Math.max(56, col.implicitHeight + 10)
    Layout.alignment: Qt.AlignHCenter
    onClicked: AppState.page = pageName
    Accessible.role: Accessible.PageTab
    Accessible.name: text
    hoverEnabled: true
    ToolTip.visible: hovered
    ToolTip.text: text
    ToolTip.delay: 400

    background: Rectangle {
        radius: 14
        color: item.active ? Theme.accentSoft : (item.hovered ? Theme.surface2 : "transparent")
        Rectangle {
            anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2
            color: "transparent"; border.width: 2; border.color: Theme.accent; visible: item.visualFocus
        }
    }
    contentItem: Item {
        ColumnLayout {
            id: col
            anchors.centerIn: parent
            width: item.width - 4
            spacing: 2
            Icon {
                Layout.alignment: Qt.AlignHCenter
                path: item.iconPath
                color: item.active ? Theme.accentInk : Theme.inkMuted
            }
            AppText {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: col.width
                horizontalAlignment: Text.AlignHCenter
                text: item.shortText
                oneLine: true
                elide: Text.ElideRight   // ตัวอักษรใหญ่มาก → ตัดท้าย ชื่อเต็มยังอยู่ใน tooltip
                size: Theme.fontCaption
                strong: item.active
                color: item.active ? Theme.accentInk : Theme.inkMuted
            }
        }
    }
}
