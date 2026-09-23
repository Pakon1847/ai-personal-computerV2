// กล่องบอกว่าส่วนนี้ "ยังไม่เชื่อมต่อ" · ใช้แทนการวาดข้อมูลปลอม
// บอกทั้งว่าอะไรยังไม่มี และอยู่เฟสไหนใน ROADMAP เพื่อให้ผู้ใช้/กรรมการรู้ตรง ๆ
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string title: ""
    property string detail: ""
    color: Theme.surface2
    radius: Theme.radiusCard
    border.width: 1
    border.color: Theme.lineStrong
    implicitHeight: col.implicitHeight + 32

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 4
        RowLayout {
            spacing: 8
            Icon { path: Icons.alert; color: Theme.inkMuted; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
            AppText { text: root.title; strong: true; Layout.fillWidth: true }
        }
        AppText { text: root.detail; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true; visible: root.detail !== "" }
    }
}
