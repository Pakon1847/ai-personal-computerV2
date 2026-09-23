// หน้าผู้ช่วย AI (BRIEF 5.4) · ช่องพิมพ์ทำงานจริงตามข้อ 7:
//   Enter = ส่ง · Shift+Enter = ขึ้นบรรทัดใหม่ · ไม่ส่งขณะ IME กำลังประกอบคำ
// ยังไม่มีโมเดลในเครื่อง (llama-server, เฟส 1) ข้อความที่ส่งจึงได้คำตอบเป็น "ประกาศจากระบบ"
// ที่บอกเหตุผล ไม่ใช่คำตอบปลอมของ AI · ข้อความยังไม่ถูกบันทึกที่ไหน
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

RowLayout {
    id: root
    spacing: 0

    ListModel { id: messages }

    function send() {
        const text = input.text.trim()
        if (text === "") return
        messages.append({ fromUser: true, body: text })
        messages.append({ fromUser: false, body: "ยังตอบไม่ได้: ยังไม่ได้เชื่อมต่อโมเดลในเครื่อง (llama-server อยู่ในเฟส 1) · ข้อความนี้ไม่ได้ถูกส่งไปที่ไหน" })
        input.text = ""
        list.positionViewAtEnd()
    }

    // ---------- รายการบทสนทนา ----------
    Rectangle {
        Layout.preferredWidth: 264
        Layout.fillHeight: true
        color: Theme.surface2
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            anchors.topMargin: 16
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                AppText { text: "บทสนทนา"; size: Theme.px(18); strong: true; Layout.fillWidth: true }
                AppButton { text: "แชทใหม่"; kind: "outline"; iconPath: Icons.plus; onClicked: messages.clear() }
            }
            AppText {
                Layout.fillWidth: true
                text: "ยังไม่มีบทสนทนาที่บันทึกไว้ · การบันทึกประวัติมาพร้อมฐานข้อมูลในเฟส 1"
                size: Theme.fontSmall
                color: Theme.inkMuted
            }
            Item { Layout.fillHeight: true }
        }
    }

    // ---------- แชท ----------
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        color: Theme.surface

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 64
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 12
                AppText { text: messages.count > 0 ? "แชทใหม่" : "ผู้ช่วย AI"; size: Theme.fontHeading; strong: true; Layout.fillWidth: true }
                Chip { text: "ยังไม่ได้เชื่อมต่อโมเดล"; iconPath: Icons.cpu; kind: "neutral" }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                NotReady {
                    visible: messages.count === 0
                    anchors.centerIn: parent
                    width: 520
                    title: "แชทกับโมเดลในเครื่องยังไม่พร้อม"
                    detail: "ช่องพิมพ์ด้านล่างใช้งานได้แล้ว (Enter ส่ง · Shift+Enter ขึ้นบรรทัดใหม่) แต่ยังไม่มีโมเดลตอบ · โมเดลภาษาไทยจะเลือกจากผลวัดบน Pi 5 (ADR-007)"
                }

                ListView {
                    id: list
                    objectName: "chatList"
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 16
                    clip: true
                    model: messages
                    delegate: Item {
                        required property bool fromUser
                        required property string body
                        width: ListView.view.width
                        height: bubble.height
                        Rectangle {
                            id: bubble
                            anchors.right: parent.fromUser ? parent.right : undefined
                            width: Math.min(bodyText.implicitWidth + 32, parent.width * 0.75)
                            height: bodyText.implicitHeight + 24
                            radius: Theme.radiusCard
                            color: parent.fromUser ? Theme.accentSoft : Theme.surface2
                            border.width: parent.fromUser ? 0 : 1
                            border.color: Theme.lineStrong
                            AppText {
                                id: bodyText
                                x: 16; y: 12
                                width: parent.width - 32
                                text: parent.parent.body
                                color: parent.parent.fromUser ? Theme.bubbleInk : Theme.inkMuted
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: 16
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 8
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: Math.min(160, Math.max(60, input.implicitHeight + 16))
                    radius: Theme.radiusCard
                    color: Theme.surface
                    border.width: input.activeFocus ? 2 : 1
                    border.color: input.activeFocus ? Theme.accent : Theme.lineStrong
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8
                        AppButton {
                            kind: "ghost"; iconPath: Icons.clip; enabled: false
                            Accessible.name: "แนบไฟล์"
                            ToolTip.visible: hovered; ToolTip.text: "แนบไฟล์: ยังไม่พร้อม"
                        }
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            TextArea {
                                id: input
                                objectName: "chatInput"
                                placeholderText: "พิมพ์ข้อความถึงผู้ช่วย AI"
                                placeholderTextColor: Theme.inkFaint
                                color: Theme.ink
                                font.family: Theme.family
                                font.pixelSize: Theme.fontBody
                                wrapMode: TextEdit.Wrap
                                background: null
                                Accessible.name: "ข้อความ"
                                Keys.onPressed: (event) => {
                                    const enter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                                    // inputMethodComposing = กำลังพิมพ์ผ่าน IME และคำยังไม่เสร็จ → ห้ามส่ง
                                    if (enter && !(event.modifiers & Qt.ShiftModifier) && !input.inputMethodComposing) {
                                        event.accepted = true
                                        root.send()
                                    }
                                }
                            }
                        }
                        AppButton {
                            kind: "secondary"; iconPath: Icons.mic; enabled: false
                            Accessible.name: "พูดกับ AI"
                            ToolTip.visible: hovered; ToolTip.text: "พูดด้วยเสียง: ยังไม่พร้อม (เฟส 3)"
                        }
                        AppButton { text: "ส่ง"; iconPath: Icons.send; enabled: input.text.trim() !== ""; onClicked: root.send() }
                    }
                }
                AppText { text: "Enter ส่ง · Shift+Enter ขึ้นบรรทัดใหม่"; size: Theme.fontCaption; color: Theme.inkFaint; oneLine: true }
            }
        }
    }
}
