// ภาพสดตอนลงทะเบียนใบหน้าผ่าน visiond (หน้าสมัคร · สวิตช์เข้าเครื่องด้วยใบหน้า) · Pakon ขอ 2026-09-30
// หน้าตาเดียวกับหน้าตั้งค่า (การ์ด 0010): ภาพกระจก · นอกวงรีมืดลง · วงรีเขียวเมื่อเห็นหน้า · ลูกศรท่าถัดไป · ท่า n/5
// ยังไม่เริ่ม = วงรีเส้นประบนพื้นมืด + บอกว่ากล้องจะเปิดเมื่อกดเริ่ม · สำเร็จ = เครื่องหมายถูกกลางวงรี
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes

ColumnLayout {
    id: root
    property var view                  // EnrollView จาก Python (signupEnroll / loginFaceEnroll)
    property string provider: ""       // ชื่อ image provider (signupface / loginface)
    property bool running: false       // กำลังลงทะเบียน (กล้องเปิดอยู่)
    property bool done: false          // ลงทะเบียนสำเร็จแล้ว
    spacing: 10

    readonly property var poseNames: ({ front: Tr.t("ตรง"), left: Tr.t("ซ้าย"), right: Tr.t("ขวา"), up: Tr.t("เงย"), down: Tr.t("ก้ม") })
    readonly property var poseOrder: ["front", "left", "right", "up", "down"]
    readonly property var poseArrow: ({ front: 0, left: 0, right: 180, up: 90, down: -90 })
    readonly property bool live: running && view.previewSerial > 0

    Rectangle {
        id: stage
        objectName: "enrollStage"
        Layout.fillWidth: true
        Layout.preferredHeight: width * 9 / 16
        radius: Theme.radiusLarge
        color: Theme.camera
        clip: true

        readonly property real cx: width / 2
        readonly property real cy: height / 2
        readonly property real ry: height * 0.36
        readonly property real rx: height * 0.28
        readonly property bool seen: root.view.faceBox.length === 4
        readonly property string pose: root.running ? root.view.currentPose : ""

        Image {
            id: img
            anchors.fill: parent
            visible: root.live
            fillMode: Image.PreserveAspectFit
            cache: false
            source: root.live ? "image://" + root.provider + "/" + root.view.previewSerial : ""
        }

        // นอกวงรีมืดลง (เฉพาะตอนมีภาพ) + เส้นวงรี
        Shape {
            anchors.fill: parent
            layer.enabled: true
            ShapePath {
                fillRule: ShapePath.OddEvenFill
                fillColor: root.live ? "#8C000000" : "transparent"
                strokeColor: "transparent"
                PathRectangle { x: 0; y: 0; width: stage.width; height: stage.height }
                PathAngleArc { moveToStart: true; centerX: stage.cx; centerY: stage.cy; radiusX: stage.rx; radiusY: stage.ry; startAngle: 0; sweepAngle: 360 }
            }
            ShapePath {
                strokeWidth: 4
                strokeStyle: root.live || root.done ? ShapePath.SolidLine : ShapePath.DashLine
                dashPattern: [3, 2]
                strokeColor: root.done || (root.live && stage.seen) ? Theme.scanFound : "#B3FFFFFF"
                fillColor: "transparent"
                PathAngleArc { centerX: stage.cx; centerY: stage.cy; radiusX: stage.rx; radiusY: stage.ry; startAngle: 0; sweepAngle: 360 }
            }
        }

        // ยังไม่เริ่ม / กำลังเปิดกล้อง / สำเร็จ · ไอคอนกลางวงรี ข้อความชิดล่าง (ไม่ทับเส้นวงรี)
        Icon {
            anchors.centerIn: parent
            visible: !root.live
            path: root.done ? Icons.check : Icons.camera
            color: root.done ? Theme.scanFound : Theme.cameraText
            width: root.done ? 56 : 40; height: width; stroke: root.done ? 2.6 : 1.8
        }
        Rectangle {
            visible: !root.live
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 12
            radius: height / 2
            color: "#99000000"
            width: placeholder.implicitWidth + 28; height: placeholder.implicitHeight + 10
            AppText {
                id: placeholder
                anchors.centerIn: parent
                color: "#FFFFFF"
                size: Theme.fontSmall
                strong: root.done
                text: root.done ? Tr.t("ลงทะเบียนสำเร็จ")
                    : root.running ? Tr.t("กำลังเปิดกล้อง…")
                    : Tr.t("กล้องจะเปิดเมื่อกด “เริ่มสแกน” · ภาพอยู่บนจอนี้เท่านั้น ไม่ถูกบันทึก")
            }
        }

        // ลูกศรท่าถัดไป (นอกวงรี · กะพริบเบา ๆ)
        Icon {
            id: cue
            objectName: "enrollPoseCue"
            visible: root.live && stage.pose !== "" && stage.pose !== "front"
            width: 48; height: 48
            path: Icons.back
            color: "#FFFFFF"
            rotation: root.poseArrow[stage.pose] || 0
            readonly property real gap: 18
            x: stage.pose === "left" ? stage.cx - stage.rx - gap - width
             : stage.pose === "right" ? stage.cx + stage.rx + gap
             : stage.cx - width / 2
            y: stage.pose === "up" ? Math.max(4, stage.cy - stage.ry - gap - height)
             : stage.pose === "down" ? Math.min(stage.height - height - 4, stage.cy + stage.ry + gap)
             : stage.cy - height / 2
            SequentialAnimation on opacity {
                running: cue.visible
                loops: Animation.Infinite
                NumberAnimation { from: 1; to: 0.5; duration: 700 }
                NumberAnimation { from: 0.5; to: 1; duration: 700 }
            }
        }

        // ท่า n/5 มุมซ้ายบน
        Rectangle {
            visible: root.live && stage.pose !== ""
            anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
            radius: height / 2
            color: "#99000000"
            width: stepText.implicitWidth + 22; height: stepText.implicitHeight + 8
            AppText {
                id: stepText
                anchors.centerIn: parent
                color: "#FFFFFF"
                size: Theme.fontSmall
                text: Tr.t("ท่า ") + (root.poseOrder.indexOf(stage.pose) + 1) + "/5 · " + (root.poseNames[stage.pose] || "")
            }
        }
    }

    // หันถึงหรือยัง (เต็ม = นับท่านี้ได้แล้ว)
    Rectangle {
        objectName: "enrollReach"
        visible: root.live && stage.pose !== "" && stage.pose !== "front"
        Layout.fillWidth: true
        implicitHeight: 8
        radius: 4
        color: Theme.surface2
        Rectangle {
            width: parent.width * root.view.reach
            height: parent.height
            radius: 4
            color: root.view.reach >= 1 ? Theme.ok : Theme.accent
            Behavior on width { NumberAnimation { duration: 120 } }
        }
    }

    // คำแนะนำสด (ตัวใหญ่ อ่านได้ขณะหันหน้า)
    AppText {
        objectName: "enrollAdvice"
        visible: root.running
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignHCenter
        text: root.view.advice !== "" ? root.view.advice : Tr.t("มองตรงมาที่กล้อง")
        size: Theme.fontHeading
        strong: true
        color: Theme.accentInk
    }

    // 5 ท่า · เขียว = ได้แล้ว · คราม = ท่าที่กำลังทำ
    Flow {
        Layout.alignment: Qt.AlignHCenter
        spacing: 8
        Repeater {
            model: root.poseOrder
            Chip {
                required property string modelData
                readonly property int got: root.view.poses[modelData] || 0
                text: root.poseNames[modelData] + (got >= 2 || root.done ? " ✓" : "")
                kind: got >= 2 || root.done ? "ok" : root.running && modelData === stage.pose ? "accent" : "neutral"
            }
        }
    }
}
