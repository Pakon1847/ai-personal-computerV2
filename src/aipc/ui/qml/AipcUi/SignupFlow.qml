// สมัครบัญชีจากหน้า Login (BRIEF 5.1 ข้อ 3–6)
// ลำดับ: บัญชี+รหัสผ่าน → รหัสกู้คืน → ผู้ดูแลอนุมัติ → ยินยอม → ลงทะเบียนใบหน้า → พร้อมใช้
// ผู้ดูแลอนุมัติก่อนลงทะเบียนใบหน้า เพราะ BRIEF 5.1 ข้อ 3: ระหว่างรออนุมัติ ลงทะเบียนใบหน้าไม่ได้
//
// ยังไม่มีตัวสร้างบัญชีจริง (authd, เฟส 1) · ทุกอย่างที่ต้องใช้ backend จริงถูกปิดไว้นอกโหมดพัฒนา
// และบอกผู้ใช้ตรง ๆ แทนการทำเป็นว่าสำเร็จ
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import AipcUi

Rectangle {
    id: root
    color: Theme.bg
    property int page: 0                 // 0 บัญชี 1 รหัสกู้คืน 2 อนุมัติ 3 ยินยอม 4 ใบหน้า 5 เสร็จ
    readonly property var stepOf: [1, 2, 3, 4, 4, 5]
    property string recoveryCode: ""
    // จริงเป็น true ได้เมื่อ visiond บันทึกแม่แบบใบหน้าสำเร็จเท่านั้น (ยังไม่มี) · ห้ามตั้งเองจากหน้าจอ
    readonly property bool faceEnrolled: false

    // ผลตรวจฟอร์มจาก Python (กฎชุดเดียวกับที่ตัวสร้างบัญชีจริงจะใช้)
    readonly property var userCheck: signup.checkUsername(userField.text)
    readonly property var pwCheck: signup.checkPassword(pw1.text, pw2.text)
    readonly property int strength: signup.strength(pw1.text)
    readonly property bool accountValid: nameField.text.trim() !== "" && userCheck.ok && pwCheck.ok

    Component.onCompleted: {
        page = startSignupStep
        if (page > 0) recoveryCode = signup.newRecoveryCode()
    }

    function next() {
        if (page === 0) recoveryCode = signup.newRecoveryCode()
        page = page + 1
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
            AppButton { text: "ยกเลิก กลับหน้า Login"; kind: "ghost"; visible: root.page < 5; onClicked: AppState.go("login") }
        }

        SignupSteps { Layout.fillWidth: true; step: root.stepOf[root.page] }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // StackLayout คิดความสูงขั้นต่ำจากทุกหน้ารวมกัน (ไม่ใช่แค่หน้าที่แสดง) จนดันจอล้น
            // จึงบอกว่าขั้นต่ำเป็น 0 แล้วให้หน้าที่แสดงใช้พื้นที่ที่เหลือจริง
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
                            AppField { id: nameField; Layout.fillWidth: true; label: "ชื่อที่แสดง"; hint: "ใช้ทักทายและแสดงที่หน้า Login" }
                            AppField {
                                id: userField
                                Layout.fillWidth: true
                                label: "ชื่อผู้ใช้"; mono: true; placeholder: "เช่น namfon"
                                hint: text === "" ? "a–z ตัวเลข และ - ใช้เข้าระบบเมื่อไม่ใช้ใบหน้า" : root.userCheck.message
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
                            AppButton { text: "ถัดไป"; enabled: root.accountValid; onClicked: root.next() }
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
                        AppText { text: "ทำไมรหัสผ่านสำคัญ"; size: Theme.fontHeading; strong: true; color: Theme.bubbleInk }
                        AppText { Layout.fillWidth: true; color: Theme.bubbleInk
                                  text: "รหัสผ่านคือกุญแจที่ใช้เข้ารหัสไฟล์และแชทของคุณ แม้ผู้ดูแลเครื่องก็เปิดอ่านไม่ได้" }
                        AppText { Layout.fillWidth: true; color: Theme.bubbleInk
                                  text: "ใบหน้าช่วยให้ไม่ต้องพิมพ์ชื่อ และปลดล็อกหน้าจอได้เร็ว แต่ใช้แทนรหัสผ่านตอนเปิดเครื่องไม่ได้" }
                        Item { Layout.fillHeight: true }
                    }
                }
            }

            // ---------- 2. รหัสกู้คืน ----------
            Card {
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 32
                    spacing: 18
                    RowLayout {
                        spacing: 12
                        Rectangle {
                            width: 44; height: 44; radius: Theme.radiusCard; color: Theme.accentSoft
                            Icon { anchors.centerIn: parent; path: Icons.key; color: Theme.accentInk; width: 22; height: 22 }
                        }
                        AppText { text: "จดรหัสกู้คืนไว้ในที่ปลอดภัย"; size: Theme.fontTitle; strong: true }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 88
                        radius: Theme.radiusCard
                        color: Theme.surface2
                        border.width: 1
                        border.color: Theme.lineStrong
                        Text {
                            anchors.centerIn: parent
                            text: root.recoveryCode
                            font.family: Theme.mono
                            font.pixelSize: Theme.px(28)
                            font.letterSpacing: 2
                            color: Theme.ink
                            Accessible.name: "รหัสกู้คืน"
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: warnText.implicitHeight + 28
                        radius: Theme.radiusCard
                        color: Theme.dangerSoft
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 12
                            Icon { path: Icons.alert; color: Theme.dangerInk; Layout.alignment: Qt.AlignTop }
                            AppText {
                                id: warnText
                                Layout.fillWidth: true
                                color: Theme.dangerInk
                                text: "แสดงครั้งเดียว · ถ้าลืมรหัสผ่านและไม่มีรหัสนี้ ข้อมูลของคุณจะเปิดไม่ได้อีก ผู้ดูแลรีเซ็ตรหัสผ่านให้ได้ แต่เปิดข้อมูลที่เข้ารหัสไม่ได้"
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        AppButton { text: "พิมพ์ออกกระดาษ"; kind: "secondary"; enabled: false
                                    ToolTip.visible: hovered; ToolTip.text: "ยังไม่พร้อม" }
                        Item { Layout.fillWidth: true }
                        AppCheck { id: wroteDown; text: "ฉันจดไว้แล้ว" }
                        AppButton { text: "ถัดไป"; enabled: wroteDown.checked; onClicked: root.next() }
                    }
                }
            }

            // ---------- 3. ผู้ดูแลอนุมัติ ----------
            ColumnLayout {
                spacing: 16
                ColumnLayout {
                    spacing: 2
                    AppText { text: "ผู้ดูแลต้องอนุมัติบัญชีใหม่"; size: Theme.fontTitle; strong: true }
                    AppText { text: "บัญชีใหม่ต้องได้รับอนุมัติก่อนใช้งานและก่อนลงทะเบียนใบหน้า"; color: Theme.inkMuted }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 24
                    Card {
                        highlight: true
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 28
                            spacing: 14
                            AppText { text: "ผู้ดูแลอยู่ตรงนี้"; size: Theme.px(22); strong: true }
                            AppText { text: "ให้ผู้ดูแลใส่รหัสผ่านของตัวเองเพื่ออนุมัติทันที"; color: Theme.inkMuted; Layout.fillWidth: true }
                            AppField { id: adminPw; Layout.fillWidth: true; label: "รหัสผ่านของผู้ดูแล"; password: true; emphasis: true }
                            AppText {
                                id: approveMsg
                                visible: text !== ""
                                color: Theme.danger
                                Layout.fillWidth: true
                            }
                            Item { Layout.fillHeight: true }
                            AppButton {
                                text: "อนุมัติและทำต่อ"
                                onClicked: {
                                    if (AppState.devMode) root.next()
                                    else approveMsg.text = "ยังตรวจรหัสผ่านผู้ดูแลไม่ได้: ตัวจัดการบัญชี (authd) อยู่ในเฟส 1"
                                }
                            }
                        }
                    }
                    Card {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 28
                            spacing: 14
                            AppText { text: "ขออนุมัติภายหลัง"; size: Theme.px(22); strong: true }
                            AppText { text: "ส่งคำขอไว้ ผู้ดูแลจะเห็นเมื่อเข้าสู่ระบบครั้งถัดไป"; color: Theme.inkMuted; Layout.fillWidth: true }
                            Chip {
                                Layout.fillWidth: true
                                implicitHeight: 64
                                radius: Theme.radiusCard
                                kind: "warn"
                                text: "ระหว่างรอ เข้าใช้และลงทะเบียนใบหน้ายังไม่ได้"
                                iconPath: Icons.alert
                            }
                            Item { Layout.fillHeight: true }
                            AppButton { text: "ส่งคำขอแล้วกลับหน้า Login"; kind: "secondary"; enabled: false
                                        ToolTip.visible: hovered; ToolTip.text: "ยังไม่พร้อม: ต้องมีตัวจัดการบัญชี (เฟส 1)" }
                        }
                    }
                }
            }

            // ---------- 4ก. ยินยอมใช้ใบหน้า ----------
            Card {
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 28
                    spacing: 32
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 12
                        AppText { text: "ใช้ใบหน้าเพื่อเข้าสู่ระบบไหม"; size: Theme.fontTitle; strong: true }
                        AppText { text: "ไม่บังคับ ข้ามได้และใช้รหัสผ่านอย่างเดียวก็ได้ เปลี่ยนใจภายหลังได้"; color: Theme.inkMuted; Layout.fillWidth: true }
                        Repeater {
                            model: [
                                { t: "ให้หน้า Login จำหน้าฉัน และปลดล็อกหน้าจอ", d: "มองกล้องแล้วระบบหาบัญชีให้ · ข้อมูลใบหน้าชุดนี้ต้องอ่านได้ก่อนมีใครเข้าสู่ระบบ จึงเข้ารหัสด้วยกุญแจของเครื่อง" },
                                { t: "ใช้แค่ปลดล็อกหน้าจอ", d: "ที่หน้า Login ต้องพิมพ์ชื่อผู้ใช้เอง · ข้อมูลใบหน้าเข้ารหัสด้วยกุญแจของคุณ" }
                            ]
                            AppCheck {
                                required property int index
                                required property var modelData
                                Layout.fillWidth: true
                                radio: true
                                boxed: true
                                autoExclusive: true
                                checked: index === 0
                                text: modelData.t
                                detail: modelData.d
                            }
                        }
                        AppCheck {
                            id: consent
                            Layout.fillWidth: true
                            text: "ฉันยินยอมให้เครื่องนี้เก็บข้อมูลใบหน้าของฉันเป็นตัวเลข เพื่อใช้ตามที่เลือกไว้ด้านบน"
                        }
                        Item { Layout.fillHeight: true }
                        RowLayout {
                            spacing: 12
                            AppButton { text: "ยินยอมและเริ่มลงทะเบียน"; enabled: consent.checked; onClicked: root.page = 4 }
                            AppButton { text: "ข้าม ใช้รหัสผ่านอย่างเดียว"; kind: "secondary"; onClicked: root.page = 5 }
                        }
                    }
                    Rectangle {
                        Layout.preferredWidth: 340
                        Layout.fillHeight: true
                        radius: Theme.radiusCard
                        color: Theme.surface2
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 12
                            AppText { text: "สิ่งที่ระบบเก็บ"; size: Theme.px(18); strong: true }
                            Repeater {
                                model: ["ตัวเลขแทนใบหน้า ไม่เก็บภาพหรือวิดีโอ", "ภาพจากกล้องประมวลผลในเครื่อง ไม่ส่งออกเน็ต", "ลบหรือถอนความยินยอมได้ทุกเมื่อ แล้วใช้รหัสผ่านต่อได้"]
                                RowLayout {
                                    required property string modelData
                                    Layout.fillWidth: true
                                    spacing: 10
                                    Icon { path: Icons.check; color: Theme.ok; Layout.alignment: Qt.AlignTop }
                                    AppText { text: parent.modelData; Layout.fillWidth: true }
                                }
                            }
                            AppText { Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                      text: "ข้อมูลใบหน้าเป็นข้อมูลชีวภาพ ซึ่งเป็นข้อมูลอ่อนไหวตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล มาตรา 26" }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // ---------- 4ข. ลงทะเบียนใบหน้า ----------
            RowLayout {
                spacing: 32
                Rectangle {
                    Layout.preferredWidth: 640
                    Layout.fillHeight: true
                    radius: Theme.radiusLarge
                    color: Theme.camera
                    FaceRing { anchors.centerIn: parent; dashed: true; color: Theme.inkFaint; width: 200; height: 260 }
                    Chip {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                        anchors.margins: 16
                        height: 44
                        radius: Theme.radiusCard
                        kind: "neutral"
                        text: system.cameraPresent ? "พบกล้อง แต่ระบบจดจำใบหน้ายังไม่ได้ติดตั้ง" : "ไม่พบกล้องที่เครื่องนี้"
                        iconPath: Icons.alert
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 16
                    NotReady {
                        Layout.fillWidth: true
                        title: "ลงทะเบียนใบหน้ายังไม่ได้"
                        detail: "ระบบจดจำใบหน้า (visiond) อยู่ในเฟส 2 · ข้ามขั้นนี้ได้ และกลับมาลงทะเบียนภายหลังในหน้าความเป็นส่วนตัว"
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: useCol.implicitHeight + 36
                        radius: Theme.radiusLarge
                        color: Theme.surface2
                        ColumnLayout {
                            id: useCol
                            anchors.fill: parent
                            anchors.margins: 18
                            spacing: 6
                            AppText { text: "เมื่อพร้อม ขั้นนี้จะ"; strong: true }
                            AppText { text: "· เก็บหลายมุม (ตรง ซ้าย ขวา ก้ม เงย) และหลายสภาพแสง"; Layout.fillWidth: true }
                            AppText { text: "· รับเฉพาะภาพที่ชัดและสว่างพอ บอกเหตุผลเมื่อไม่ผ่าน"; Layout.fillWidth: true }
                            AppText { text: "· เก็บเป็นตัวเลขแทนใบหน้า ไม่เก็บภาพ"; Layout.fillWidth: true }
                        }
                    }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        spacing: 12
                        AppButton { text: "ย้อนกลับ"; kind: "secondary"; onClicked: root.page = 3 }
                        AppButton { text: "ข้ามขั้นนี้"; onClicked: root.page = 5 }
                    }
                }
            }

            // ---------- 5. พร้อมใช้ ----------
            Card {
                ColumnLayout {
                    anchors.centerIn: parent
                    width: 600
                    spacing: 16
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 72; height: 72; radius: 36
                        color: AppState.devMode ? Theme.warnSoft : Theme.okSoft
                        Icon { anchors.centerIn: parent; path: AppState.devMode ? Icons.alert : Icons.check
                               color: AppState.devMode ? Theme.warnInk : Theme.okInk; width: 36; height: 36; stroke: 2.2 }
                    }
                    AppText {
                        Layout.alignment: Qt.AlignHCenter
                        text: AppState.devMode ? "เดินครบทุกขั้นแล้ว (โหมดพัฒนา)" : "บัญชีของ " + nameField.text + " พร้อมใช้แล้ว"
                        size: Theme.px(30); strong: true
                    }
                    AppText {
                        visible: AppState.devMode
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        color: Theme.warnInk
                        text: "บัญชียังไม่ถูกสร้างจริง และรหัสกู้คืนไม่ได้ถูกบันทึก — ต้องมีตัวจัดการบัญชี (เฟส 1)"
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: summary.implicitHeight
                        radius: Theme.radiusCard
                        color: "transparent"
                        border.width: 1
                        border.color: Theme.line
                        ColumnLayout {
                            id: summary
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 0
                            Repeater {
                                model: [
                                    ["ชื่อที่แสดง", nameField.text],
                                    ["ชื่อผู้ใช้", userField.text],
                                    ["รหัสกู้คืน", "จดไว้แล้ว"],
                                    ["ใบหน้า", root.faceEnrolled ? "ลงทะเบียนแล้ว" : "ยังไม่ได้ลงทะเบียน · ใช้รหัสผ่าน"]
                                ]
                                RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.margins: 12
                                    AppText { text: parent.modelData[0]; color: Theme.inkMuted; oneLine: true }
                                    Item { Layout.fillWidth: true }
                                    AppText { text: parent.modelData[1]; strong: true; oneLine: true }
                                }
                            }
                        }
                    }
                    AppButton {
                        Layout.alignment: Qt.AlignHCenter
                        text: "ไปหน้า Login"
                        onClicked: AppState.go("login")
                    }
                }
            }
        }
    }
}
