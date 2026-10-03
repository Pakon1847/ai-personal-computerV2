// ลบบัญชีถาวร (ข้อเสนอ 2026-10-03 · สิทธิ์ขอให้ลบตาม PDPA) · ทำที่หน้า Login เท่านั้น (บัญชีต้องไม่ได้เปิดใช้อยู่)
// ตัวช่วย root ตรวจรหัสผ่าน · ลบทุกที่ที่ระบบเก็บข้อมูล · ตรวจซ้ำทีละที่ แล้วตอบใบยืนยันกลับมา (หน้านี้แค่แสดง)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import AipcUi

Rectangle {
    id: root
    color: Theme.bg
    property var result: null
    readonly property bool formValid: userField.text.trim() !== "" && pwField.text !== ""
                                      && confirmField.text.trim() === userField.text.trim() && understood.checked

    Connections {
        target: signup
        function onFinished(r) {
            pwField.text = ""
            if (r.checks !== undefined) {
                root.result = r
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
            BrandMark { title: "ลบบัญชี" }
            Item { Layout.fillWidth: true }
            AppButton { text: "กลับหน้า Login"; kind: "ghost"; enabled: !signup.busy; onClicked: AppState.go("login") }
        }

        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.result === null
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 14
                AppText { text: "ลบบัญชีและข้อมูลทั้งหมดถาวร"; size: Theme.fontTitle; strong: true }
                AppText {
                    text: "ลบแชท นัด ไฟล์ การตั้งค่า สกิล ใบหน้า PIN และประวัติการส่งข้อมูลออก · กู้คืนไม่ได้ · "
                          + "ต้องออกจากระบบบัญชีนั้นก่อน · บัญชีผู้ดูแลเครื่องลบที่นี่ไม่ได้"
                    color: Theme.inkMuted; Layout.fillWidth: true
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 12
                    AppField { id: userField; objectName: "deleteUser"; Layout.fillWidth: true; label: "ชื่อผู้ใช้"; mono: true }
                    AppField { id: pwField; objectName: "deletePassword"; Layout.fillWidth: true; label: "รหัสผ่าน"; password: true }
                    AppField {
                        id: confirmField
                        objectName: "deleteConfirm"
                        Layout.fillWidth: true
                        Layout.columnSpan: 2
                        label: "พิมพ์ชื่อผู้ใช้อีกครั้งเพื่อยืนยัน"; mono: true
                        hint: confirmField.text === "" || confirmField.text.trim() === userField.text.trim() ? "" : "ไม่ตรงกับชื่อผู้ใช้"
                        hintKind: "error"
                    }
                }
                AppCheck { id: understood; objectName: "deleteUnderstood"; text: "เข้าใจแล้วว่าลบแล้วกู้คืนไม่ได้" }
                AppText { id: msg; objectName: "deleteMsg"; visible: text !== ""; color: Theme.danger; Layout.fillWidth: true }
                AppText { visible: signup.busy; text: "กำลังลบและตรวจทีละที่…"; color: Theme.inkMuted }
                Item { Layout.fillHeight: true }
                AppButton {
                    objectName: "deleteButton"
                    Layout.alignment: Qt.AlignRight
                    text: "ลบบัญชีถาวร"
                    kind: "danger"
                    enabled: root.formValid && !signup.busy
                    onClicked: signup.deleteAccount(userField.text, pwField.text, confirmField.text)
                }
            }
        }

        // ใบยืนยันการลบ: ทุกที่ที่ตรวจ + ข้อจำกัดที่ต้องบอกตรง ๆ
        Card {
            objectName: "deleteCertificate"
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.result !== null
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 32
                spacing: 10
                AppText {
                    text: root.result === null ? ""
                          : root.result.simulated ? "ใบยืนยันการลบ (จำลอง · ไม่ได้ลบจริง)"
                          : root.result.ok ? "ใบยืนยันการลบบัญชี " + root.result.user
                          : "ลบไม่ครบ · ยังเหลือบางที่"
                    size: Theme.fontTitle; strong: true; Layout.fillWidth: true
                }
                AppText {
                    visible: root.result !== null && !!root.result.at
                    text: root.result !== null && root.result.at ? "ลบเมื่อ " + root.result.at + " · ตรวจซ้ำหลังลบทีละที่" : ""
                    color: Theme.inkMuted
                }
                Repeater {
                    model: root.result === null ? [] : root.result.checks
                    RowLayout {
                        required property var modelData
                        objectName: "deleteCheck"
                        Layout.fillWidth: true
                        spacing: 10
                        Chip { text: modelData.gone ? "ลบแล้ว" : "ยังอยู่"; kind: modelData.gone ? "ok" : "danger" }
                        AppText { text: modelData.what; Layout.fillWidth: true }
                    }
                }
                AppText {
                    visible: root.result !== null && (root.result.limits || []).length > 0
                    text: "ข้อจำกัดที่ต้องรู้"; strong: true; Layout.topMargin: 8
                }
                Repeater {
                    model: root.result === null ? [] : (root.result.limits || [])
                    AppText { required property string modelData; text: "· " + modelData; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                }
                Item { Layout.fillHeight: true }
                AppButton { Layout.alignment: Qt.AlignRight; text: "ไปหน้า Login"; onClicked: AppState.go("login") }
            }
        }
    }
}
