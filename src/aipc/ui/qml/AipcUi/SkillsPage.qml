// หน้า Skill · รายการจากไฟล์สกิลจริง ผ่าน skills.skills (สกิลในเครื่อง) และ skills.userSkills (สกิลที่ Claude สร้าง)
// บอกตรง ๆ ว่าสกิลไหนใช้ได้แล้ว และสกิลไหนยังขาดอะไร
// สกิลที่ Claude สร้าง (การ์ด 0017 ชั้นที่ 3): ดูขั้นตอน · เปิด/ปิด · ย้อนรุ่น · ลบ (กดสองครั้ง) · ที่มา (สร้างจากประโยคไหน)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: page
    spacing: 16
    property string confirmDelete: ""   // id ที่กดลบไปหนึ่งครั้ง (กดอีกครั้ง = ลบจริง)
    property string message: ""

    PageHeader {
        title: "Skill"
        subtitle: "AI เลือกสกิลเองจากรายการนี้ · สกิลเป็นข้อมูล ไม่ใช่โปรแกรม · ใช้ได้แค่สิทธิ์ที่แสดงไว้"
    }

    // ---------- สกิลที่ Claude สร้างให้ผู้ใช้คนนี้ ----------
    RowLayout {
        Layout.fillWidth: true
        AppText { text: "สกิลที่ Claude สร้างให้คุณ"; strong: true; size: Theme.px(17); Layout.fillWidth: true }
        Chip { text: skills.userSkills.length + " สกิล" }
    }
    AppText {
        objectName: "userSkillsEmpty"
        visible: skills.userSkills.length === 0
        Layout.fillWidth: true
        size: Theme.fontSmall; color: Theme.inkMuted
        text: skills.canForge
              ? "ยังไม่มี · สั่งงานใหม่ในแชท เช่น “เปิดโหมดทำงานให้หน่อย” แล้ว Claude จะสร้างสกิลให้ ครั้งหน้า AI ในเครื่องทำเองได้"
              : "ยังไม่มี · ต้องติดตั้งและเข้าสู่ระบบ Claude Code ในบัญชีนี้ก่อน จึงจะให้ Claude สร้างสกิลได้"
    }
    AppText {
        visible: page.message !== ""
        text: page.message
        Layout.fillWidth: true
        size: Theme.fontSmall; color: Theme.warnInk
    }
    GridLayout {
        objectName: "userSkillsGrid"
        Layout.fillWidth: true
        columns: 2
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: skills.userSkills
            Card {
                id: uc
                required property var modelData
                objectName: "userSkillCard"
                Layout.fillWidth: true
                Layout.preferredHeight: ucol.implicitHeight + 28
                Layout.alignment: Qt.AlignTop
                radius: Theme.radiusCard
                opacity: uc.modelData.enabled ? 1 : 0.72
                ColumnLayout {
                    id: ucol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        AppText { text: uc.modelData.name; strong: true; size: Theme.px(17); oneLine: true; Layout.fillWidth: true }
                        Chip { text: uc.modelData.enabled ? "เปิดอยู่" : "ปิดอยู่"; kind: uc.modelData.enabled ? "ok" : "neutral"; dot: true }
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Chip { text: (uc.modelData.imported ? "นำเข้าจากไฟล์" : "Claude สร้าง") + " · รุ่น " + uc.modelData.version; kind: "accent" }
                        Chip { text: "ใช้แล้ว " + uc.modelData.uses + " ครั้ง" }
                        Chip { visible: uc.modelData.created !== ""; text: uc.modelData.created }
                    }
                    Repeater {
                        model: uc.modelData.detail
                        AppText { required property string modelData; required property int index
                                  text: (uc.modelData.detail.length > 1 ? (index + 1) + ". " : "") + modelData
                                  size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                    }
                    AppText {
                        visible: uc.modelData.request !== ""
                        text: "สร้างจาก: “" + uc.modelData.request + "”"
                        size: Theme.fontCaption; color: Theme.inkFaint; Layout.fillWidth: true
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        AppButton {
                            text: uc.modelData.enabled ? "ปิด" : "เปิดใช้"; kind: "secondary"
                            onClicked: { page.message = ""; skills.setSkillEnabled(uc.modelData.id, !uc.modelData.enabled) }
                        }
                        AppButton {
                            // ย้อนไปรุ่นก่อนหน้าที่เก็บไว้ (รุ่นที่มีเลขน้อยกว่ารุ่นปัจจุบัน)
                            readonly property var older: uc.modelData.versions.filter(v => v < uc.modelData.version)
                            visible: older.length > 0
                            text: visible ? "ย้อนไปรุ่น " + older[older.length - 1] : ""
                            kind: "secondary"
                            onClicked: page.message = skills.revertSkill(uc.modelData.id, older[older.length - 1])
                        }
                        AppButton {
                            text: "ส่งออกเป็นไฟล์"; kind: "secondary"
                            onClicked: page.message = skills.exportSkill(uc.modelData.id)
                        }
                        AppButton {
                            objectName: "deleteSkillButton"
                            text: page.confirmDelete === uc.modelData.id ? "กดอีกครั้งเพื่อลบ" : "ลบ"
                            kind: page.confirmDelete === uc.modelData.id ? "danger" : "ghost"
                            onClicked: {
                                if (page.confirmDelete === uc.modelData.id) {
                                    page.confirmDelete = ""
                                    page.message = ""
                                    skills.removeSkill(uc.modelData.id)
                                } else {
                                    page.confirmDelete = uc.modelData.id
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ---------- สกิลในเครื่อง ----------
    AppText { text: "สกิลในเครื่อง"; strong: true; size: Theme.px(17); Layout.fillWidth: true }
    GridLayout {
        Layout.fillWidth: true
        columns: 2
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: skills.skills.filter(s => !s.byClaude)
            Card {
                id: sc
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: col.implicitHeight + 28
                Layout.alignment: Qt.AlignTop
                radius: Theme.radiusCard
                ColumnLayout {
                    id: col
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        AppText { text: sc.modelData.name; strong: true; size: Theme.px(17); oneLine: true; Layout.fillWidth: true }
                        Chip { text: sc.modelData.ready ? "ใช้ได้แล้ว" : "ยังไม่พร้อม"; kind: sc.modelData.ready ? "ok" : "neutral"; dot: true }
                    }
                    AppText { text: sc.modelData.description; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Chip { text: sc.modelData.worker }
                        Repeater { model: sc.modelData.permissions; Chip { required property string modelData; text: modelData; kind: "warn" } }
                    }
                    Repeater {
                        model: sc.modelData.missing
                        AppText { required property string modelData; text: "ต้องมีก่อน: " + modelData; size: Theme.fontCaption; color: Theme.inkFaint; Layout.fillWidth: true }
                    }
                }
            }
        }
    }
    Item { Layout.fillHeight: true }
}
