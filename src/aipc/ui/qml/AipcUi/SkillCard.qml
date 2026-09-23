// การ์ดคำตอบจากสกิล · รูปเดียวกันทุกสกิล ตรงกับบอร์ด "Skill ชุดแรก" บน canvas
// ข้อมูลทั้งหมด (info) มาจาก Python (skills.handle / skills.confirm) · การ์ดนี้แค่วาด
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    property var info: ({})
    property bool answered: false
    signal answer(bool yes)

    readonly property bool hasBadge: info.badge !== undefined && info.badge.name !== undefined
    implicitHeight: col.implicitHeight + 28
    radius: Theme.radiusLarge
    color: Theme.surface

    ColumnLayout {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 14
        spacing: 10

        RowLayout {
            visible: card.hasBadge
            Layout.fillWidth: true
            spacing: 8
            Chip { text: card.hasBadge ? "ใช้ Skill: " + card.info.badge.name : ""; iconPath: Icons.sparkle }
            AppText { text: card.hasBadge ? card.info.badge.reason : ""; size: Theme.fontSmall; color: Theme.inkMuted; oneLine: true; elide: Text.ElideRight; Layout.fillWidth: true }
            Chip { text: card.hasBadge ? card.info.badge.worker : "" }
        }

        AppText { text: card.info.title || ""; strong: true; Layout.fillWidth: true }

        Flow {
            Layout.fillWidth: true
            spacing: 8
            visible: (card.info.chips || []).length > 0
            Repeater {
                model: card.info.chips || []
                Chip { required property var modelData; text: modelData.text; kind: modelData.kind }
            }
        }

        Repeater {
            model: card.info.lines || []
            AppText {
                required property string modelData
                text: modelData
                size: Theme.fontSmall
                color: Theme.inkMuted
                Layout.fillWidth: true
            }
        }

        RowLayout {
            visible: (card.info.confirmToken || "") !== "" && !card.answered
            spacing: 8
            AppButton { text: "ใช่ ทำเลย"; onClicked: card.answer(true) }
            AppButton { text: "ไม่ใช่"; kind: "secondary"; onClicked: card.answer(false) }
        }
    }
}
