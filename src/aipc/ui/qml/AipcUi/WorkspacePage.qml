// หน้าผู้ช่วย AI (BRIEF 5.4 · หน้าตาตามการ์ด 0002) · ช่องพิมพ์ทำงานจริงตามข้อ 7:
//   Enter = ส่ง · Shift+Enter = ขึ้นบรรทัดใหม่ · ไม่ส่งขณะ IME กำลังประกอบคำ
// ยังไม่มีข้อความ = หน้าแรก: คำทัก + ช่องพิมพ์กลางจอ + ปุ่มลัดสกิลที่ใช้ได้จริง + นัดถัดไป + สถานะเครื่อง
// มีข้อความแล้ว = แชท: คอลัมน์กลางกว้างไม่เกิน 760 px ช่องพิมพ์ย้ายลงล่าง (ช่องเดียวกัน ไม่ใช่สองช่อง)
// ข้อความทุกอันผ่านตัวเลือกสกิล (skills.handle ใน Python) แล้วได้ "การ์ดคำตอบ" กลับมา
// ข้อความที่ไม่ตรงสกิลใด (และสกิลแปล) ส่งให้ LLM ในเครื่อง (chat · การ์ด 0013) คำตอบขึ้นทีละคำ หยุดได้ด้วยปุ่ม/Esc
// AI ไม่พร้อม = ประกาศจากระบบตามจริง ไม่ใช่คำตอบปลอม · ประวัติบันทึกใน home (ยกเว้นแชทชั่วคราว)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    objectName: "workspace"
    id: root
    clip: true   // ตัดส่วนที่เลื่อนพ้นกรอบ รวมไอคอนแบบ Shape ที่ ListView ตัดเองไม่หมด

    // รายการข้อความเป็น JS array ธรรมดา: { user: true, text } · { user: false, card } · { ai: true, text, note, done }
    property var items: []
    property var answered: ({})   // token ของการ์ดที่ตอบ "ใช่/ไม่ใช่" ไปแล้ว
    // กด "ไม่ใช่แบบนี้" ที่สกิลที่ Claude สร้าง → ข้อความถัดไปคือคำติ ส่งให้ Claude แก้สกิล (การ์ด 0017) · null = แชทปกติ
    property var feedbackFor: null
    property int copiedRow: -1    // คำตอบ AI ที่เพิ่งกดคัดลอก (ปุ่มขึ้นว่า "คัดลอกแล้ว")
    readonly property bool home: items.length === 0
    readonly property int colWidth: Math.min(760, width - 48)

    // ตัวอย่างประโยคของสกิลที่โค้ดทำงานได้แล้ว · สกิลที่ยังไม่พร้อมแสดงชื่อพร้อมคำว่า "ยังไม่พร้อม"
    readonly property var examples: ({
        "system-command": "เปิดยูทูบ",
        "machine-status": "ทำไมเครื่องช้า",
        "reminder": "เตือนส่งรายงานพรุ่งนี้บ่ายสอง"
    })

    function push(item) {
        items = items.concat([item])
    }
    function showCard(card) {
        push({ user: false, card: card })
        if (card.page) AppState.page = card.page   // เช่น "เปิดหน้าตั้งค่า"
    }
    function send() {
        const text = input.text.trim()
        if (text === "" || chat.busy) return
        push({ user: true, text: text })
        input.text = ""
        if (chat.attachedFile !== "") {  // ถามเกี่ยวกับไฟล์: ตรงไป AI ในเครื่อง ไม่ผ่านสกิล (ฟีเจอร์ข้อ 4)
            if (chat.send(text, "", false))
                push({ ai: true, text: "", note: "", done: false, skill: "ไฟล์ " + chat.attachedFile })
            return
        }
        if (feedbackFor) {
            const id = feedbackFor.id
            feedbackFor = null
            showCard(skills.reviseSkill(id, text, ""))
            return
        }
        dispatch(skills.handle(text), text)
    }
    // การ์ดจากสกิล → แสดง และ/หรือส่งให้ AI ในเครื่อง · ใช้ทั้งตอนผู้ใช้พิมพ์ และตอน AI เลือกสกิลให้ (skillRequested)
    function dispatch(card, text) {
        const toAi = card.llm === true && chat.send(text, card.prompt || "", card.tools !== false)
        if (card.llm && !toAi)
            card.title = "ยังตอบไม่ได้: " + chat.statusText   // สถานะเปลี่ยนระหว่างทาง · บอกตามจริง
        // สกิลแบบขั้นตอนเห็นการ์ดขั้นตอนเสมอ แม้ขั้นสุดท้ายจะส่งต่อให้ AI
        if (!toAi || card.kind === "steps")
            showCard(card)
        if (toAi)
            push({ ai: true, text: "", note: "", done: false, skill: (card.badge || {}).name || "" })
    }
    function loadChat(messages) {
        items = messages.map(m => m.role === "user" ? { user: true, text: m.shown || m.content }
                                                    : { ai: true, text: m.content, note: "", done: true })
        answered = ({})
    }
    Connections {
        target: chat
        // AI ในเครื่องเลือกสกิล (อาจารย์ขอ · งานข้อ ④): เอาฟองคำตอบที่รออยู่ออก แล้วทำทางเดียวกับที่กฎเลือก
        function onSkillRequested(skillId, text) {
            const i = root.items.slice()
            if (i.length > 0 && i[i.length - 1].ai && !i[i.length - 1].done)
                i.pop()
            root.items = i
            root.dispatch(skills.handleAs(skillId, text), text)
        }
        function onFinished(text, note) {
            const i = root.items.slice()
            if (i.length === 0 || !i[i.length - 1].ai) return
            i[i.length - 1] = Object.assign({}, i[i.length - 1], { text: text, note: note, done: true })
            root.items = i
        }
    }
    // สกิลอัตโนมัติ (การ์ด 0017): Claude สร้าง/แก้เสร็จ → ทำงานนั้นทันที · ไม่สำเร็จ = ให้ Claude ตอบคำขอนี้แทน
    Connections {
        target: skills
        function onForgeDone(card, text) {
            if (card.fallback === true) {
                root.showCard(card)
                if (chat.askCloudFor(text))
                    root.push({ ai: true, text: "", note: "", done: false, skill: "" })
                return
            }
            root.dispatch(card, text)
        }
    }
    function sendText(text) {
        input.text = text
        send()
    }
    function answer(token, yes) {
        const a = Object.assign({}, answered)
        a[token] = true
        answered = a
        const card = skills.confirm(token, yes)
        showCard(card)
        // สกิลแบบขั้นตอนที่จบด้วย "ถาม AI:" · ส่งข้อความเดิมของผู้ใช้ให้ AI พร้อมคำสั่งของขั้นนั้น
        if (card.llm && card.llmText && chat.send(card.llmText, card.prompt || ""))
            push({ ai: true, text: "", note: "", done: false, skill: (card.badge || {}).name || "" })
    }

    // ---------- ปุ่มมุมขวาบน ----------
    RowLayout {
        id: tools
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: 24
        spacing: 8
        AppButton {
            id: historyButton
            text: "ประวัติ"; kind: "secondary"; iconPath: Icons.chat
            onClicked: historyPopup.open()
        }
        AppButton {
            visible: !root.home
            text: "แชทใหม่"; kind: "secondary"; iconPath: Icons.plus
            onClicked: { chat.newChat(false); root.items = []; root.answered = ({}) }
        }
        AppButton {
            text: chat.temporary ? "แชทชั่วคราว ✓" : "แชทชั่วคราว"; kind: "secondary"
            ToolTip.visible: hovered; ToolTip.text: "ไม่บันทึกประวัติของบทสนทนานี้"
            onClicked: { chat.newChat(!chat.temporary); root.items = []; root.answered = ({}) }
        }
    }
    Popup {
        id: historyPopup
        x: root.width - width - 24
        y: tools.y + tools.height + 8
        width: 320
        padding: 16
        background: Rectangle { radius: Theme.radiusLarge; color: Theme.surface; border.width: 1; border.color: Theme.line }
        contentItem: ColumnLayout {
            spacing: 6
            AppText { text: "ประวัติบทสนทนา"; strong: true }
            AppText {
                Layout.fillWidth: true
                visible: chat.history.length === 0
                text: "ยังไม่มีบทสนทนาที่บันทึกไว้"
                size: Theme.fontSmall; color: Theme.inkMuted
            }
            Repeater {
                model: chat.history.slice(0, 12)
                AppButton {
                    required property var modelData
                    Layout.fillWidth: true
                    kind: "ghost"
                    text: modelData.title || "(ไม่มีชื่อ)"
                    onClicked: { root.loadChat(chat.openChat(modelData.id)); historyPopup.close() }
                }
            }
        }
    }

    // ---------- นัดที่พลาดขณะปิดเครื่อง/ไม่ได้เข้าใช้ และคำเตือนเรื่องไฟล์/นาฬิกา (การ์ด 0001, H2) ----------
    Rectangle {
        id: notice
        property bool dismissed: false
        readonly property string missedText: skills.missed.length === 0 ? ""
            : "พลาดการเตือน " + skills.missed.length + " รายการขณะไม่ได้ใช้เครื่อง: "
              + skills.missed.map(r => r.what + " (" + r.when + ")").join(" · ")
        readonly property string message: [missedText, skills.reminderWarning].filter(t => t !== "").join("\n")
        visible: message !== "" && !dismissed
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: tools.bottom
        anchors.topMargin: 8
        width: root.colWidth
        height: visible ? noticeRow.implicitHeight + 20 : 0
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

    // ---------- หน้าแรก · เลื่อนได้เมื่อตัวอักษรใหญ่จนล้นจอ (150–200%) ----------
    Flickable {
        id: homeFlick
        visible: root.home
        anchors.top: notice.bottom
        anchors.topMargin: notice.visible ? 16 : 4
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        contentWidth: width
        contentHeight: homeCol.implicitHeight + 24
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        ScrollBar.vertical: ScrollBar { policy: homeFlick.contentHeight > homeFlick.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }

    ColumnLayout {
        id: homeCol
        x: (homeFlick.width - width) / 2
        width: root.colWidth
        spacing: 18

        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 2
            AppText {
                objectName: "greeting"
                Layout.alignment: Qt.AlignHCenter
                text: system.greeting + ", " + system.userName
                size: Theme.fontDisplay; strong: true; oneLine: true
                Layout.maximumWidth: root.colWidth
                elide: Text.ElideRight
            }
            AppText {
                Layout.alignment: Qt.AlignHCenter
                text: "วันนี้ให้ช่วยอะไรดี · ทุกอย่างทำในเครื่องนี้"
                color: Theme.inkMuted; oneLine: true
            }
        }

        // แนะนำการใช้งานครั้งแรก (ฟีเจอร์ข้อ 8) · กดตัวอย่าง = ส่งจริง · "เข้าใจแล้ว" = ไม่ขึ้นอีก (จำในไฟล์ตั้งค่า)
        Card {
            objectName: "onboarding"
            visible: !uiSettings.onboarded
            Layout.fillWidth: true
            implicitHeight: visible ? obCol.implicitHeight + 32 : 0
            ColumnLayout {
                id: obCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 16
                spacing: 10
                AppText { text: "ยินดีต้อนรับ · ลองพิมพ์แบบนี้ได้เลย"; strong: true; Layout.fillWidth: true }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Repeater {
                        model: [
                            "วันนี้ต้องทำอะไรบ้าง",
                            "เตือนส่งรายงานพรุ่งนี้บ่ายสอง",
                            "ทำไมเครื่องช้า",
                            "สรุปข้อความนี้ให้หน่อย: ",
                        ].concat(skills.canForge ? ["เปิดโหมดทำงานให้หน่อย"] : [])
                        AppButton {
                            required property string modelData
                            kind: "secondary"; iconPath: Icons.sparkle
                            text: "“" + modelData.replace(/: $/, "") + "”"
                            onClicked: modelData.endsWith(": ") ? (input.text = modelData, input.forceActiveFocus())
                                                                : root.sendText(modelData)
                        }
                    }
                }
                AppText {
                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                    text: "แชท นัด และไฟล์เก็บในเครื่องนี้ในโฟลเดอร์ของคุณ · คำสั่งเครื่องกับคำถามทั่วไป AI ในเครื่องทำเอง"
                          + (skills.canForge ? " · ข้อมูลสด (อากาศ ข่าว) และงานใหม่ที่ยังไม่มีสกิล จะส่งเฉพาะประโยคนั้นให้ Claude" : "")
                          + " · ตั้งเข้าเครื่องด้วยใบหน้าได้ที่หน้าตั้งค่า"
                }
                AppButton {
                    objectName: "onboardingDone"
                    text: "เข้าใจแล้ว"
                    onClicked: uiSettings.finishOnboarding()
                }
            }
        }

        // ที่ว่างให้ช่องพิมพ์วางทับ (ช่องพิมพ์ตัวจริงอยู่ข้างล่าง ตำแหน่งผูกกับ Item นี้)
        Item { id: composerSlot; Layout.fillWidth: true; Layout.preferredHeight: composer.height + hint.height + 6 }

        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: skills.skills
                delegate: AppButton {
                    required property var modelData
                    readonly property string example: root.examples[modelData.id] || ""
                    visible: !modelData.ready || example !== ""
                    enabled: modelData.ready && example !== ""
                    kind: "secondary"
                    iconPath: Icons.sparkle
                    text: enabled ? "“" + example + "”" : modelData.name + " · ยังไม่พร้อม"
                    ToolTip.visible: hovered
                    ToolTip.text: enabled ? "สกิล: " + modelData.name : "ต้องมีก่อน: " + modelData.missing.join(", ")
                    onClicked: root.sendText(example)
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 16
            Layout.alignment: Qt.AlignTop

            // นัดถัดไป (จาก skills.upcoming จริง · การ์ด 0001)
            Card {
                objectName: "nextReminderCard"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                implicitHeight: remCol.implicitHeight + 32
                ColumnLayout {
                    id: remCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 6
                    RowLayout {
                        spacing: 8
                        Icon { path: Icons.alert; color: Theme.accent; width: 18; height: 18; visible: skills.reminderWarning !== "" }
                        AppText { text: "นัดถัดไป"; size: Theme.fontSmall; strong: true; color: Theme.inkMuted; oneLine: true }
                    }
                    AppText {
                        visible: skills.reminderWarning !== ""
                        Layout.fillWidth: true
                        text: skills.reminderWarning; color: Theme.warnInk; size: Theme.fontSmall
                    }
                    AppText {
                        objectName: "nextReminderWhat"
                        visible: skills.reminderWarning === ""
                        Layout.fillWidth: true
                        text: skills.upcoming.length > 0 ? skills.upcoming[0].what : "ยังไม่มีนัด"
                        size: Theme.fontHeading; strong: true
                        elide: Text.ElideRight; maximumLineCount: 2
                    }
                    RowLayout {
                        visible: skills.reminderWarning === ""
                        spacing: 8
                        Chip { objectName: "nextReminderWhen"; visible: skills.upcoming.length > 0; text: skills.upcoming.length > 0 ? skills.upcoming[0].when : ""; kind: "accent" }
                        AppText {
                            text: skills.upcoming.length > 1 ? "และอีก " + (skills.upcoming.length - 1) + " นัด"
                                : skills.upcoming.length === 0 ? "ลองพิมพ์ “เตือน…” ในช่องด้านบน" : ""
                            size: Theme.fontSmall; color: Theme.inkMuted; oneLine: true
                        }
                    }
                }
            }

            // สถานะเครื่อง (จาก aipc.doctor จริง) · อ่านไม่ได้ต้องบอกว่าไม่รู้ ไม่ใช่บอกว่าปกติ (H5)
            Card {
                objectName: "machineCard"
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                implicitHeight: macCol.implicitHeight + 32
                readonly property int unknown: system.checks.filter(c => c.level === "neutral").length
                readonly property int known: system.checks.length - unknown
                readonly property string summary: system.healthIssues > 0 ? "มีเรื่องควรดู " + system.healthIssues + " ข้อ"
                    : known === 0 ? "ยังไม่รู้" : unknown > 0 ? "ไม่พบปัญหา · อ่านไม่ได้ " + unknown + " ข้อ" : "ปกติ"
                id: machineCard
                ColumnLayout {
                    id: macCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 6
                    AppText { text: "เครื่อง"; size: Theme.fontSmall; strong: true; color: Theme.inkMuted; oneLine: true }
                    RowLayout {
                        spacing: 8
                        Rectangle {
                            width: 10; height: 10; radius: 5
                            // เขียวเฉพาะตอนอ่านได้ครบและไม่มีปัญหา · อ่านไม่ได้บางข้อ = เทา (ไม่รู้ ≠ ปกติ)
                            color: system.healthIssues > 0 ? Theme.warn
                                 : (machineCard.known > 0 && machineCard.unknown === 0) ? Theme.ok : Theme.inkFaint
                        }
                        AppText { text: machineCard.summary; size: Theme.fontHeading; strong: true; oneLine: true }
                    }
                    RowLayout {
                        spacing: 8
                        AppText { text: "อุณหภูมิ " + system.tempText + " · " + system.storageText; size: Theme.fontSmall; color: Theme.inkMuted; oneLine: true }
                        Item { Layout.fillWidth: true }
                        AppButton { text: "ดูรายละเอียด"; kind: "ghost"; onClicked: AppState.page = "health" }
                    }
                }
            }
        }
    }

    }

    // ---------- แชท ----------
    ListView {
        id: list
        objectName: "chatList"
        visible: !root.home
        anchors.top: notice.visible ? notice.bottom : tools.bottom
        anchors.topMargin: 12
        // ช่องพิมพ์ย้ายพ่อได้ (หน้าแรก/แชท) จึง anchor ไม่ได้ · คำนวณความสูงจากตำแหน่งช่องพิมพ์ตอนเป็นแชท
        height: Math.max(0, (root.home ? root.height : composer.y) - y - 12)
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.colWidth
        spacing: 14
        clip: true
        model: root.items
        // ความสูงของการ์ดรู้หลังวาดเสร็จ จึงเลื่อนลงล่างสุดทุกครั้งที่เนื้อหายาวขึ้น
        onContentHeightChanged: positionViewAtEnd()
        delegate: Item {
            id: row
            required property var modelData
            required property int index
            width: ListView.view.width
            height: modelData.user ? bubble.height : modelData.ai ? aiBox.height : card.height

            Rectangle {
                id: bubble
                visible: !!row.modelData.user  // ข้อความ AI ไม่มีช่อง user → undefined (พบ 2026-09-28)
                anchors.right: parent.right
                width: Math.min(bodyText.implicitWidth + 32, parent.width * 0.75)
                height: bodyText.implicitHeight + 20
                radius: 20
                color: Theme.accentSoft
                AppText {
                    id: bodyText
                    x: 16; y: 10
                    width: parent.width - 32
                    text: row.modelData.text || ""
                    color: Theme.bubbleInk
                }
            }
            Rectangle {
                id: aiBox
                visible: !!row.modelData.ai
                width: parent.width
                height: visible ? aiCol.implicitHeight + 24 : 0
                radius: Theme.radiusLarge
                color: Theme.surface
                border.width: 1
                border.color: Theme.line
                ColumnLayout {
                    id: aiCol
                    x: 16; y: 12
                    width: parent.width - 32
                    spacing: 6
                    AppText {
                        text: "AI ในเครื่อง" + (row.modelData.skill ? " · " + row.modelData.skill : "")
                        size: Theme.fontCaption; color: Theme.inkMuted
                    }
                    AppText {
                        objectName: "aiText"
                        Layout.fillWidth: true
                        text: row.modelData.done ? row.modelData.text : (chat.streamText !== "" ? chat.streamText : "กำลังอ่านข้อความ…")
                    }
                    AppText {
                        visible: !!row.modelData.note
                        Layout.fillWidth: true
                        text: row.modelData.note || ""
                        size: Theme.fontSmall; color: Theme.warnInk
                    }
                    // เอาคำตอบไปใช้ต่อ (เช่น จดหมายที่ร่าง) · คลิปบอร์ดอยู่ในเครื่อง ไม่ได้ส่งไปไหน
                    AppButton {
                        objectName: "copyAnswer"
                        visible: !!row.modelData.done && (row.modelData.text || "") !== ""
                        text: root.copiedRow === row.index ? "คัดลอกแล้ว" : "คัดลอก"
                        kind: "ghost"
                        onClicked: { chat.copyText(row.modelData.text); root.copiedRow = row.index }
                    }
                }
            }
            SkillCard {
                id: card
                visible: !row.modelData.user && !row.modelData.ai
                width: parent.width
                height: visible ? implicitHeight : 0
                info: row.modelData.card || ({})
                answered: !!root.answered[(row.modelData.card || {}).confirmToken]
                onAnswer: (yes) => root.answer(row.modelData.card.confirmToken, yes)
                onRemoveSkill: (skillId) => root.showCard(skills.removeSkill(skillId))
                onWrongSkill: (skillId, name) => {
                    root.feedbackFor = { id: skillId, name: name }
                    input.forceActiveFocus()
                }
            }
        }
    }

    // ---------- ช่องพิมพ์ (ช่องเดียว · หน้าแรกอยู่กลางจอ แชทอยู่ล่าง) ----------
    Rectangle {
        id: composer
        // หน้าแรก: อยู่ในส่วนที่เลื่อนได้ ตรงที่ว่าง composerSlot · แชท: ติดล่างของหน้า
        parent: root.home ? homeFlick.contentItem : root
        x: (parent.width - width) / 2
        y: root.home ? homeCol.y + composerSlot.y : root.height - height - hint.height - 22
        width: root.colWidth
        height: Math.min(160, Math.max(60, input.implicitHeight + 16))
        radius: Math.min(height / 2, 28)
        color: Theme.surface
        border.width: 2
        border.color: input.activeFocus ? Theme.accent : Theme.lineStrong
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 8
            spacing: 6
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                TextArea {
                    id: input
                    objectName: "chatInput"
                    placeholderText: !!root.feedbackFor
                                     ? "บอกว่าสกิล “" + root.feedbackFor.name + "” ผิดตรงไหน เช่น ให้เปิด Gmail แทน · Esc = ยกเลิก"
                                     : "พิมพ์ข้อความถึงผู้ช่วย AI"
                    placeholderTextColor: Theme.inkFaint
                    color: Theme.ink
                    font.family: Theme.family
                    font.pixelSize: Theme.fontBody
                    wrapMode: TextEdit.Wrap
                    verticalAlignment: TextEdit.AlignVCenter
                    background: null
                    Accessible.name: "ข้อความ"
                    Keys.onPressed: (event) => {
                        const enter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                        // inputMethodComposing = กำลังพิมพ์ผ่าน IME และคำยังไม่เสร็จ → ห้ามส่ง
                        if (enter && !(event.modifiers & Qt.ShiftModifier) && !input.inputMethodComposing) {
                            event.accepted = true
                            root.send()
                        } else if (event.key === Qt.Key_Escape && !!root.feedbackFor) {
                            event.accepted = true
                            root.feedbackFor = null
                        } else if (event.key === Qt.Key_Escape && chat.busy) {
                            event.accepted = true
                            chat.stop()   // BRIEF 5.4 ข้อ 7: หยุดการตอบด้วย Esc
                        }
                    }
                }
            }
            AppButton {
                objectName: "sendButton"
                text: chat.busy ? "หยุด" : "ส่ง"; iconPath: chat.busy ? Icons.stop : Icons.send
                enabled: chat.busy || input.text.trim() !== ""
                onClicked: chat.busy ? chat.stop() : root.send()
            }
        }
    }
    // โหมดบอกว่าสกิลผิด (การ์ด 0017): เดิมบอกแค่ใน placeholder · ผู้ใช้บน Pi 5 พิมพ์คำสั่งปกติ ("เปิดเทอร์มินัล")
    // แล้วถูกส่งไปเป็นคำติสกิล → แถบเห็นชัดเหนือช่องพิมพ์ + ปุ่มยกเลิก
    Rectangle {
        objectName: "feedbackBanner"
        parent: composer.parent
        visible: !!root.feedbackFor
        x: composer.x
        width: composer.width
        y: composer.y - height - 8   // ไม่ใช้ anchors: composer ย้ายพ่อได้ (หน้าแรก/แชท)
        height: fbRow.implicitHeight + 16
        radius: Theme.radiusLarge
        color: Theme.warnSoft
        RowLayout {
            id: fbRow
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 8
            spacing: 8
            AppText {
                Layout.fillWidth: true
                text: !!root.feedbackFor
                      ? "ข้อความถัดไปจะส่งให้ Claude แก้สกิล “" + root.feedbackFor.name + "” · บอกว่าผิดตรงไหน"
                      : ""
                size: Theme.fontSmall; color: Theme.warnInk
            }
            AppButton { text: "ยกเลิก"; kind: "ghost"; onClicked: root.feedbackFor = null }
        }
    }
    // แนบไฟล์อยู่ (ฟีเจอร์ข้อ 4): คำถามถัดไปตอบจากไฟล์นี้ · กด ✕ เลิกแนบ
    Rectangle {
        objectName: "fileBanner"
        parent: composer.parent
        visible: chat.attachedFile !== "" && !root.feedbackFor
        x: composer.x
        width: composer.width
        y: composer.y - height - 8
        height: fileRow.implicitHeight + 16
        radius: Theme.radiusLarge
        color: Theme.accentSoft
        RowLayout {
            id: fileRow
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 8
            spacing: 8
            AppText {
                Layout.fillWidth: true
                text: "ถามเกี่ยวกับไฟล์ “" + chat.attachedFile + "” · AI ในเครื่องอ่าน ไม่ส่งไฟล์ออกนอกเครื่อง"
                size: Theme.fontSmall; color: Theme.accentInk
            }
            AppButton { text: "เลิกแนบ"; kind: "ghost"; onClicked: chat.detachFile() }
        }
    }
    AppText {
        id: hint
        parent: composer.parent
        anchors.top: composer.bottom
        anchors.topMargin: 6
        anchors.horizontalCenter: parent.horizontalCenter
        objectName: "chatHint"
        text: chat.notice !== "" ? chat.notice
              : chat.busy ? "Esc หรือปุ่มหยุด = หยุดตอบ" : "Enter ส่ง · Shift+Enter ขึ้นบรรทัดใหม่"
        size: Theme.fontCaption; color: chat.notice !== "" ? Theme.warnInk : Theme.inkFaint; oneLine: true
    }
}
