// รูปโปรไฟล์แบบตัวอักษรแรกของชื่อ (ยังไม่มีระบบรูปโปรไฟล์)
import QtQuick

Rectangle {
    property string name: ""
    property int size: 48
    width: size
    height: size
    radius: size / 2
    color: Theme.accentFill
    AppText {
        anchors.centerIn: parent
        text: parent.name.length > 0 ? parent.name.charAt(0).toUpperCase() : "?"
        size: Math.round(parent.size * 0.42)
        strong: true
        color: Theme.textOnAccent
        oneLine: true
    }
}
