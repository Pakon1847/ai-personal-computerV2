// "ใบหน้าของฉัน" ในหน้าตั้งค่า (การ์ด 0006) · ลงทะเบียน · ทดลองสแกน · ลบ
// ทุกการตัดสินอยู่ใน Python (face = FaceController) · หน้านี้แสดงสถานะและส่งคำสั่งเท่านั้น (H7)
// ไม่มีภาพจากกล้องบนจอ (การ์ด 0006 ข้อ 3) · ขอความยินยอมก่อนเปิดกล้องทุกครั้งที่ลงทะเบียน
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Card {
    id: root
    objectName: "facePanel"
    radius: Theme.radiusCard
    implicitHeight: col.implicitHeight + 40

    readonly property var poseNames: ({ front: "หน้าตรง", left: "หันซ้าย", right: "หันขวา" })
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
                Layout.fillWidth: true
                spacing: 8
                visible: Object.keys(face.poses).length === 3
                Repeater {
                    model: ["front", "left", "right"]
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
