// ช่องติ๊ก หรือปุ่มเลือกข้อเดียว (radio: true) พร้อมข้อความและคำอธิบาย
// วาด indicator เองให้ตรงระบบดีไซน์ และวางตำแหน่งเองทั้งหมด
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

AbstractButton {
    id: c
    property bool radio: false
    property string detail: ""
    property bool boxed: false          // true = มีกรอบรอบทั้งตัวเลือก (แบบการ์ด)
    checkable: true
    padding: boxed ? 14 : 4
    implicitWidth: row.implicitWidth + leftPadding + rightPadding
    implicitHeight: Math.max(Theme.touch, row.implicitHeight + topPadding + bottomPadding)
    Accessible.role: radio ? Accessible.RadioButton : Accessible.CheckBox
    Accessible.name: text

    background: Rectangle {
        visible: c.boxed
        radius: Theme.radiusCard
        color: Theme.surface
        border.width: c.checked ? 2 : 1
        border.color: c.checked ? Theme.accent : Theme.line
    }

    contentItem: RowLayout {
        id: row
        spacing: 12
        Rectangle {
            Layout.alignment: c.detail !== "" ? Qt.AlignTop : Qt.AlignVCenter
            Layout.topMargin: c.detail !== "" ? 2 : 0
            width: 22; height: 22
            radius: c.radio ? 11 : 6
            color: c.checked && !c.radio ? Theme.accentFill : Theme.surface
            border.width: 2
            border.color: c.checked ? Theme.accent : Theme.lineStrong
            Rectangle { visible: c.radio && c.checked; anchors.centerIn: parent; width: 10; height: 10; radius: 5; color: Theme.accent }
            Icon { visible: !c.radio && c.checked; anchors.centerIn: parent; path: Icons.check; color: Theme.textOnAccent; width: 16; height: 16; stroke: 2.6 }
            Rectangle {
                anchors.fill: parent; anchors.margins: -4; radius: parent.radius + 4
                color: "transparent"; border.width: 2; border.color: Theme.accent; visible: c.visualFocus
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            AppText { text: c.text; strong: c.detail !== ""; Layout.fillWidth: true }
            AppText { visible: c.detail !== ""; text: c.detail; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
        }
    }
}
