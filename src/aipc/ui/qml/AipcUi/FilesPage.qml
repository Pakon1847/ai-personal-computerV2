// หน้าไฟล์ของฉัน · แสดงไฟล์จริงใน home แบบอ่านอย่างเดียว (ยังไม่มีเพิ่ม/ลบ/ถังขยะ)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: page
    spacing: 16
    property string pendingSkill: ""   // ไฟล์สกิลที่ตรวจแล้ว รอกดยืนยันติดตั้ง

    PageHeader {
        title: Tr.t("ไฟล์ของฉัน")
        subtitle: Tr.t("ไฟล์ในโฟลเดอร์ของคุณ · ค้นจากชื่อหรือข้อความในไฟล์ได้")
        AppText { text: filesBrowser.quotaText; color: Theme.inkMuted; oneLine: true }
    }

    // ค้นในเนื้อหาไฟล์ (txt md csv pdf) · ทำในเครื่อง ไม่ใช้ AI · ผล docs/benchmarks/2026-10-01-file-search
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        AppField {
            id: searchBox
            objectName: "fileSearchBox"
            Layout.fillWidth: true
            placeholder: Tr.t("ค้นในเนื้อหาไฟล์ เช่น ใบเสร็จซ่อมแอร์ · ค่าเทอมลูก")
            field.onAccepted: filesBrowser.search(text)
        }
        AppButton { objectName: "fileSearchButton"; text: Tr.t("ค้น"); iconPath: Icons.search; kind: "primary"; onClicked: filesBrowser.search(searchBox.text) }
        AppButton {
            visible: filesBrowser.searchResults.length > 0 || filesBrowser.searchNote !== ""
            text: Tr.t("ล้าง"); kind: "ghost"
            onClicked: { searchBox.text = ""; filesBrowser.search("") }
        }
    }
    AppText { objectName: "fileSearchNote"; visible: filesBrowser.searchNote !== ""; text: filesBrowser.searchNote; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
    Card {
        objectName: "fileSearchResults"
        visible: filesBrowser.searchResults.length > 0
        Layout.fillWidth: true
        implicitHeight: resultCol.implicitHeight + 24
        radius: Theme.radiusCard
        ColumnLayout {
            id: resultCol
            anchors.fill: parent
            anchors.margins: 12
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            spacing: 6
            Repeater {
                model: filesBrowser.searchResults
                delegate: RowLayout {
                    id: hit
                    required property var modelData
                    objectName: "fileSearchHit"
                    Layout.fillWidth: true
                    spacing: 12
                    Icon { path: Icons.file; color: Theme.inkMuted }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        AppText { text: hit.modelData.name; strong: true; oneLine: true; elide: Text.ElideRight; Layout.fillWidth: true }
                        AppText { text: hit.modelData.folder; size: Theme.fontCaption; color: Theme.inkMuted; oneLine: true; Layout.fillWidth: true }
                        AppText { text: hit.modelData.snippet; size: Theme.fontSmall; color: Theme.inkMuted; oneLine: true; elide: Text.ElideRight; Layout.fillWidth: true }
                    }
                    AppButton {
                        text: Tr.t("ถาม AI"); kind: "secondary"; iconPath: Icons.chat
                        onClicked: {
                            const err = chat.attachFile(filesBrowser.resultPath(hit.modelData.path))
                            if (err === "") AppState.page = "workspace"
                            else fileError.text = err
                        }
                    }
                    AppButton { text: Tr.t("เปิดโฟลเดอร์"); kind: "ghost"; onClicked: filesBrowser.openFolderOf(hit.modelData.path) }
                }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        AppButton { text: Tr.t("ขึ้นไป"); kind: "secondary"; iconPath: Icons.back; enabled: filesBrowser.canGoUp; onClicked: filesBrowser.up() }
        AppText { text: filesBrowser.location; strong: true; oneLine: true; Layout.fillWidth: true; elide: Text.ElideMiddle }
    }

    AppText { visible: filesBrowser.error !== ""; text: filesBrowser.error; color: Theme.danger; Layout.fillWidth: true }
    AppText { id: fileError; objectName: "fileError"; visible: text !== ""; color: Theme.danger; Layout.fillWidth: true }

    Card {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: 0
        radius: Theme.radiusCard
        RowLayout {
            id: tableHead
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 12
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            AppText { text: Tr.t("ชื่อ"); size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true; oneLine: true }
            AppText { text: Tr.t("แก้ไขล่าสุด", "หัวตาราง"); size: Theme.fontSmall; color: Theme.inkMuted; Layout.preferredWidth: 180; oneLine: true }
            AppText { text: Tr.t("ขนาด"); size: Theme.fontSmall; color: Theme.inkMuted; Layout.preferredWidth: 100; oneLine: true }
        }
        Rectangle { id: headLine; anchors.top: tableHead.bottom; anchors.topMargin: 12; width: parent.width; height: 1; color: Theme.line }
            // ยึดขอบกับการ์ดตรง ๆ: รายการยาวแค่ไหนก็อยู่ในการ์ด แล้วเลื่อนดูส่วนที่เกิน
            ListView {
                anchors.top: headLine.bottom
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottomMargin: 8
                clip: true
                model: filesBrowser.entries
                ScrollBar.vertical: ScrollBar {}
                delegate: ItemDelegate {
                    id: row
                    required property var modelData
                    width: ListView.view.width
                    height: Theme.touch + 4
                    onClicked: if (modelData.is_dir) filesBrowser.open(modelData.name)
                    background: Rectangle { color: row.hovered ? Theme.surface2 : "transparent" }
                    contentItem: RowLayout {
                        spacing: 12
                        Item { width: 8 }
                        Icon { path: row.modelData.is_dir ? Icons.folder : Icons.file; color: row.modelData.is_dir ? Theme.accent : Theme.inkMuted }
                        AppText { text: row.modelData.name; oneLine: true; elide: Text.ElideRight; Layout.fillWidth: true }
                        AppText { text: row.modelData.modified_text; color: Theme.inkMuted; oneLine: true; Layout.preferredWidth: 180 }
                        AppText { text: row.modelData.size_text; color: Theme.inkMuted; oneLine: true; Layout.preferredWidth: 100 }
                        // ถาม AI ในเครื่องเกี่ยวกับไฟล์นี้ (ฟีเจอร์ข้อ 4) · เนื้อหาไม่ออกนอกเครื่อง
                        AppButton {
                            objectName: "askFileButton"
                            visible: row.modelData.askable === true
                            text: Tr.t("ถาม AI"); kind: "secondary"; iconPath: Icons.chat
                            onClicked: {
                                const err = chat.attachFile(filesBrowser.pathOf(row.modelData.name))
                                if (err === "") AppState.page = "workspace"
                                else fileError.text = err
                            }
                        }
                        // ไฟล์สกิล .md จากภายนอก (ฟีเจอร์ข้อ 9): กดแรก = ตรวจและบอกว่าทำอะไร · กดอีกครั้ง = ติดตั้ง
                        AppButton {
                            objectName: "installSkillButton"
                            visible: !row.modelData.is_dir && row.modelData.name.toLowerCase().endsWith(".md")
                            text: page.pendingSkill === row.modelData.name ? Tr.t("ยืนยันติดตั้ง") : Tr.t("ติดตั้งเป็นสกิล")
                            kind: page.pendingSkill === row.modelData.name ? "primary" : "secondary"
                            onClicked: {
                                const path = filesBrowser.pathOf(row.modelData.name)
                                const install = page.pendingSkill === row.modelData.name
                                const msg = skills.importSkill(path, install)
                                page.pendingSkill = (!install && msg.indexOf("กดอีกครั้ง") >= 0) ? row.modelData.name : ""
                                fileError.text = msg
                            }
                        }
                        Item { width: 4 }
                    }
                }
            }
    }
}
