// โลโก้ + ชื่อระบบ มุมซ้ายบนของหน้าที่ไม่มีแถบนำทาง
import QtQuick
import QtQuick.Layouts

RowLayout {
    property string title: "AI PC"
    spacing: 10
    Rectangle {
        width: 32; height: 32; radius: 8
        color: Theme.accentFill
        AppText { anchors.centerIn: parent; text: "AI"; strong: true; size: Theme.px(14); color: Theme.textOnAccent; oneLine: true }
    }
    AppText { text: parent.title; strong: true; size: Theme.px(18); oneLine: true }
}
