// ขั้นตอนเชื่อมต่อ Claude (การ์ด 0021) · ใช้ทั้งหน้าผู้ช่วย (หน้าต่างกลางจอ) และหน้าตั้งค่า
// ข้อความมาจาก aipc.cloud.setup_guide ผ่าน cloudUsage.guideSteps (เรียก cloudUsage.refreshGuide() ก่อนเปิด)
// ไม่มีปุ่มคัดลอก: คำสั่งพิมพ์บนคอมพิวเตอร์อีกเครื่อง คลิปบอร์ดของเครื่องนี้ไม่ช่วย
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    spacing: 14
    Repeater {
        model: cloudUsage.guideSteps
        ColumnLayout {
            id: guideStep
            objectName: "claudeGuideStep"
            required property var modelData
            Layout.fillWidth: true
            spacing: 4
            AppText { text: guideStep.modelData.title; strong: true; Layout.fillWidth: true }
            AppText {
                text: guideStep.modelData.detail
                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
            }
            Rectangle {
                objectName: "claudeGuideCommand"
                visible: guideStep.modelData.command !== ""
                Layout.fillWidth: true
                Layout.topMargin: 2
                implicitHeight: cmdText.implicitHeight + 20
                radius: Theme.radiusControl
                color: Theme.surface2
                border.color: Theme.line
                AppText {
                    id: cmdText
                    anchors.fill: parent
                    anchors.margins: 10
                    font.family: Theme.mono
                    text: guideStep.modelData.command
                }
            }
        }
    }
}
