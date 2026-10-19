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
    property string filter: "all"       // ตัวกรองสกิลในเครื่อง: all | ready | notReady (การ์ด 0041)
    property string openId: ""          // ไทล์ที่แตะเปิดดูรายละเอียดอยู่
    readonly property var localSkills: skills.skills.filter(s => !s.byClaude)
    // ไอคอนของสกิลในเครื่อง (ไอคอนเส้นชุดเดิม) · สกิลอื่น = ประกาย
    readonly property var icons: ({
        "reminder": Icons.calendar, "system-command": Icons.terminal, "machine-status": Icons.activity,
        "letter-writer": Icons.mail, "summarize-text": Icons.file, "translate": Icons.globe
    })

    PageHeader {
        title: "Skill"
        subtitle: Tr.t("AI เลือกสกิลเองจากรายการนี้ · สกิลเป็นข้อมูล ไม่ใช่โปรแกรม · ใช้ได้แค่สิทธิ์ที่แสดงไว้")
    }

    // ---------- สกิลที่ Claude สร้างให้ผู้ใช้คนนี้ ----------
    RowLayout {
        Layout.fillWidth: true
        AppText { text: Tr.t("สกิลที่ Claude สร้างให้คุณ"); strong: true; size: Theme.px(17); Layout.fillWidth: true }
        Chip { text: skills.userSkills.length + Tr.t(" สกิล") }
    }
    AppText {
        objectName: "userSkillsEmpty"
        visible: skills.userSkills.length === 0
        Layout.fillWidth: true
        size: Theme.fontSmall; color: Theme.inkMuted
        text: skills.canForge
              ? Tr.t("ยังไม่มี · สั่งงานใหม่ในแชท เช่น “เปิดโหมดทำงานให้หน่อย” แล้ว Claude จะสร้างสกิลให้ ครั้งหน้า AI ในเครื่องทำเองได้")
              : Tr.t("ยังไม่มี · ต้องติดตั้งและเข้าสู่ระบบ Claude Code ในบัญชีนี้ก่อน จึงจะให้ Claude สร้างสกิลได้ · ดูวิธีที่หน้าผู้ช่วย › \"ดูวิธีเชื่อมต่อ\"")
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
                        Chip { text: uc.modelData.enabled ? Tr.t("เปิดอยู่") : Tr.t("ปิดอยู่"); kind: uc.modelData.enabled ? "ok" : "neutral"; dot: true }
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Chip { text: (uc.modelData.imported ? Tr.t("นำเข้าจากไฟล์") : Tr.t("Claude สร้าง")) + Tr.t(" · รุ่น ") + uc.modelData.version; kind: "accent" }
                        Chip { text: Tr.t("ใช้แล้ว ") + uc.modelData.uses + Tr.t(" ครั้ง") }
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
                        text: Tr.t("สร้างจาก: “") + uc.modelData.request + "”"
                        size: Theme.fontCaption; color: Theme.inkFaint; Layout.fillWidth: true
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        AppButton {
                            text: uc.modelData.enabled ? Tr.t("ปิด") : Tr.t("เปิดใช้"); kind: "secondary"
                            onClicked: { page.message = ""; skills.setSkillEnabled(uc.modelData.id, !uc.modelData.enabled) }
                        }
                        AppButton {
                            // ย้อนไปรุ่นก่อนหน้าที่เก็บไว้ (รุ่นที่มีเลขน้อยกว่ารุ่นปัจจุบัน)
                            readonly property var older: uc.modelData.versions.filter(v => v < uc.modelData.version)
                            visible: older.length > 0
                            text: visible ? Tr.t("ย้อนไปรุ่น ") + older[older.length - 1] : ""
                            kind: "secondary"
                            onClicked: page.message = skills.revertSkill(uc.modelData.id, older[older.length - 1])
                        }
                        AppButton {
                            text: Tr.t("ส่งออกเป็นไฟล์"); kind: "secondary"
                            onClicked: page.message = skills.exportSkill(uc.modelData.id)
                        }
                        AppButton {
                            objectName: "deleteSkillButton"
                            text: page.confirmDelete === uc.modelData.id ? Tr.t("กดอีกครั้งเพื่อลบ") : Tr.t("ลบ")
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

    // ---------- สกิลในเครื่อง (การ์ด 0041): ไทล์ ไอคอน · ชื่อ · ตัวอย่างคำพูด · จุดพร้อม/ไม่พร้อม · แตะ = ดูรายละเอียดและสิทธิ์ ----------
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        AppText { text: Tr.t("สกิลในเครื่อง"); strong: true; size: Theme.px(17); Layout.fillWidth: true }
        // ตัวกรองมีคำกำกับ (ไม่ใช้สีอย่างเดียวบอกสถานะ)
        Repeater {
            model: [
                { key: "all", label: Tr.t("ทั้งหมด") },
                { key: "ready", label: Tr.t("ใช้ได้แล้ว") },
                { key: "notReady", label: Tr.t("ยังไม่พร้อม") }
            ]
            AppButton {
                required property var modelData
                objectName: "skillFilter_" + modelData.key
                readonly property int count: page.localSkills.filter(s => modelData.key === "all" || (modelData.key === "ready") === s.ready).length
                kind: page.filter === modelData.key ? "primary" : "secondary"
                text: modelData.label + " " + count
                onClicked: { page.filter = modelData.key; page.openId = "" }
            }
        }
    }
    GridLayout {
        objectName: "localSkillsGrid"
        Layout.fillWidth: true
        columns: Theme.fontScale > 1.25 ? 1 : page.width >= 900 ? 3 : 2
        columnSpacing: 14
        rowSpacing: 14
        Repeater {
            model: page.localSkills.filter(s => page.filter === "all" || (page.filter === "ready") === s.ready)
            Button {
                id: sc
                required property var modelData
                objectName: "skillTile"
                readonly property bool open: page.openId === modelData.id
                Layout.fillWidth: true
                Layout.preferredWidth: 1   // ทุกคอลัมน์กว้างเท่ากัน (ไม่ขึ้นกับความยาวข้อความ)
                Layout.alignment: Qt.AlignTop
                // แตะเปิดแล้วกินเต็มแถว (รายละเอียดอ่านง่าย ไม่เบียดไทล์ข้าง ๆ)
                Layout.columnSpan: open ? parent.columns : 1
                hoverEnabled: true
                padding: 16
                implicitHeight: col.implicitHeight + 2 * padding
                Accessible.name: modelData.name + " · " + (modelData.ready ? Tr.t("ใช้ได้แล้ว") : Tr.t("ยังไม่พร้อม"))
                Keys.onReturnPressed: (event) => { sc.clicked(); event.accepted = true }
                onClicked: page.openId = open ? "" : modelData.id
                background: Rectangle {
                    radius: Theme.radiusLarge
                    color: Theme.surface
                    border.width: sc.visualFocus ? 2 : (sc.hovered || sc.open) ? 1 : 0
                    border.color: Theme.accent
                }
                contentItem: ColumnLayout {
                    id: col
                    spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Rectangle {
                            implicitWidth: 40; implicitHeight: 40; radius: 12
                            color: sc.modelData.ready ? Theme.accentSoft : Theme.surface2
                            Icon {
                                anchors.centerIn: parent
                                path: page.icons[sc.modelData.id] || Icons.sparkle
                                color: sc.modelData.ready ? Theme.accentInk : Theme.inkFaint
                                width: 20; height: 20
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Chip {
                            objectName: "skillReady"
                            text: sc.modelData.ready ? Tr.t("ใช้ได้แล้ว") : Tr.t("ยังไม่พร้อม")
                            kind: sc.modelData.ready ? "ok" : "neutral"; dot: true
                        }
                    }
                    AppText { text: sc.modelData.name; strong: true; size: Theme.px(17); Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                    // ตัวอย่างคำพูดจากไฟล์สกิลจริง · ยังไม่พร้อม = บอกสิ่งที่ขาดแทน (H5)
                    AppText {
                        Layout.fillWidth: true
                        size: Theme.fontSmall
                        color: sc.modelData.ready ? Theme.inkMuted : Theme.inkFaint
                        maximumLineCount: sc.open ? 4 : 2; elide: Text.ElideRight
                        text: !sc.modelData.ready ? Tr.t("ต้องมีก่อน: ") + sc.modelData.missing.join(", ")
                              : sc.modelData.examples.length ? sc.modelData.examples.map(e => "“" + e + "”").join("  ")
                              : Tr.t("แตะเพื่อดูรายละเอียด")
                    }
                    // รายละเอียด (แตะแล้วเปิด): ทำอะไร · ใครทำ (โค้ด/LLM) · สิทธิ์ที่ใช้
                    ColumnLayout {
                        objectName: "skillDetail"
                        visible: sc.open
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        spacing: 8
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.line }
                        AppText { text: sc.modelData.description; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 6
                            Chip { text: sc.modelData.worker }
                            Repeater { model: sc.modelData.permissions; Chip { required property string modelData; text: modelData; kind: "warn" } }
                        }
                    }
                }
            }
        }
    }
    Item { Layout.fillHeight: true }
}
