// "ใบหน้าของฉัน" ในหน้าตั้งค่า (การ์ด 0006, 0010) · ลงทะเบียน · ทดลองสแกน · ลบ
// ทุกการตัดสินอยู่ใน Python (face = FaceController) · หน้านี้แสดงสถานะและส่งคำสั่งเท่านั้น (H7)
// ภาพสดเฉพาะตอนลงทะเบียน (การ์ด 0010) · ภาพมาจาก Python ทาง image://face · ไม่มีการบันทึกภาพ
// ขอความยินยอมก่อนเปิดกล้องทุกครั้งที่ลงทะเบียน
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes

Card {
    id: root
    objectName: "facePanel"
    radius: Theme.radiusCard
    implicitHeight: col.implicitHeight + 40

    readonly property var poseNames: ({ front: "ตรง", left: "ซ้าย", right: "ขวา", up: "เงย", down: "ก้ม" })
    readonly property var poseOrder: ["front", "left", "right", "up", "down"]
    // ลูกศรบอกทิศบนภาพกระจก: หันซ้ายของผู้ใช้ = ซ้ายของจอ
    readonly property var poseArrow: ({ front: 0, left: 0, right: 180, up: 90, down: -90 })
    readonly property bool enrolling: face.busy && face.currentPose !== ""
    readonly property string statusText: ({
        none: "ยังไม่ได้ลงทะเบียน",
        enrolled: "ลงทะเบียนแล้ว · " + face.enrolledAt.slice(0, 16).replace("T", " ") + " · ความยินยอม " + face.consentVersion,
        broken: face.problem,
        unavailable: face.problem !== "" ? face.problem : "ยังใช้ไม่ได้ในเครื่องนี้"
    })[face.state] || ""

    ColumnLayout {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Icon { path: Icons.camera; color: Theme.accent; Layout.alignment: Qt.AlignTop }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                AppText { text: "ใบหน้าของฉัน"; strong: true }
                AppText {
                    objectName: "faceStatus"
                    Layout.fillWidth: true
                    text: root.statusText
                    size: Theme.fontSmall
                    color: face.state === "broken" ? Theme.warnInk : Theme.inkMuted
                }
            }
        }

        AppText {
            Layout.fillWidth: true
            size: Theme.fontSmall
            color: Theme.inkMuted
            // แม่แบบตรงนี้อยู่ใน home ของคุณ ใช้ทดลองสแกน · เข้าเครื่องด้วยใบหน้าแยกไปที่ LoginFacePanel (การ์ด 0015)
            text: "ลงทะเบียนและทดลองสแกนได้ในหน้านี้ · เข้าเครื่องด้วยใบหน้าตั้งค่าที่ส่วนถัดไป · "
                + "เก็บแค่ตัวเลข 128 ค่า ไม่เก็บภาพ · รหัสผ่านยังเป็นกุญแจเสมอ"
        }

        // ---------- ระหว่างลงทะเบียน: ภาพสด (กระจก) · นอกวงรีมืดลง · ลูกศรอยู่นอกวงรี ไม่บังหน้า ----------
        Rectangle {
            id: preview
            objectName: "facePreview"
            visible: root.enrolling
            Layout.fillWidth: true
            Layout.maximumWidth: 640
            Layout.preferredHeight: width * 9 / 16
            Layout.alignment: Qt.AlignHCenter
            radius: Theme.radiusCard
            color: Theme.camera
            clip: true

            // วงรีคำนวณจากภาพที่วาดจริง (ภาพอาจไม่เต็มกรอบถ้ากล้องไม่ใช่ 16:9)
            readonly property real cx: width / 2
            readonly property real cy: height / 2
            readonly property real rx: live.paintedHeight * 0.28
            readonly property real ry: live.paintedHeight * 0.36
            readonly property bool seen: face.faceBox.length === 4
            readonly property string pose: face.currentPose

            Image {
                id: live
                anchors.fill: parent
                fillMode: Image.PreserveAspectFit
                cache: false
                asynchronous: false
                // เลข serial เปลี่ยน = ขอภาพใหม่ · 0 = ยังไม่มีภาพ (ไม่ขอเลย)
                source: face.previewSerial > 0 ? "image://face/" + face.previewSerial : ""
            }
            AppText {
                anchors.centerIn: parent
                visible: face.previewSerial === 0
                text: "กำลังเปิดกล้อง…"
                color: Theme.cameraText
            }
            // ม่านมืดนอกวงรี + เส้นวงรี · สีเขียว = ระบบเห็นหน้าแล้ว (ไม่มีกรอบทับหน้า)
            Shape {
                anchors.fill: parent
                layer.enabled: true  // วาดลง texture ก่อน ไม่หลุดกรอบเมื่อวาดด้วย CPU (เหมือน Icon)
                ShapePath {
                    fillRule: ShapePath.OddEvenFill  // สี่เหลี่ยมลบวงรี = ทึบเฉพาะนอกวงรี
                    fillColor: "#8C000000"
                    strokeColor: "transparent"
                    PathRectangle { x: 0; y: 0; width: preview.width; height: preview.height }
                    PathAngleArc {
                        moveToStart: true
                        centerX: preview.cx; centerY: preview.cy
                        radiusX: preview.rx; radiusY: preview.ry
                        startAngle: 0; sweepAngle: 360
                    }
                }
                ShapePath {
                    strokeWidth: 4
                    strokeColor: preview.seen ? Theme.scanFound : "#E6FFFFFF"
                    fillColor: "transparent"
                    PathAngleArc {
                        centerX: preview.cx; centerY: preview.cy
                        radiusX: preview.rx; radiusY: preview.ry
                        startAngle: 0; sweepAngle: 360
                    }
                }
            }
            // ลูกศรท่าถัดไป: อยู่ในส่วนมืดนอกวงรีเสมอ · กะพริบเบา ๆ ให้สังเกตง่าย
            Icon {
                id: cue
                objectName: "facePoseCue"
                visible: preview.pose !== "" && preview.pose !== "front"
                width: 48; height: 48
                path: Icons.back
                color: "#FFFFFF"
                rotation: root.poseArrow[preview.pose] || 0
                readonly property real gap: 18
                x: preview.pose === "left" ? preview.cx - preview.rx - gap - width
                 : preview.pose === "right" ? preview.cx + preview.rx + gap
                 : preview.cx - width / 2
                y: preview.pose === "up" ? Math.max(4, preview.cy - preview.ry - gap - height)
                 : preview.pose === "down" ? Math.min(preview.height - height - 4, preview.cy + preview.ry + gap)
                 : preview.cy - height / 2
                SequentialAnimation on opacity {
                    running: cue.visible
                    loops: Animation.Infinite
                    NumberAnimation { from: 1; to: 0.5; duration: 700 }
                    NumberAnimation { from: 0.5; to: 1; duration: 700 }
                }
            }
            // ขั้นตอน "ท่า n/5" มุมซ้ายบน (อยู่ในส่วนมืด)
            Rectangle {
                anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 10
                radius: height / 2
                color: "#99000000"
                width: step.implicitWidth + 20; height: step.implicitHeight + 8
                AppText {
                    id: step
                    anchors.centerIn: parent
                    color: "#FFFFFF"
                    size: Theme.fontSmall
                    text: "ท่า " + (root.poseOrder.indexOf(preview.pose) + 1) + "/5 · " + (root.poseNames[preview.pose] || "")
                }
            }
        }

        // แถบบอกว่าหัน/ก้มถึงหรือยัง (เต็ม = นับท่านี้ได้แล้ว) · ช่วยท่าก้มที่ผู้ใช้ไม่รู้ต้องก้มแค่ไหน
        Rectangle {
            objectName: "faceReach"
            visible: root.enrolling && face.currentPose !== "front"
            Layout.fillWidth: true
            Layout.maximumWidth: 640
            Layout.alignment: Qt.AlignHCenter
            implicitHeight: 8
            radius: 4
            color: Theme.surface2
            Rectangle {
                width: parent.width * face.reach
                height: parent.height
                radius: 4
                color: face.reach >= 1 ? Theme.ok : Theme.accent
                Behavior on width { NumberAnimation { duration: 120 } }
            }
        }

        // ---------- ระหว่างทำงาน: คำแนะนำสด + ท่าที่ได้แล้ว ----------
        ColumnLayout {
            visible: face.busy
            Layout.fillWidth: true
            spacing: 8
            AppText {
                objectName: "faceAdvice"
                Layout.fillWidth: true
                horizontalAlignment: root.enrolling ? Text.AlignHCenter : Text.AlignLeft
                text: face.advice
                size: Theme.fontHeading
                strong: true
                color: Theme.accentInk
            }
            Flow {
                objectName: "facePoses"
                Layout.alignment: Qt.AlignHCenter
                spacing: 8
                visible: root.enrolling
                Repeater {
                    model: root.poseOrder
                    Chip {
                        required property string modelData
                        readonly property int got: face.poses[modelData] || 0
                        text: root.poseNames[modelData] + (got >= 2 ? " ✓" : "")
                        // เสร็จ = เขียว · ท่าที่กำลังทำ = คราม · ที่เหลือ = เทา
                        kind: got >= 2 ? "ok" : modelData === face.currentPose ? "accent" : "neutral"
                    }
                }
            }
            AppButton {
                text: "ยกเลิก"; kind: "secondary"; onClicked: face.cancel()
                Layout.alignment: root.enrolling ? Qt.AlignHCenter : Qt.AlignLeft
            }
        }

        // ---------- ปุ่ม ----------
        Flow {
            visible: !face.busy
            Layout.fillWidth: true
            spacing: 8
            AppButton {
                objectName: "faceEnrollButton"
                text: face.state === "enrolled" ? "ลงทะเบียนใหม่" : "ลงทะเบียนใบหน้า"
                enabled: face.state !== "unavailable"
                onClicked: consent.open()
            }
            AppButton {
                text: "ทดลองสแกน"; kind: "secondary"
                enabled: face.state === "enrolled"
                onClicked: face.tryScan()
            }
            AppButton {
                text: "ลบใบหน้า"; kind: "secondary"; iconPath: Icons.trash
                enabled: face.state === "enrolled" || face.state === "broken"
                onClicked: confirmDelete.open()
            }
        }

        AppText {
            objectName: "faceMessage"
            visible: face.message !== "" && !face.busy
            Layout.fillWidth: true
            text: face.message
        }
    }

    // ---------- ขอความยินยอม (ก่อนเปิดกล้องทุกครั้ง) ----------
    Popup {
        id: consent
        objectName: "faceConsent"
        modal: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(560, (root.Window.window ? root.Window.window.width : 560) - 48)
        padding: 24
        background: Rectangle { radius: Theme.radiusCard; color: Theme.surface; border.width: 1; border.color: Theme.line }
        contentItem: ColumnLayout {
            spacing: 14
            AppText { Layout.fillWidth: true; text: face.consentText }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                AppButton { text: "ไม่ยินยอม"; kind: "secondary"; onClicked: { consent.close(); face.startEnroll(false) } }
                AppButton {
                    text: "ยินยอม · เริ่มลงทะเบียน"
                    onClicked: { consent.close(); face.startEnroll(true) }
                }
            }
        }
    }

    Popup {
        id: confirmDelete
        modal: true
        anchors.centerIn: Overlay.overlay
        padding: 24
        background: Rectangle { radius: Theme.radiusCard; color: Theme.surface; border.width: 1; border.color: Theme.line }
        contentItem: ColumnLayout {
            spacing: 14
            AppText { text: "ลบแม่แบบใบหน้า? · ใช้ใบหน้าไม่ได้ทันที · เข้าเครื่องด้วยรหัสผ่านได้ตามปกติ" }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                AppButton { text: "ไม่ลบ"; kind: "secondary"; onClicked: confirmDelete.close() }
                AppButton { text: "ลบ"; onClicked: { confirmDelete.close(); face.deleteTemplate() } }
            }
        }
    }
}
