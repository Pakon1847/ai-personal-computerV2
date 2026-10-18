// "เข้าเครื่องด้วยใบหน้า" ในหน้าตั้งค่า (การ์ด 0015 ข้อ 2 = ก. เจ้าของบัญชีเลือกเปิดเอง)
// เปิด = ยินยอม + รหัสผ่าน → visiond สแกน 5 ท่า · ปิด = รหัสผ่าน → ลบข้อมูลใบหน้าของหน้า Login
// ตัดสินทุกอย่างใน visiond + ตัวช่วย root · หน้านี้ส่งคำสั่งและแสดงผลเท่านั้น (H7)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Card {
    id: root
    objectName: "loginFacePanel"
    radius: Theme.radiusCard
    implicitHeight: col.implicitHeight + 40
    readonly property bool on: loginFace.state === "enabled"

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
            Icon { path: Icons.shield; color: Theme.accent; Layout.alignment: Qt.AlignTop }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                AppText { text: Tr.both("เข้าเครื่องด้วยใบหน้า"); strong: true }
                AppText {
                    objectName: "loginFaceStatus"
                    Layout.fillWidth: true
                    size: Theme.fontSmall
                    color: Theme.inkMuted
                    text: loginFace.state === "enabled" ? Tr.both("เปิดอยู่ · ที่หน้า Login แค่มองกล้องก็เข้าได้")
                        : loginFace.state === "disabled" ? Tr.both("ปิดอยู่ · เข้าเครื่องด้วยรหัสผ่าน")
                        : Tr.both("ระบบใบหน้าของหน้า Login ยังไม่ได้ติดตั้งในเครื่องนี้")
                }
            }
            Chip {
                visible: loginFace.state !== "unavailable"
                text: root.on ? Tr.both("เปิด") : Tr.both("ปิด")
                kind: root.on ? "ok" : "neutral"
            }
        }

        // ภาพสดระหว่างสแกน (เห็นหน้าตัวเอง · Pakon ขอ 2026-09-30)
        EnrollPreview {
            objectName: "loginFaceEnrollPreview"
            visible: loginFace.busy && loginFace.state === "disabled"
            Layout.fillWidth: true
            Layout.maximumWidth: 640
            Layout.alignment: Qt.AlignHCenter
            view: loginFaceEnroll
            provider: "loginface"
            running: loginFace.busy
        }

        AppCheck {
            id: consentBox
            objectName: "loginFaceConsent"
            visible: loginFace.state === "disabled"
            Layout.fillWidth: true
            text: Tr.both("ยินยอมให้เก็บข้อมูลใบหน้าสำหรับหน้า Login")
            detail: Tr.both("ตัวเลข 128 ค่าในเครื่องนี้ ไม่เก็บรูป · รูปถ่ายหรือคนหน้าคล้ายอาจเข้าได้ถ้าระบบกันรูปปลอมพลาด · งานสำคัญยังต้องใช้รหัสผ่าน")
        }

        RowLayout {
            visible: loginFace.state !== "unavailable"
            spacing: 8
            AppField {
                id: pw
                objectName: "loginFacePassword"
                Layout.preferredWidth: 260
                placeholder: Tr.both("รหัสผ่านของคุณ"); password: true
                enabled: !loginFace.busy
            }
            AppButton {
                objectName: "loginFaceToggle"
                text: root.on ? Tr.both("ปิดเข้าด้วยใบหน้า") : Tr.both("เปิดและสแกนใบหน้า")
                kind: root.on ? "secondary" : "primary"
                enabled: !loginFace.busy && pw.text !== "" && (root.on || consentBox.checked)
                onClicked: {
                    if (root.on) loginFace.disable(pw.text)
                    else loginFace.enable(pw.text)
                    pw.text = ""   // ไม่ถือรหัสผ่านค้างในช่อง
                }
            }
        }

        AppText {
            objectName: "loginFaceMessage"
            visible: loginFace.message !== "" || loginFace.busy
            Layout.fillWidth: true
            text: loginFace.busy && loginFace.message === "" ? Tr.both("กำลังทำงาน… ถ้าสแกน ให้มองกล้องแล้วค่อย ๆ หันซ้าย ขวา เงย ก้ม") : loginFace.message
            color: Theme.inkMuted
        }
    }
}
