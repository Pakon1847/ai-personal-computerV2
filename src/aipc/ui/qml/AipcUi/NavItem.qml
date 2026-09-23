// รายการในแถบนำทางซ้าย · มีไอคอนพร้อมคำกำกับเสมอ (BRIEF 5.7 ข้อ 6)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AbstractButton {
    id: item
    property string iconPath: ""
    property string pageName: ""
    readonly property bool active: AppState.page === pageName
    implicitHeight: Theme.touch
    Layout.fillWidth: true
    onClicked: AppState.page = pageName
    Accessible.role: Accessible.PageTab
    Accessible.name: text

    background: Rectangle {
        radius: Theme.radiusControl
        color: item.active ? Theme.accentSoft : (item.hovered ? Theme.surface2 : "transparent")
        Rectangle {
            anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2
            color: "transparent"; border.width: 2; border.color: Theme.accent; visible: item.visualFocus
        }
    }
    contentItem: RowLayout {
        spacing: 12
        Item { width: 0 }
        Icon { path: item.iconPath; color: item.active ? Theme.accentInk : Theme.ink }
        AppText {
            text: item.text
            oneLine: true
            strong: item.active
            color: item.active ? Theme.accentInk : Theme.ink
            Layout.fillWidth: true
        }
    }
    hoverEnabled: true
}
