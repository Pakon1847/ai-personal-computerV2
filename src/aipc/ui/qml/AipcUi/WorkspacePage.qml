// หน้าผู้ช่วย AI (BRIEF 5.4) · ช่องพิมพ์ทำงานจริงตามข้อ 7:
//   Enter = ส่ง · Shift+Enter = ขึ้นบรรทัดใหม่ · ไม่ส่งขณะ IME กำลังประกอบคำ
// ข้อความทุกอันผ่านตัวเลือกสกิล (skills.handle ใน Python) แล้วได้ "การ์ดคำตอบ" กลับมา
// สกิลที่โค้ดทำงานหลัก (สั่งงานเครื่อง, ถามเครื่อง) ใช้ได้จริงแล้ว · ที่ต้องใช้โมเดลบอกว่ายังขาดอะไร
// ยังไม่มีโมเดลในเครื่อง ข้อความคุยทั่วไปจึงได้ประกาศจากระบบ ไม่ใช่คำตอบปลอมของ AI · ยังไม่บันทึกประวัติ
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

RowLayout {
    id: root
    spacing: 0

    // รายการข้อความเป็น JS array ธรรมดา: { user: true, text } หรือ { user: false, card }
    property var items: []
    property var answered: ({})   // token ของการ์ดที่ตอบ "ใช่/ไม่ใช่" ไปแล้ว

    function push(item) {
        items = items.concat([item])
    }
    function showCard(card) {
        push({ user: false, card: card })
        if (card.page) AppState.page = card.page   // เช่น "เปิดหน้าตั้งค่า"
    }
    function send() {
        const text = input.text.trim()
        if (text === "") return
        push({ user: true, text: text })
        input.text = ""
        showCard(skills.handle(text))
    }
    function answer(token, yes) {
        const a = Object.assign({}, answered)
        a[token] = true
        answered = a
        showCard(skills.confirm(token, yes))
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
                AppButton { text: "แชทใหม่"; kind: "outline"; iconPath: Icons.plus; onClicked: { root.items = []; root.answered = ({}) } }
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
                AppText { text: root.items.length > 0 ? "แชทใหม่" : "ผู้ช่วย AI"; size: Theme.fontHeading; strong: true; Layout.fillWidth: true }
                Chip { text: "ยังไม่ได้เชื่อมต่อโมเดล"; iconPath: Icons.cpu; kind: "neutral" }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }

            // นัดที่พลาดขณะปิดเครื่อง/ไม่ได้เข้าใช้ และคำเตือนเรื่องไฟล์/นาฬิกา (การ์ด 0001, H2)
            Rectangle {
                id: notice
                property bool dismissed: false
                readonly property string missedText: skills.missed.length === 0 ? ""
                    : "พลาดการเตือน " + skills.missed.length + " รายการขณะไม่ได้ใช้เครื่อง: "
                      + skills.missed.map(r => r.what + " (" + r.when + ")").join(" · ")
                readonly property string message: [missedText, skills.reminderWarning].filter(t => t !== "").join("\n")
                visible: message !== "" && !dismissed
                Layout.fillWidth: true
                Layout.margins: 12
                Layout.bottomMargin: 0
                implicitHeight: noticeRow.implicitHeight + 20
                radius: Theme.radiusCard
                color: Theme.warnSoft
                RowLayout {
                    id: noticeRow
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10
                    Icon { path: Icons.alert; color: Theme.warnInk; Layout.alignment: Qt.AlignTop }
                    AppText { text: notice.message; color: Theme.warnInk; size: Theme.fontSmall; Layout.fillWidth: true }
                    AppButton { text: "รับทราบ"; kind: "secondary"; onClicked: notice.dismissed = true }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true   // ตัดส่วนที่เลื่อนพ้นกรอบ รวมไอคอนแบบ Shape ที่ ListView ตัดเองไม่หมด

                NotReady {
                    visible: root.items.length === 0
                    anchors.centerIn: parent
                    width: 560
                    title: "ยังไม่มีโมเดลภาษา แต่สกิลที่โค้ดทำงานหลักใช้ได้แล้ว"
                    detail: "ลองพิมพ์: “เปิดยูทูบ” · “ปรับเสียงสี่สิบ” · “ทำไมเครื่องช้า” · “เตือนส่งรายงานพรุ่งนี้บ่ายสอง” — การคุยทั่วไปและการแปล รอโมเดลในเครื่อง (ADR-007)"
                }

                ListView {
                    id: list
                    objectName: "chatList"
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 16
                    clip: true
                    model: root.items
                    // ความสูงของการ์ดรู้หลังวาดเสร็จ จึงเลื่อนลงล่างสุดทุกครั้งที่เนื้อหายาวขึ้น
                    onContentHeightChanged: positionViewAtEnd()
                    delegate: Item {
                        id: row
                        required property var modelData
                        width: ListView.view.width
                        height: modelData.user ? bubble.height : card.height

                        Rectangle {
                            id: bubble
                            visible: row.modelData.user
                            anchors.right: parent.right
                            width: Math.min(bodyText.implicitWidth + 32, parent.width * 0.75)
                            height: bodyText.implicitHeight + 24
                            radius: Theme.radiusCard
                            color: Theme.accentSoft
                            AppText {
                                id: bodyText
                                x: 16; y: 12
                                width: parent.width - 32
                                text: row.modelData.text || ""
                                color: Theme.bubbleInk
                            }
                        }
                        SkillCard {
                            id: card
                            visible: !row.modelData.user
                            width: Math.min(640, parent.width)
                            height: visible ? implicitHeight : 0
                            info: row.modelData.card || ({})
                            answered: !!root.answered[(row.modelData.card || {}).confirmToken]
                            onAnswer: (yes) => root.answer(row.modelData.card.confirmToken, yes)
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
