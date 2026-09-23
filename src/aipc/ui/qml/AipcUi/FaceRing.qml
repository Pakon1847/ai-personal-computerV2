// กรอบวงรีสำหรับวางหน้า · วาดด้วย Shape เพราะ Rectangle ทำได้แค่มุมโค้ง ไม่ใช่วงรีจริง
import QtQuick
import QtQuick.Shapes

Shape {
    id: root
    property color color: Theme.cameraText
    property bool dashed: false
    width: 220
    height: 290
    ShapePath {
        strokeColor: root.color
        strokeWidth: 4
        fillColor: "transparent"
        strokeStyle: root.dashed ? ShapePath.DashLine : ShapePath.SolidLine
        dashPattern: [3, 2]
        startX: 2
        startY: root.height / 2
        PathArc { x: root.width - 2; y: root.height / 2; radiusX: root.width / 2 - 2; radiusY: root.height / 2 - 2 }
        PathArc { x: 2; y: root.height / 2; radiusX: root.width / 2 - 2; radiusY: root.height / 2 - 2 }
    }
}
