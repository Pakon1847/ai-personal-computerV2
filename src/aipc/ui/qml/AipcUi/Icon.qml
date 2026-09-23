// วาดไอคอนจาก SVG path ใน Icons.qml · สีตามตัวอักษรรอบข้างได้ด้วย property color
import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property string path: ""
    property color color: Theme.ink
    property real stroke: 1.8
    property bool filled: false
    implicitWidth: 20
    implicitHeight: 20
    // วาดลง texture ก่อน: ตัวเรนเดอร์แบบ CPU ไม่ตัด Shape ตาม clip ของ ListView ทำให้ไอคอนหลุดกรอบ
    layer.enabled: true
    layer.smooth: true

    Shape {
        width: 24
        height: 24
        // path ออกแบบไว้บนตาราง 24×24 แล้วย่อ/ขยายให้พอดีกับขนาดจริง
        transform: Scale { xScale: root.width / 24; yScale: root.height / 24 }
        ShapePath {
            strokeColor: root.filled ? "transparent" : root.color
            strokeWidth: root.stroke
            fillColor: root.filled ? root.color : "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.path }
        }
    }
}
