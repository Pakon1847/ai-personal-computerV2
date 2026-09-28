// แถบขั้นตอนสมัครบัญชี 3 ขั้น (การ์ด 0012) · step = ขั้นปัจจุบัน (1–3)
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property int step: 1
    readonly property var labels: ["บัญชีและรหัสผ่าน", "รหัสกู้คืน", "พร้อมใช้"]
    implicitHeight: 52
    radius: Theme.radiusCard
    color: Theme.surface
    border.width: 1
    border.color: Theme.line

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        spacing: 12
        Repeater {
            model: root.labels
            RowLayout {
                required property int index
                required property string modelData
                readonly property int n: index + 1
                readonly property bool done: n < root.step
                readonly property bool current: n === root.step
                Layout.fillWidth: true
                spacing: 8
                Rectangle {
                    width: 26; height: 26; radius: 13
                    color: parent.current ? Theme.accentFill : parent.done ? Theme.okSoft : Theme.surface
                    border.width: 1
                    border.color: parent.current ? Theme.accentFill : parent.done ? Theme.okSoft : Theme.lineStrong
                    Icon { anchors.centerIn: parent; visible: parent.parent.done; path: Icons.check; color: Theme.okInk; width: 14; height: 14; stroke: 2.6 }
                    AppText {
                        anchors.centerIn: parent
                        visible: !parent.parent.done
                        text: parent.parent.n
                        size: Theme.fontCaption
                        oneLine: true
                        color: parent.parent.current ? Theme.textOnAccent : Theme.inkMuted
                    }
                }
                AppText {
                    text: parent.modelData
                    size: Theme.px(15)
                    oneLine: true
                    strong: parent.current
                    color: parent.current ? Theme.ink : parent.done ? Theme.okInk : Theme.inkMuted
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }
        }
    }
}
