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
            text: "ลงทะเบียนและทดลองได้ในเซสชันนี้ · ใช้ใบหน้าที่หน้า Login ยังไม่พร้อม (ต้องมีบริการ visiond) · "
                + "เก็บแค่ตัวเลข 128 ค่า ไม่เก็บภาพ · รหัสผ่านยังเป็นกุญแจเสมอ"
        }

        // ---------- ระหว่างลงทะเบียน: ภาพสด (กระจก) + วงรีนำทาง + กรอบหน้า + ลูกศรท่าถัดไป ----------
        Rectangle {
            id: preview
            objectName: "facePreview"
            visible: root.enrolling
            Layout.fillWidth: true
            Layout.maximumWidth: 480
            Layout.preferredHeight: width * 9 / 16
            Layout.alignment: Qt.AlignHCenter
            radius: Theme.radiusCard
            color: Theme.camera
            clip: true

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
            // วงรีให้เอาหน้าใส่ · เป็นเส้นประกอบเท่านั้น ไม่ได้ใช้ตัดสิน
            Shape {
                anchors.fill: parent
                opacity: 0.85
                layer.enabled: true  // วาดลง texture ก่อน ไม่หลุดกรอบเมื่อวาดด้วย CPU (เหมือน Icon)
                ShapePath {
                    strokeWidth: 3
                    strokeColor: face.faceBox.length === 4 ? Theme.scanLine : Theme.lineStrong
                    fillColor: "transparent"
                    PathAngleArc {
                        centerX: preview.width / 2
                        centerY: preview.height / 2
                        radiusX: live.paintedHeight * 0.3
                        radiusY: live.paintedHeight * 0.4
                        startAngle: 0
                        sweepAngle: 360
                    }
                }
            }
            // กรอบหน้าที่ระบบเห็น (สัดส่วน 0–1 ของภาพที่วาดจริง)
            Rectangle {
                readonly property real ox: (live.width - live.paintedWidth) / 2
                readonly property real oy: (live.height - live.paintedHeight) / 2
                visible: face.faceBox.length === 4
                x: ox + (face.faceBox[0] || 0) * live.paintedWidth
                y: oy + (face.faceBox[1] || 0) * live.paintedHeight
                width: (face.faceBox[2] || 0) * live.paintedWidth
                height: (face.faceBox[3] || 0) * live.paintedHeight
                color: "transparent"
                border.width: 2
                border.color: Theme.scanFound
                radius: 8
            }
            // ลูกศรท่าถัดไป (ท่าตรง = ไม่มีลูกศร)
            Rectangle {
                visible: face.currentPose !== "" && face.currentPose !== "front"
                width: 56; height: 56; radius: 28
                color: Theme.accent
                opacity: 0.9
                anchors.verticalCenter: face.currentPose === "up" || face.currentPose === "down" ? undefined : parent.verticalCenter
                anchors.horizontalCenter: face.currentPose === "up" || face.currentPose === "down" ? parent.horizontalCenter : undefined
                anchors.left: face.currentPose === "left" ? parent.left : undefined
                anchors.right: face.currentPose === "right" ? parent.right : undefined
                anchors.top: face.currentPose === "up" ? parent.top : undefined
                anchors.bottom: face.currentPose === "down" ? parent.bottom : undefined
                anchors.margins: 12
                Icon {
                    anchors.centerIn: parent
                    path: Icons.back
                    color: Theme.textOnAccent
                    rotation: root.poseArrow[face.currentPose] || 0
                }
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
                text: face.advice
                size: Theme.fontHeading
                strong: true
                color: Theme.accentInk
            }
            Flow {
                objectName: "facePoses"
                Layout.fillWidth: true
                spacing: 8
                visible: root.enrolling
                Repeater {
                    model: root.poseOrder
                    Chip {
                        required property string modelData
                        readonly property int got: face.poses[modelData] || 0
                        text: root.poseNames[modelData] + (got >= 2 ? " ✓" : " " + got + "/2")
                        kind: got >= 2 ? "ok" : "neutral"
                    }
                }
            }
            AppButton { text: "ยกเลิก"; kind: "secondary"; onClicked: face.cancel() }
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
