// แถบนำทางแบบราง กว้าง 76 px (การ์ด 0002) · หกหน้าหลักตาม BRIEF 5.7 ข้อ 2 · ผู้ใช้ ปิดบัง ออก อยู่ล่างสุด
// เดิมกว้าง 232 px + รายการบทสนทนา 264 px กินจอ 39% · รางนี้คืนพื้นที่ให้เนื้อหา (BRIEF 5.7 ข้อ 5)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    // กว้าง 76 ที่ 100% และกว้างขึ้นตามขนาดตัวอักษร (ไม่เกิน 1.8 เท่า) ป้ายใต้ไอคอนจะได้ไม่ถูกตัดจนอ่านไม่ออก
    implicitWidth: Math.round(76 * Math.min(Theme.fontScale, 1.8))
    color: Theme.surface

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 16
        anchors.bottomMargin: 16
        spacing: 4

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: 14
            Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 12
            color: Theme.accentFill
            Accessible.name: "AI PC"
            AppText { anchors.centerIn: parent; text: "AI"; strong: true; oneLine: true; color: Theme.textOnAccent; size: Theme.px(15) }
        }
        NavItem { text: Tr.t("ผู้ช่วย AI"); shortText: Tr.t("ผู้ช่วย"); iconPath: Icons.chat; pageName: "workspace" }
        NavItem { text: Tr.t("ปฏิทิน"); iconPath: Icons.calendar; pageName: "calendar" }
        NavItem { text: Tr.t("ไฟล์ของฉัน"); shortText: Tr.t("ไฟล์"); iconPath: Icons.folder; pageName: "files" }
        NavItem { text: "Skill"; iconPath: Icons.sparkle; pageName: "skills" }
        NavItem { text: Tr.t("สุขภาพเครื่อง"); shortText: Tr.t("เครื่อง"); iconPath: Icons.activity; pageName: "health" }
        NavItem { text: Tr.t("ตั้งค่า"); iconPath: Icons.sliders; pageName: "settings" }
        Item { Layout.fillHeight: true }

        // ปิด/รีสตาร์ตเครื่อง (การ์ด 0052) · ถามยืนยันก่อนเสมอ (PowerDialog)
        AppButton {
            objectName: "rebootButton"
            Layout.alignment: Qt.AlignHCenter
            kind: "ghost"; iconPath: Icons.restart
            Accessible.name: Tr.t("รีสตาร์ตเครื่อง")
            ToolTip.visible: hovered; ToolTip.text: Tr.t("รีสตาร์ตเครื่อง")
            onClicked: powerDialog.ask("reboot")
        }
        AppButton {
            objectName: "powerOffButton"
            Layout.alignment: Qt.AlignHCenter
            kind: "ghost"; iconPath: Icons.power
            Accessible.name: Tr.t("ปิดเครื่อง")
            ToolTip.visible: hovered; ToolTip.text: Tr.t("ปิดเครื่อง")
            onClicked: powerDialog.ask("power_off")
        }
        AppButton {
            objectName: "logoutButton"
            Layout.alignment: Qt.AlignHCenter
            kind: "ghost"; iconPath: Icons.logout
            Accessible.name: Tr.t("ออกจากระบบ")
            // ออกไม่สำเร็จ → ข้อความค้างให้เห็น ไม่เงียบ (H2)
            ToolTip.visible: hovered || session.error !== ""
            ToolTip.text: session.error !== "" ? session.error : Tr.t("ออกจากระบบ")
            // เซสชันจริง: จบเซสชันทั้งหมดแล้ว greetd กลับหน้า Login (การ์ด 0004) · หน้าต่างพัฒนา: สลับหน้าในแอป
            onClicked: if (!session.active) AppState.go("login"); else session.logout()
        }
        Avatar {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            name: system.userName
            size: 40
            Layout.preferredWidth: 40
            Layout.preferredHeight: 40
            HoverHandler { id: who }
            ToolTip.visible: who.hovered
            ToolTip.text: system.userName + (AppState.devMode ? Tr.t(" · โหมดพัฒนา") : "")
        }
    }
    PowerDialog {
        id: powerDialog
        note: Tr.t("แชทและนัดบันทึกไว้แล้ว · งานในแอปอื่น (เช่น เอกสารที่ยังไม่บันทึก) จะหาย")
    }
}
