// สมัครบัญชีจากหน้า Login (การ์ด 0012 · BRIEF 5.1 ข้อ 3–4)
// ลำดับ: บัญชี+รหัสผ่าน → ตั้ง PIN กู้คืน (กด "สร้างบัญชี" = สร้างจริง) → พร้อมใช้
// PIN แทนรหัสกู้คืนสุ่ม 24 ตัว (Pakon 2026-09-29: จำง่ายกว่า · การ์ด 0012 หัวข้อ 11)
// สมัครเสรี ไม่ต้องมีผู้ดูแลอนุมัติ (Pakon 2026-09-29)
// หน้าจอตรวจฟอร์มเพื่อบอกผู้ใช้เร็ว ๆ เท่านั้น · ตัวช่วย root ตรวจซ้ำทุกข้อก่อนสร้าง (H7)
// ลงทะเบียนใบหน้าอยู่ในหน้าตั้งค่าหลังเข้าครั้งแรก (BRIEF 5.1 ข้อ 6: ต้องยืนยันตัวตนก่อน)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import AipcUi

Rectangle {
    id: root
    color: Theme.bg
    property int page: 0                 // 0 บัญชี 1 PIN กู้คืน 2 เสร็จ
    property bool simulated: false       // หน้าต่างพัฒนา: ผลจำลอง ต้องเขียนว่า "จำลอง" (H5)
    property string loginError: ""

    readonly property var nameCheck: signup.checkDisplayName(nameField.text)
    readonly property var userCheck: signup.checkUsername(userField.text)
    readonly property var pwCheck: signup.checkPassword(pw1.text, pw2.text)
    readonly property int strength: signup.strength(pw1.text)
    readonly property bool accountValid: nameCheck.ok && userCheck.ok && pwCheck.ok
    readonly property var pinCheck: signup.checkPin(pin1.text, pin2.text)

    Component.onCompleted: {
        page = startSignupStep
        if (page >= 2) simulated = true  // ถ่ายภาพ/ทดสอบหน้าจอ
    }

    Connections {
        target: signup
        function onFinished(r) {
            if (r.ok) {
                pin1.text = ""  // ไม่ถือ PIN ค้างไว้หลังสร้างบัญชีแล้ว
                pin2.text = ""
                root.simulated = r.simulated === true
                createMsg.text = ""
                root.page = 2
            } else {
                createMsg.text = r.message
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
            BrandMark { title: "สมัครบัญชี" }
            Item { Layout.fillWidth: true }
            AppButton { text: "ยกเลิก กลับหน้า Login"; kind: "ghost"; visible: root.page < 2; enabled: !signup.busy
                        onClicked: AppState.go("login") }
        }

        SignupSteps { Layout.fillWidth: true; step: root.page + 1 }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // StackLayout คิดความสูงขั้นต่ำจากทุกหน้ารวมกัน จึงบอกว่าขั้นต่ำเป็น 0
            Layout.minimumHeight: 0
            currentIndex: root.page

            // ---------- 1. บัญชีและรหัสผ่าน ----------
            RowLayout {
                spacing: 24
                Card {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 28
                        spacing: 16
                        AppText { text: "ข้อมูลบัญชี"; size: Theme.fontTitle; strong: true }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 16
                            rowSpacing: 12
                            AppField {
                                id: nameField
                                Layout.fillWidth: true
                                label: "ชื่อที่แสดง"
                                hint: text === "" ? "ใช้ทักทายในหน้าจอ" : root.nameCheck.message
                                hintKind: text === "" ? "normal" : root.nameCheck.ok ? "ok" : "error"
                            }
                            AppField {
                                id: userField
                                Layout.fillWidth: true
                                label: "ชื่อผู้ใช้"; mono: true; placeholder: "เช่น namfon"
                                hint: text === "" ? "a–z ตัวเลข และ - ใช้พิมพ์ตอนเข้าสู่ระบบ" : root.userCheck.message
                                hintKind: text === "" ? "normal" : root.userCheck.ok ? "ok" : "error"
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                AppField { id: pw1; Layout.fillWidth: true; label: "รหัสผ่าน"; password: true; emphasis: true }
                                RowLayout {
                                    spacing: 8
                                    Repeater {
                                        model: 4
                                        Rectangle {
                                            required property int index
                                            Layout.fillWidth: true
                                            height: 6; radius: 3
                                            color: index < root.strength ? (root.strength >= 3 ? Theme.ok : Theme.warn) : Theme.line
                                        }
                                    }
                                    AppText { text: signup.strengthLabel(root.strength); size: Theme.fontCaption; oneLine: true; strong: true
                                              color: root.strength >= 3 ? Theme.okInk : Theme.warnInk }
                                }
                            }
                            AppField {
                                id: pw2
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignTop
                                label: "ยืนยันรหัสผ่าน"; password: true
                                hint: pw2.text === "" ? "" : root.pwCheck.message
                                hintKind: root.pwCheck.ok ? "ok" : "error"
                            }
                        }
                        Item { Layout.fillHeight: true }
                        RowLayout {
                            Layout.alignment: Qt.AlignRight
                            spacing: 12
                            AppButton { text: "ย้อนกลับ"; kind: "secondary"; onClicked: AppState.go("login") }
                            AppButton { text: "ถัดไป"; enabled: root.accountValid; onClicked: root.page = 1 }
                        }
                    }
                }
                Rectangle {
                    Layout.preferredWidth: 340
                    Layout.fillHeight: true
                    radius: Theme.radiusLarge
                    color: Theme.accentSoft
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 12
                        Icon { path: Icons.lock; color: Theme.bubbleInk; width: 28; height: 28 }
                        AppText { text: "บัญชีของคุณแยกจากคนอื่น"; size: Theme.fontHeading; strong: true; color: Theme.bubbleInk }
                        AppText { Layout.fillWidth: true; color: Theme.bubbleInk
                                  text: "ทุกบัญชีเป็นบัญชีของเครื่องจริง ไฟล์ แชท และนัดหมายของคุณอยู่ในโฟลเดอร์ที่ผู้ใช้คนอื่นเปิดไม่ได้" }
                        AppText { Layout.fillWidth: true; color: Theme.bubbleInk
                                  text: "ลืมรหัสผ่านได้ ใช้ PIN ที่ตั้งในขั้นถัดไปตั้งรหัสใหม่ · ลงทะเบียนใบหน้าได้ในหน้าตั้งค่าหลังเข้าใช้" }
                        Item { Layout.fillHeight: true }
                    }
                }
            }

            // ---------- 2. ตั้ง PIN กู้คืน (กด "สร้างบัญชี" = สร้างจริงตรงนี้) ----------
            Card {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 32
                    spacing: 16
                    RowLayout {
                        spacing: 12
                        Rectangle {
                            width: 44; height: 44; radius: Theme.radiusCard; color: Theme.accentSoft
                            Icon { anchors.centerIn: parent; path: Icons.key; color: Theme.accentInk; width: 22; height: 22 }
                        }
                        AppText { text: "ตั้ง PIN สำหรับกู้คืนรหัสผ่าน"; size: Theme.fontTitle; strong: true }
                    }
                    AppText { Layout.fillWidth: true; color: Theme.inkMuted
                              text: "ถ้าลืมรหัสผ่าน ใช้ PIN นี้ที่หน้า Login (“ลืมรหัสผ่าน?”) เพื่อตั้งรหัสใหม่ · ตัวเลข 6–12 หลัก" }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 16
                        AppField {
                            id: pin1
                            objectName: "pin1"
                            Layout.fillWidth: true
                            label: "PIN"; password: true; mono: true; emphasis: true
                            field.inputMethodHints: Qt.ImhDigitsOnly
                            field.maximumLength: 12
                        }
                        AppField {
                            id: pin2
                            objectName: "pin2"
                            Layout.fillWidth: true
                            label: "ยืนยัน PIN"; password: true; mono: true
                            field.inputMethodHints: Qt.ImhDigitsOnly
                            field.maximumLength: 12
                            hint: pin1.text === "" ? "" : root.pinCheck.message
                            hintKind: pin1.text === "" ? "normal" : root.pinCheck.ok ? "ok" : "error"
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: warnText.implicitHeight + 28
                        radius: Theme.radiusCard
                        color: Theme.warnSoft
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 12
                            Icon { path: Icons.alert; color: Theme.warnInk; Layout.alignment: Qt.AlignTop }
                            AppText {
                                id: warnText
                                Layout.fillWidth: true
                                color: Theme.warnInk
                                text: "ใครรู้ PIN นี้ ตั้งรหัสผ่านใหม่ให้บัญชีของคุณได้ · อย่าใช้วันเกิด เบอร์โทร หรือ PIN เดียวกับบัตร ATM · ใส่ผิดหลายครั้งต้องรอนานขึ้นเรื่อย ๆ"
                            }
                        }
                    }
                    AppText {
                        id: createMsg
                        objectName: "createMsg"
                        visible: text !== ""
                        color: Theme.danger
                        Layout.fillWidth: true
                    }
                    AppText { visible: signup.busy; text: "กำลังสร้างบัญชี…"; color: Theme.inkMuted }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        spacing: 12
                        AppButton { text: "ย้อนกลับ"; kind: "secondary"; enabled: !signup.busy; onClicked: root.page = 0 }
                        AppButton {
                            text: "สร้างบัญชี"
                            enabled: root.accountValid && root.pinCheck.ok && !signup.busy
                            onClicked: signup.create(nameField.text, userField.text, pw1.text, pin1.text)
                        }
                    }
                }
            }

            // ---------- 3. พร้อมใช้ ----------
            Card {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: 600
                    spacing: 16
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 72; height: 72; radius: 36
                        color: root.simulated ? Theme.warnSoft : Theme.okSoft
                        Icon { anchors.centerIn: parent; path: root.simulated ? Icons.alert : Icons.check
                               color: root.simulated ? Theme.warnInk : Theme.okInk; width: 36; height: 36; stroke: 2.2 }
                    }
                    AppText {
                        Layout.alignment: Qt.AlignHCenter
                        text: root.simulated ? "เดินครบทุกขั้นแล้ว (จำลอง)" : "บัญชีของ " + nameField.text + " พร้อมใช้แล้ว"
                        size: Theme.px(30); strong: true
                    }
                    AppText {
                        visible: root.simulated
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        color: Theme.warnInk
                        text: "หน้าต่างพัฒนา: ไม่ได้สร้างบัญชีจริง · บัญชีจริงสร้างได้จากหน้า Login ของเครื่องเท่านั้น"
                    }
                    AppText { visible: root.loginError !== ""; text: root.loginError; color: Theme.danger; Layout.fillWidth: true }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 12
                        AppButton { text: "ไปหน้า Login"; kind: "secondary"; onClicked: AppState.go("login") }
                        AppButton {
                            text: "เข้าสู่ระบบเลย"
                            visible: !root.simulated
                            onClicked: root.loginError = login.signIn(userField.text, pw1.text)
                        }
                    }
                }
            }
        }
    }
}
