// แถบนำทางซ้าย · หกหน้าหลักตาม BRIEF 5.7 ข้อ 2 + กล่องผู้ใช้ด้านล่าง
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    implicitWidth: 232
    color: Theme.surface
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        anchors.topMargin: 16
        spacing: 4

        BrandMark { Layout.leftMargin: 8; Layout.bottomMargin: 12 }
        NavItem { text: "ผู้ช่วย AI"; iconPath: Icons.chat; pageName: "workspace" }
        NavItem { text: "ไฟล์ของฉัน"; iconPath: Icons.folder; pageName: "files" }
        NavItem { text: "Skill"; iconPath: Icons.sparkle; pageName: "skills" }
        NavItem { text: "ความเป็นส่วนตัว"; iconPath: Icons.shield; pageName: "privacy" }
        NavItem { text: "สุขภาพเครื่อง"; iconPath: Icons.activity; pageName: "health" }
        NavItem { text: "ตั้งค่า"; iconPath: Icons.sliders; pageName: "settings" }
        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: userCol.implicitHeight + 24
            radius: Theme.radiusCard
            color: Theme.bg
            ColumnLayout {
                id: userCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8
                RowLayout {
                    spacing: 10
                    Avatar { name: system.userName; size: 36 }
                    ColumnLayout {
                        spacing: 0
                        AppText { text: system.userName; strong: true; oneLine: true }
                        AppText { text: AppState.devMode ? "โหมดพัฒนา" : "ผู้ใช้ของเครื่องนี้"; size: Theme.fontSmall; color: Theme.inkMuted; oneLine: true }
                    }
                }
                RowLayout {
                    spacing: 6
                    AppButton {
                        Layout.fillWidth: true
                        text: "ปิดบัง"; kind: "secondary"; iconPath: Icons.eyeOff
                        enabled: false
                        ToolTip.visible: hovered
                        ToolTip.text: "ยังไม่พร้อม: ตัวปิดบังใช้ ext-session-lock (เฟส 2)"
                    }
                    AppButton {
                        Layout.fillWidth: true
                        text: "ออก"; kind: "secondary"; iconPath: Icons.logout
                        onClicked: AppState.go("login")
                    }
                }
            }
        }
    }
}
