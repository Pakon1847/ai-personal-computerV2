// หน้า Login (BRIEF 5.1) แบบหน้าล็อก (การ์ด 0002) · เวลาใหญ่ → วงกล้อง → ชื่อ/รหัสผ่าน อยู่กลางจอ
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
        // รหัสผ่านไม่ค้างอยู่ในช่องหลังส่ง (การ์ด 0003 H3)
        pwField.text = ""
        foundPw.text = ""
        // โหมด greeter: เข้าได้แล้ว Python ปิดหน้าต่างเอง แล้ว greetd เริ่มเซสชันของผู้ใช้
        if (error === "" && !login.greeterMode) AppState.open("workspace")
    }

    readonly property var status: ({
        unavailable: { text: system.cameraPresent ? "รุ่นนี้เข้าสู่ระบบด้วยรหัสผ่าน"
                                                  : "ไม่พบกล้อง · ใช้รหัสผ่านได้เลย", kind: "neutral" },
        scanning: { text: "กำลังสแกนใบหน้า… มองมาที่กล้อง", kind: "accent" },
        found: { text: "จำหน้าได้", kind: "ok" },
        unknown: { text: "ยังไม่พบบัญชีที่ตรงกับใบหน้านี้", kind: "warn" },
        manual: { text: "หยุดสแกนแล้ว · ใช้ชื่อผู้ใช้และรหัสผ่าน", kind: "neutral" }
    })[scan]

    // ---------- แถบบน ----------
    RowLayout {
        id: topBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 24
        anchors.leftMargin: 32
        anchors.rightMargin: 32
        BrandMark {}
        Item { Layout.fillWidth: true }
        Chip { text: "ใบหน้าประมวลผลในเครื่อง ไม่บันทึกภาพ"; kind: "ok"; iconPath: Icons.shield }
    }

    // ---------- กลางจอ ----------
    // อยู่ระหว่างแถบบนกับแถบล่างเสมอ · ตัวอักษรใหญ่ (สูงสุด 200%) จนยาวเกินจอ → เลื่อนได้ ไม่ทับแถบล่าง
    PageScroll {
        id: middle
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: topBar.bottom
        anchors.bottom: bottomBar.top
        anchors.bottomMargin: 8
        contentHeight: Math.max(height, col.implicitHeight)

    ColumnLayout {
        id: col
        x: (middle.width - width) / 2
        width: Math.min(implicitWidth, middle.width - 32)
        spacing: 0

        AppText {
            Layout.alignment: Qt.AlignHCenter
            // นาฬิกาใหญ่อยู่แล้ว ขยายตามตัวอักษรได้ไม่เกิน 84 px · ที่เหลือให้ช่องพิมพ์ ไม่ต้องเลื่อนหา
            text: system.clock; size: Math.min(Theme.px(60), 84); strong: true; oneLine: true
        }
        AppText {
            Layout.alignment: Qt.AlignHCenter
            text: system.longDate; color: Theme.inkMuted; oneLine: true
        }

        // วงกล้อง · สีขอบบอกสถานะ (เขียว = จำได้, ส้ม = ไม่รู้จัก, คราม = กำลังสแกน)
        Rectangle {
            id: cam
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 18
            // ตัวอักษรใหญ่ → วงเล็กลง เหลือที่ให้ช่องพิมพ์ (ความกว้างจอเท่าเดิม)
            implicitWidth: Theme.fontScale > 1.5 ? 112 : Theme.fontScale > 1.2 ? 160 : 200
            implicitHeight: implicitWidth; radius: implicitWidth / 2
            color: Theme.camera
            border.width: 4
            border.color: root.scan === "found" ? Theme.scanFound
                        : root.scan === "unknown" ? Theme.scanUnknown
                        : root.scan === "scanning" ? Theme.scanLine : Theme.lineStrong
            Accessible.name: "สแกนใบหน้า"
            clip: true

            Icon {
                anchors.centerIn: parent
                visible: root.scan === "unavailable" || root.scan === "manual"
                path: system.cameraPresent ? Icons.camera : Icons.cameraOff
                color: Theme.cameraText
                width: 48; height: 48; stroke: 1.4
            }
            Icon {
                anchors.centerIn: parent
                visible: root.scan === "found"
                path: Icons.check; color: Theme.scanFound
                width: 56; height: 56; stroke: 2.4
            }
            // เส้นสแกนเลื่อนขึ้นลงระหว่างสแกน · ขยับแค่ตำแหน่ง จึงไม่หนัก GPU
            Rectangle {
                visible: root.scan === "scanning"
                x: 40; width: parent.width - 80; height: 3; radius: 2
                color: Theme.scanLine
                SequentialAnimation on y {
                    running: root.scan === "scanning"
                    loops: Animation.Infinite
                    NumberAnimation { from: 50; to: 150; duration: 1400; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 150; to: 50; duration: 1400; easing.type: Easing.InOutSine }
                }
            }
        }

        Chip {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 12
            text: root.status.text
            kind: root.status.kind
        }

        // กำลังสแกน
        AppButton {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 16
            visible: root.scan === "scanning"
            text: "พิมพ์ชื่อผู้ใช้และรหัสผ่านแทน"; kind: "secondary"
            onClicked: login.setScanState("manual")
        }

        // จำหน้าได้
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 14
            visible: root.scan === "found"
            spacing: 12
            AppText { text: "สวัสดี " + login.foundName; size: Theme.px(22); strong: true; oneLine: true }
            AppButton { text: "ไม่ใช่ฉัน"; kind: "ghost"; onClicked: login.setScanState("manual") }
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            visible: root.scan === "found"
            spacing: 8
            AppField {
                id: foundPw
                Layout.preferredWidth: 300
                placeholder: "รหัสผ่าน"; password: true; emphasis: true
                field.onAccepted: root.submit(login.foundName, text)
            }
            AppButton { text: "เข้าสู่ระบบ"; onClicked: root.submit(login.foundName, foundPw.text) }
        }

        // ไม่รู้จักใบหน้า
        AppText {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 14
            visible: root.scan === "unknown"
            text: "อาจยังไม่ได้ลงทะเบียนใบหน้า หรือแสงไม่พอ"; color: Theme.inkMuted; oneLine: true
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 10
            visible: root.scan === "unknown"
            spacing: 8
            AppButton { text: "สแกนอีกครั้ง"; onClicked: login.setScanState("scanning") }
            AppButton { text: "พิมพ์ชื่อผู้ใช้แทน"; kind: "secondary"; onClicked: login.setScanState("manual") }
        }

        // พิมพ์ชื่อผู้ใช้ (รวมกรณียังไม่มีระบบใบหน้า) · ช่องเรียงแถวเดียวเพื่อไม่ให้ดันจอล้น
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 16
            visible: root.typing
            spacing: 8
            AppField { id: userField; Layout.preferredWidth: Math.round(220 * Math.min(Theme.fontScale, 1.5)); placeholder: "ชื่อผู้ใช้"; mono: true }
            AppField {
                id: pwField
                Layout.preferredWidth: Math.round(220 * Math.min(Theme.fontScale, 1.5))
                placeholder: "รหัสผ่าน"; password: true; emphasis: true
                field.onAccepted: root.submit(userField.text, text)
            }
            AppButton { text: "เข้าสู่ระบบ"; onClicked: root.submit(userField.text, pwField.text) }
        }
        AppButton {
            Layout.alignment: Qt.AlignHCenter
            visible: root.scan === "manual"
            text: "สแกนหน้าแทน"; kind: "ghost"
            onClicked: login.setScanState("scanning")
        }

        AppText {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 8
            visible: root.error !== ""
            text: root.error
            color: Theme.danger
        }

        AppButton {
            Layout.alignment: Qt.AlignHCenter
            text: "ลืมรหัสผ่าน? ใช้รหัสกู้คืน"; kind: "ghost"
            onClicked: AppState.go("recover")   // การ์ด 0012
        }
    }
    }

    // ---------- แถบล่าง ----------
    RowLayout {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24
        anchors.leftMargin: 32
        anchors.rightMargin: 32
        spacing: 8
        AppText {
            text: "เข้าสู่ระบบด้วยรหัสผ่าน · ข้อมูลของแต่ละคนแยกกันด้วยบัญชีของเครื่อง"
            size: Theme.fontSmall; color: Theme.inkFaint
            Layout.fillWidth: true
        }
        // สมัครจริงผ่านตัวช่วย root โดยผู้ดูแลยืนยัน (การ์ด 0012)
        AppButton { text: "สมัครบัญชี"; kind: "secondary"; iconPath: Icons.userPlus
                    onClicked: AppState.go("signup") }
        AppButton { text: "ภาษา: ไทย"; kind: "secondary"; iconPath: Icons.globe; enabled: false }
        AppButton { text: "ปิดเครื่อง"; kind: "secondary"; iconPath: Icons.power; enabled: false
                    ToolTip.visible: hovered; ToolTip.text: "ยังไม่พร้อม (เฟส 1)" }
    }
}
