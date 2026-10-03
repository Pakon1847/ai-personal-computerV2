// การ์ดคำตอบจากสกิล · รูปเดียวกันทุกสกิล ตรงกับบอร์ด "Skill ชุดแรก" บน canvas
// ข้อมูลทั้งหมด (info) มาจาก Python (skills.handle / skills.confirm) · การ์ดนี้แค่วาด
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    property var info: ({})
    property bool answered: false
    property bool undone: false  // กดย้อนกลับไปแล้ว
    signal answer(bool yes)
    signal undo()  // คำสั่งที่ทำไปแล้ว (ปรับเสียง): คืนสภาพเดิม
    // สกิลที่ Claude สร้าง (การ์ด 0017 ชั้นที่ 2): ลบทิ้ง หรือบอกว่าผิดตรงไหนให้ Claude แก้
    signal removeSkill(string skillId)
    signal wrongSkill(string skillId, string name)
    signal askFile(string path)  // การ์ดผลค้นไฟล์: ส่งไฟล์ให้ AI ในเครื่อง
    signal summarizeFile(string path)  // แนบไฟล์แล้วสั่งสรุปทันที
    readonly property bool forged: hasBadge && (info.badge.forgedId || "") !== ""

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

        // ผลค้นไฟล์ (หาไฟล์ด้วยการพิมพ์ในแชท)
        Repeater {
            model: card.info.files || []
            RowLayout {
                id: fileRow
                required property var modelData
                objectName: "chatFileHit"
                Layout.fillWidth: true
                spacing: 8
                Icon { path: Icons.file; color: Theme.inkMuted }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    AppText { text: fileRow.modelData.name; strong: true; oneLine: true; elide: Text.ElideRight; Layout.fillWidth: true }
                    AppText { text: fileRow.modelData.folder + " · " + fileRow.modelData.snippet; size: Theme.fontCaption; color: Theme.inkMuted; oneLine: true; elide: Text.ElideRight; Layout.fillWidth: true }
                }
                AppButton { objectName: "summarizeFileButton"; text: "สรุป"; kind: "secondary"; onClicked: card.summarizeFile(fileRow.modelData.abs) }
                AppButton { text: "ถาม AI"; kind: "ghost"; onClicked: card.askFile(fileRow.modelData.abs) }
            }
        }

        RowLayout {
            visible: (card.info.confirmToken || "") !== "" && !card.answered
            spacing: 8
            AppButton { text: "ใช่ ทำเลย"; onClicked: card.answer(true) }
            AppButton { text: "ไม่ใช่"; kind: "secondary"; onClicked: card.answer(false) }
        }

        // ย้อนกลับ (ข้อเสนอ 2026-10-03): ถอดเสียงผิดจนทำคำสั่งผิด แก้คืนได้ในกดเดียว · เฉพาะคำสั่งล่าสุด
        AppButton {
            objectName: "undoButton"
            visible: (card.info.undoToken || "") !== "" && !card.undone
            text: "ย้อนกลับ"
            kind: "secondary"
            onClicked: card.undo()
        }

        WhyPanel { rows: card.info.why || []; Layout.fillWidth: true }

        RowLayout {
            objectName: "forgedRow"
            visible: card.forged
            Layout.fillWidth: true
            spacing: 8
            AppText {
                text: card.forged ? "สกิลที่ Claude สร้าง · รุ่น " + card.info.badge.forgedVersion : ""
                size: Theme.fontSmall; color: Theme.inkMuted; oneLine: true; Layout.fillWidth: true
            }
            AppButton {
                text: "ไม่ใช่แบบนี้"; kind: "ghost"
                onClicked: card.wrongSkill(card.info.badge.forgedId, card.info.badge.name)
            }
            AppButton {
                text: "ลบสกิลนี้"; kind: "ghost"
                onClicked: card.removeSkill(card.info.badge.forgedId)
            }
        }
    }
}
