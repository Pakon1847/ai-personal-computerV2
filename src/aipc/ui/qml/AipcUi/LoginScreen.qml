// หน้า Login (BRIEF 5.1) · ซ้าย = กล้องสแกนหน้า, ขวา = บัญชี/รหัสผ่าน + ปุ่มสมัครบัญชี
// state มาจาก login.scanState ใน Python:
//   unavailable = ยังไม่มีระบบจดจำใบหน้า (ค่าจริงตอนนี้) → ใช้ชื่อผู้ใช้ + รหัสผ่าน
//   scanning / found / unknown / manual = สถานะตามบอร์ดออกแบบ (ตอนนี้ดูได้ในโหมดสาธิตเท่านั้น)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import AipcUi

Rectangle {
    id: root
    color: Theme.bg
    readonly property string scan: login.scanState
    readonly property bool typing: scan === "manual" || scan === "unavailable"
    property string error: ""

    function submit(user, pw) {
        error = login.signIn(user, pw)
        if (error === "") AppState.open("workspace")
    }

    readonly property var status: ({
        unavailable: { text: system.cameraPresent ? "ระบบจดจำใบหน้ายังไม่พร้อม · ใช้รหัสผ่านได้เลย"
                                                  : "ไม่พบกล้อง · ใช้รหัสผ่านได้เลย", kind: "neutral" },
        scanning: { text: "กำลังสแกนใบหน้า…", kind: "accent" },
        found: { text: "จำหน้าได้ · ตรงกับบัญชี " + login.foundName, kind: "ok" },
        unknown: { text: "ยังไม่พบบัญชีที่ตรงกับใบหน้านี้", kind: "warn" },
        manual: { text: "หยุดสแกนแล้ว · ใช้ชื่อผู้ใช้และรหัสผ่าน", kind: "neutral" }
    })[scan]

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 56
        anchors.rightMargin: 56
        anchors.topMargin: 28
        anchors.bottomMargin: 24
        spacing: 20

        RowLayout {
            Layout.fillWidth: true
            BrandMark {}
            Item { Layout.fillWidth: true }
            AppText { text: system.clock; size: Theme.fontTitle; strong: true; oneLine: true }
            AppText { text: system.longDate; color: Theme.inkMuted; oneLine: true }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 32

            // ---------- กล้อง ----------
            Rectangle {
                Layout.preferredWidth: 600
                Layout.fillHeight: true
                radius: 20
                color: Theme.camera
                Accessible.name: "สแกนใบหน้า"

                FaceRing {
                    id: ring
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -20
                    dashed: root.scan === "scanning" || root.scan === "manual"
                    color: root.scan === "found" ? Theme.scanFound
                         : root.scan === "unknown" ? Theme.scanUnknown
                         : root.scan === "scanning" ? Theme.cameraText : Theme.inkFaint
                    visible: root.scan !== "unavailable"
                    // เส้นสแกนเลื่อนขึ้นลงระหว่างสแกน · ขยับแค่ตำแหน่ง จึงไม่หนัก GPU
                    Rectangle {
                        visible: root.scan === "scanning"
                        x: 16; width: parent.width - 32; height: 3; radius: 2
                        color: "#7FD1CB"
                        SequentialAnimation on y {
                            running: root.scan === "scanning"
                            loops: Animation.Infinite
                            NumberAnimation { from: 40; to: 250; duration: 1400; easing.type: Easing.InOutSine }
                            NumberAnimation { from: 250; to: 40; duration: 1400; easing.type: Easing.InOutSine }
                        }
                    }
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    visible: root.scan === "unavailable"
                    spacing: 12
                    Icon {
                        Layout.alignment: Qt.AlignHCenter
                        path: system.cameraPresent ? Icons.camera : Icons.cameraOff
                        color: Theme.cameraText
                        Layout.preferredWidth: 56; Layout.preferredHeight: 56
                        stroke: 1.4
                    }
                    AppText {
                        Layout.alignment: Qt.AlignHCenter
                        text: system.cameraPresent ? "พบกล้อง แต่ระบบจดจำใบหน้ายังไม่ได้ติดตั้ง" : "ไม่พบกล้องที่เครื่องนี้"
                        color: Theme.cameraText
                    }
                }

                Chip {
                    anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 16
                    text: "ประมวลผลในเครื่อง ไม่บันทึกภาพ"
                    kind: "ok"; dot: true
                }

                Chip {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                    anchors.margins: 16
                    height: 44
                    radius: Theme.radiusCard
                    text: root.status.text
                    kind: root.status.kind
                    iconPath: root.scan === "found" ? Icons.check : ""
                }
            }

            // ---------- บัญชี ----------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 16

                Card {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 28
                        spacing: 14

                        // กำลังสแกน
                        ColumnLayout {
                            visible: root.scan === "scanning"
                            spacing: 12
                            AppText { text: "มองมาที่กล้อง"; size: Theme.fontTitle; strong: true }
                            AppText { text: "ระบบจะหาบัญชีของคุณจากใบหน้า ไม่ต้องพิมพ์ชื่อ"; color: Theme.inkMuted; Layout.fillWidth: true }
                            AppButton { text: "พิมพ์ชื่อผู้ใช้และรหัสผ่านแทน"; kind: "secondary"; onClicked: login.setScanState("manual") }
                        }

                        // จำหน้าได้
                        ColumnLayout {
                            visible: root.scan === "found"
                            spacing: 16
                            RowLayout {
                                spacing: 16
                                Avatar { name: login.foundName; size: 64 }
                                ColumnLayout {
                                    spacing: 0
                                    AppText { text: "สวัสดี"; size: Theme.fontSmall; color: Theme.inkMuted }
                                    AppText { text: login.foundName; size: Theme.px(24); strong: true }
                                }
                                Item { Layout.fillWidth: true }
                                AppButton { text: "ไม่ใช่ฉัน"; kind: "ghost"; onClicked: login.setScanState("manual") }
                            }
                            AppField {
                                id: foundPw
                                Layout.fillWidth: true
                                label: "รหัสผ่าน"; password: true; emphasis: true
                                hint: "ใบหน้าช่วยหาบัญชี ส่วนรหัสผ่านคือกุญแจเปิดข้อมูลของคุณ"
                                field.onAccepted: root.submit(login.foundName, text)
                            }
                            AppButton { text: "เข้าสู่ระบบ"; onClicked: root.submit(login.foundName, foundPw.text) }
                        }

                        // ไม่รู้จักใบหน้า
                        ColumnLayout {
                            visible: root.scan === "unknown"
                            spacing: 12
                            AppText { text: "ยังไม่รู้จักใบหน้านี้"; size: Theme.fontTitle; strong: true }
                            AppText { text: "อาจยังไม่ได้ลงทะเบียนใบหน้า หรือแสงไม่พอ"; color: Theme.inkMuted; Layout.fillWidth: true }
                            RowLayout {
                                spacing: 8
                                AppButton { text: "สแกนอีกครั้ง"; onClicked: login.setScanState("scanning") }
                                AppButton { text: "พิมพ์ชื่อผู้ใช้แทน"; kind: "secondary"; onClicked: login.setScanState("manual") }
                            }
                        }

                        // พิมพ์ชื่อผู้ใช้ (รวมกรณียังไม่มีระบบใบหน้า)
                        ColumnLayout {
                            visible: root.typing
                            spacing: 12
                            AppField { id: userField; Layout.fillWidth: true; label: "ชื่อผู้ใช้"; placeholder: "เช่น pakon"; mono: true }
                            AppField {
                                id: pwField
                                Layout.fillWidth: true
                                label: "รหัสผ่าน"; password: true; emphasis: true
                                field.onAccepted: root.submit(userField.text, text)
                            }
                            RowLayout {
                                spacing: 8
                                AppButton { text: "เข้าสู่ระบบ"; onClicked: root.submit(userField.text, pwField.text) }
                                AppButton {
                                    visible: root.scan === "manual"
                                    text: "สแกนหน้าแทน"; kind: "secondary"
                                    onClicked: login.setScanState("scanning")
                                }
                            }
                        }

                        AppText {
                            visible: root.error !== ""
                            text: root.error
                            color: Theme.danger
                            Layout.fillWidth: true
                        }

                        Item { Layout.fillHeight: true }
                        AppButton { text: "ลืมรหัสผ่าน? ใช้รหัสกู้คืน"; kind: "ghost"; leftPadding: 0; enabled: false
                                    ToolTip.visible: hovered; ToolTip.text: "ยังไม่พร้อม (เฟส 1)" }
                    }
                }

                Card {
                    Layout.fillWidth: true
                    Layout.preferredHeight: signupRow.implicitHeight + 36
                    RowLayout {
                        id: signupRow
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 16
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            AppText { text: "ยังไม่มีบัญชี?"; strong: true }
                            AppText { text: "ตั้งรหัสผ่าน · รับรหัสกู้คืน · ลงทะเบียนใบหน้า"; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                        }
                        AppButton { text: "สมัครบัญชี"; kind: "outline"; iconPath: Icons.userPlus; onClicked: AppState.go("signup") }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Chip {
                text: system.cameraPresent ? "กล้องพร้อม" : "ไม่พบกล้อง"
                kind: system.cameraPresent ? "ok" : "neutral"
                dot: true
            }
            Item { Layout.fillWidth: true }
            AppButton { text: "ภาษา: ไทย"; kind: "secondary"; enabled: false }
            AppButton { text: "ปิดเครื่อง"; kind: "secondary"; iconPath: Icons.power; enabled: false
                        ToolTip.visible: hovered; ToolTip.text: "ยังไม่พร้อม (เฟส 1)" }
        }
    }
}
