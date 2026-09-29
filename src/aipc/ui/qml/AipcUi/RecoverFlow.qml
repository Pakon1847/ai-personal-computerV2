// ลืมรหัสผ่าน: ใช้ PIN ที่ตั้งตอนสมัครตั้งรหัสผ่านใหม่ที่หน้า Login (การ์ด 0012 หัวข้อ 11)
// ตัวช่วย root เทียบ hash ของ PIN · ผิดหลายครั้งต้องรอนานขึ้นเรื่อย ๆ · สำเร็จแล้ว PIN เดิมใช้ต่อได้
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import AipcUi

Rectangle {
    id: root
    color: Theme.bg
    property bool done: false
    property bool simulated: false
    readonly property var pwCheck: signup.checkPassword(pw1.text, pw2.text)
    readonly property bool formValid: userField.text.trim() !== "" && pinField.text.trim() !== "" && pwCheck.ok

    Connections {
        target: signup
        function onFinished(r) {
            pinField.text = ""
            if (r.ok) {
                root.done = true
                root.simulated = r.simulated === true
                msg.text = ""
            } else {
                msg.text = r.message
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 56
        anchors.rightMargin: 56
        anchors.topMargin: 20
        anchors.bottomMargin: 20
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            BrandMark { title: "ลืมรหัสผ่าน" }
            Item { Layout.fillWidth: true }
            AppButton { text: "กลับหน้า Login"; kind: "ghost"; enabled: !signup.busy; onClicked: AppState.go("login") }
        }

        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.done
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 14
                AppText { text: "ตั้งรหัสผ่านใหม่ด้วย PIN"; size: Theme.fontTitle; strong: true }
                AppText { text: "PIN คือตัวเลข 6–12 หลักที่ตั้งไว้ตอนสมัคร · ใส่ผิดหลายครั้งต้องรอนานขึ้นเรื่อย ๆ"
                          color: Theme.inkMuted; Layout.fillWidth: true }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 12
                    AppField { id: userField; objectName: "recoverUser"; Layout.fillWidth: true; label: "ชื่อผู้ใช้"; mono: true }
                    AppField { id: pinField; objectName: "recoverPin"; Layout.fillWidth: true; label: "PIN"; mono: true; password: true
                               field.inputMethodHints: Qt.ImhDigitsOnly; field.maximumLength: 12 }
                    AppField { id: pw1; objectName: "recoverPw1"; Layout.fillWidth: true; label: "รหัสผ่านใหม่"; password: true; emphasis: true }
                    AppField {
                        id: pw2
                        Layout.fillWidth: true
                        label: "ยืนยันรหัสผ่านใหม่"; password: true
                        hint: pw2.text === "" ? "" : root.pwCheck.message
                        hintKind: root.pwCheck.ok ? "ok" : "error"
                    }
                }
                AppText { id: msg; objectName: "recoverMsg"; visible: text !== ""; color: Theme.danger; Layout.fillWidth: true }
                AppText { visible: signup.busy; text: "กำลังตรวจ PIN…"; color: Theme.inkMuted }
                Item { Layout.fillHeight: true }
                AppButton {
                    Layout.alignment: Qt.AlignRight
                    text: "ตั้งรหัสผ่านใหม่"
                    enabled: root.formValid && !signup.busy
                    onClicked: signup.recover(userField.text, pinField.text, pw1.text)
                }
            }
        }

        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.done
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 18
                AppText { text: root.simulated ? "ตั้งรหัสผ่านใหม่แล้ว (จำลอง)" : "ตั้งรหัสผ่านใหม่แล้ว"; size: Theme.fontTitle; strong: true }
                AppText { text: "เข้าสู่ระบบด้วยรหัสผ่านใหม่ได้เลย · PIN เดิมยังใช้กู้คืนครั้งต่อไปได้"; Layout.fillWidth: true }
                Item { Layout.fillHeight: true }
                AppButton { Layout.alignment: Qt.AlignRight; text: "ไปหน้า Login"; onClicked: AppState.go("login") }
            }
        }
    }
}
