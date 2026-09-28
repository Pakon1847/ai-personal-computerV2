// ลืมรหัสผ่าน: ใช้รหัสกู้คืนตั้งรหัสผ่านใหม่ที่หน้า Login (การ์ด 0012)
// ตัวช่วย root เทียบ hash ของรหัสกู้คืน · ผิดหลายครั้งต้องรอ · ใช้แล้วออกรหัสใหม่ให้ (อันเก่าใช้ไม่ได้ทันที)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import AipcUi

Rectangle {
    id: root
    color: Theme.bg
    property string newCode: ""
    property bool simulated: false
    readonly property var pwCheck: signup.checkPassword(pw1.text, pw2.text)
    readonly property bool formValid: userField.text.trim() !== "" && codeField.text.trim() !== "" && pwCheck.ok

    Connections {
        target: signup
        function onFinished(r) {
            codeField.text = ""
            if (r.ok) {
                root.newCode = r.recovery_code
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
            visible: root.newCode === ""
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 14
                AppText { text: "ตั้งรหัสผ่านใหม่ด้วยรหัสกู้คืน"; size: Theme.fontTitle; strong: true }
                AppText { text: "รหัสกู้คืนคือรหัส 24 ตัวที่ได้ตอนสมัคร · พิมพ์ตัวเล็กหรือใหญ่ มีขีดหรือไม่มีก็ได้"
                          color: Theme.inkMuted; Layout.fillWidth: true }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 12
                    AppField { id: userField; objectName: "recoverUser"; Layout.fillWidth: true; label: "ชื่อผู้ใช้"; mono: true }
                    AppField { id: codeField; objectName: "recoverCode"; Layout.fillWidth: true; label: "รหัสกู้คืน"; mono: true
                               placeholder: "XXXX-XXXX-XXXX-XXXX-XXXX-XXXX" }
                    AppField { id: pw1; Layout.fillWidth: true; label: "รหัสผ่านใหม่"; password: true; emphasis: true }
                    AppField {
                        id: pw2
                        Layout.fillWidth: true
                        label: "ยืนยันรหัสผ่านใหม่"; password: true
                        hint: pw2.text === "" ? "" : root.pwCheck.message
                        hintKind: root.pwCheck.ok ? "ok" : "error"
                    }
                }
                AppText { id: msg; objectName: "recoverMsg"; visible: text !== ""; color: Theme.danger; Layout.fillWidth: true }
                AppText { visible: signup.busy; text: "กำลังตรวจรหัสกู้คืน…"; color: Theme.inkMuted }
                Item { Layout.fillHeight: true }
                AppButton {
                    Layout.alignment: Qt.AlignRight
                    text: "ตั้งรหัสผ่านใหม่"
                    enabled: root.formValid && !signup.busy
                    onClicked: signup.recover(userField.text, codeField.text, pw1.text)
                }
            }
        }

        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.newCode !== ""
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 18
                AppText { text: root.simulated ? "ตั้งรหัสผ่านใหม่แล้ว (จำลอง)" : "ตั้งรหัสผ่านใหม่แล้ว"; size: Theme.fontTitle; strong: true }
                AppText { text: "รหัสกู้คืนเดิมใช้ไม่ได้แล้ว · จดรหัสกู้คืนชุดใหม่นี้ไว้ แสดงครั้งเดียว"; Layout.fillWidth: true }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 88
                    radius: Theme.radiusCard
                    color: Theme.surface2
                    border.width: 1
                    border.color: Theme.lineStrong
                    Text {
                        anchors.centerIn: parent
                        text: root.newCode
                        font.family: Theme.mono
                        font.pixelSize: Theme.px(28)
                        font.letterSpacing: 2
                        color: Theme.ink
                        Accessible.name: "รหัสกู้คืนใหม่"
                    }
                }
                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Item { Layout.fillWidth: true }
                    AppCheck { id: wroteDown; text: "ฉันจดไว้แล้ว" }
                    AppButton { text: "ไปหน้า Login"; enabled: wroteDown.checked; onClicked: AppState.go("login") }
                }
            }
        }
    }
}
