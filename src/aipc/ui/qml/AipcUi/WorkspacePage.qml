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
    property int speakRow: -1     // คำตอบที่กดอ่านออกเสียงล่าสุด (แสดงข้อความผิดพลาดของตัวอ่านใต้แถวนี้)
    // สั่งด้วยคีย์ลัด F9 (การ์ด 0024): ผู้ใช้อาจไม่ได้มองจอ (เบราว์เซอร์เต็มจอ) → อ่านผลให้ฟังเสมอ
    property bool speakNext: false
    // ผลของคำสั่งคีย์ลัด (Pakon 2026-10-20): เด้งเป็นหน้าต่างบนจอ ไม่ลงแชท (คำสั่งเสียงไม่ใช่การคุย) ·
    // { heard: ข้อความที่ได้ยิน, card: การ์ดผล/ยืนยัน, text: คำบอก, busy: เบราว์เซอร์กำลังทำ }
    property var vc: ({})
    readonly property bool home: items.length === 0
    readonly property int colWidth: Math.min(760, width - 48)
    readonly property int wideWidth: Math.min(1100, width - 48)   // หน้าแรก: แผง 3 ช่อง (การ์ด 0041)

    // ตัวอย่างประโยคของสกิลที่โค้ดทำงานได้แล้ว · สกิลที่ยังไม่พร้อมแสดงชื่อพร้อมคำว่า "ยังไม่พร้อม"
    // ตัวอย่างที่กดแล้วส่งเข้าแชท = ข้อความไทยต้นฉบับ (ตัวแปลคำสั่งยังเป็นภาษาไทย · การ์ด 0039 ระยะ C) · แปลแค่ตอนแสดง
    // ใส่ข้อความในช่องพิมพ์ให้แก้ต่อได้ (แผง "ลองถาม" · ปุ่มเพิ่มนัด · การ์ด 0041) · ไม่ส่งเอง
    function putInInput(text) {
        input.text = text
        input.cursorPosition = input.length
        input.forceActiveFocus()
    }

    // คำตอบของ AI แสดงเป็นข้อความธรรมดาเสมอ (ไม่เปิด markdown/HTML: แท็กรูปในคำตอบอาจทำให้ Qt ไปดึงรูปจากเว็บ = ข้อมูลรั่ว T6)
    // พบบนจอ Pi 2026-10-01: คำตอบของ Claude มี [ชื่อ](ลิงก์) และ **ตัวหนา** ดิบ ๆ → แปลงให้อ่านง่าย
    function tidy(t) {
        return plainMath((t || "").replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, "$1 ($2)").replace(/\*\*([^*]+)\*\*/g, "$1"))
    }
    // พบในผลสอบ 2026-10-01: Gemma ตอบเป็น LaTeX ($\text{H}_2\text{O}$ · $\frac{1}{4}$) → แปลงเป็นข้อความธรรมดา
    // ตัวห้อย/ตัวยกที่เป็นตัวเลขใช้อักขระ Unicode (H₂O · x²) · คำสั่งที่ไม่รู้จักตัดทิ้ง
    readonly property var mathSymbols: ({ "times": "×", "div": "÷", "cdot": "·", "pm": "±", "le": "≤", "leq": "≤",
        "ge": "≥", "geq": "≥", "neq": "≠", "approx": "≈", "pi": "π", "infty": "∞", "circ": "°", "degree": "°",
        "rightarrow": "→", "to": "→", "alpha": "α", "beta": "β", "theta": "θ", "Delta": "Δ", "%": "%" })
    function plainMath(t) {
        if (t.indexOf("\\") < 0 && t.indexOf("$") < 0) return t
        const sub = "₀₁₂₃₄₅₆₇₈₉", sup = "⁰¹²³⁴⁵⁶⁷⁸⁹"
        const conv = (s, table) => s.replace(/[0-9]/g, d => table[+d])
        return t.replace(/\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]/g, (m, a, b, c, d) => {
            let x = a || b || c || d
            if (b && !/[\\^_{]/.test(b)) return m   // "$5 กับ $10" = ราคา ไม่ใช่สูตร
            for (let i = 0; i < 3; i++)
                x = x.replace(/\\(?:d|t)?frac\{([^{}]*)\}\{([^{}]*)\}/g, "$1/$2")
                     .replace(/\\sqrt\{([^{}]*)\}/g, "√$1")
                     .replace(/\\(?:text|mathrm|mathbf|textbf|operatorname)\{([^{}]*)\}/g, "$1")
            x = x.replace(/\^\{?\\circ\}?/g, "°")
                 .replace(/_\{([0-9]+)\}|_([0-9])/g, (m2, p, q) => conv(p || q, sub))
                 .replace(/\^\{([0-9]+)\}|\^([0-9])/g, (m2, p, q) => conv(p || q, sup))
                 .replace(/\\([A-Za-z]+|%)/g, (m2, name) => root.mathSymbols[name] !== undefined ? root.mathSymbols[name] : "")
                 .replace(/[{}]/g, "").replace(/\\,|\\;|\\!|~/g, " ")
            return x.replace(/\s+/g, " ").trim()
        })
    }
    // เปิดหน้าผู้ช่วยแล้วพิมพ์ได้ทันที (ทดสอบบนจอ Pi: ต้องกด Tab หลายครั้งกว่าจะถึงช่องพิมพ์)
    function focusInput() { if (visible && !historyPopup.opened) input.forceActiveFocus() }
    onVisibleChanged: if (visible) Qt.callLater(focusInput)
    Component.onCompleted: Qt.callLater(focusInput)
    // ข้อความสรุปวันนี้: ทักทาย · วันที่ · นัดใกล้สุด 3 รายการ · สถานะเครื่อง (ไม่เดา: อ่านไม่ได้ก็บอกว่าไม่รู้)
    function briefingText() {
        const lines = [system.greeting + " " + system.userName, Tr.t("วันนี้", "หัวสรุป") + system.longDate]
        const up = skills.upcoming
        if (skills.reminderWarning !== "") lines.push(skills.reminderWarning)
        else if (up.length === 0) lines.push(Tr.t("ยังไม่มีนัด"))
        else {
            lines.push(Tr.t("มีนัด ") + up.length + Tr.t(" รายการ"))
            for (let i = 0; i < Math.min(3, up.length); i++) lines.push(up[i].when + " " + up[i].what)
        }
        lines.push(Tr.t("เครื่อง") + machineSummary())
        return lines.join("\n")
    }
    // สถานะเครื่องแบบหนึ่งประโยค (จาก aipc.doctor จริง) · อ่านไม่ได้ต้องบอกว่าไม่รู้ ไม่ใช่บอกว่าปกติ (H5)
    function machineSummary() {
        const unknown = system.checks.filter(c => c.level === "neutral").length
        const known = system.checks.length - unknown
        return system.healthIssues > 0 ? Tr.t("มีเรื่องควรดู ") + system.healthIssues + Tr.t(" ข้อ")
             : known === 0 ? Tr.t("ยังไม่รู้")
             : unknown > 0 ? Tr.t("ไม่พบปัญหา · อ่านไม่ได้ ") + unknown + Tr.t(" ข้อ") : Tr.t("ปกติ")
    }
    function push(item) {
        items = items.concat([item])
    }
    function showCard(card) {
        push({ user: false, card: card })
        if (card.appInstall) installPopup.openFor(card.appInstall, card.appName)   // การ์ด 0054: ผู้ดูแลใส่รหัส
        if (card.page) AppState.page = card.page   // เช่น "เปิดหน้าตั้งค่า"
    }
    function send() {
        const text = input.text.trim()
        if (text === "" || chat.busy) return
        push({ user: true, text: text })
        input.text = ""
        if (chat.attachedFile !== "") {  // ถามเกี่ยวกับไฟล์: ตรงไป AI ในเครื่อง ไม่ผ่านสกิล (ฟีเจอร์ข้อ 4)
            if (chat.send(text, "", false))
                push({ ai: true, text: "", note: "", done: false, skill: Tr.t("ไฟล์ ") + chat.attachedFile })
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
        if (card.llm && !toAi)   // สถานะเปลี่ยนระหว่างทาง · บอกตามจริง (แชทงาน = เหตุที่ Claude ใช้ไม่ได้ · การ์ด 0053)
            card.title = Tr.t("ยังตอบไม่ได้: ") + (chat.mode === "work" ? chat.workBlocked : chat.statusText)
        // สกิลแบบขั้นตอนเห็นการ์ดขั้นตอนเสมอ แม้ขั้นสุดท้ายจะส่งต่อให้ AI
        if (!toAi || card.kind === "steps")
            showCard(card)
        if (toAi)
            push({ ai: true, text: "", note: "", done: false, skill: (card.badge || {}).name || "" })
    }
    function loadChat(messages) {
        voice.stop()  // แถวที่กำลังอ่านจะเป็นของแชทอื่นแล้ว
        items = messages.map(m => m.role === "user" ? { user: true, text: m.shown || m.content }
                                                    : { ai: true, text: m.content, note: "", done: true })
        answered = ({})
    }
    // ข้อความจากเสียง: ใส่ช่องพิมพ์ให้ตรวจ/แก้แล้วกดส่งเอง (ทดลองแล้ว: ถอดผิดทำให้ทำคำสั่งผิดโดยไม่ถาม)
    // แชท 2 แบบ (การ์ด 0053): สลับแบบ = บทสนทนาใหม่ของแบบนั้น · ล้างฟองข้อความของแบบเดิม
    Connections {
        target: chat
        function onModeChanged() { voice.stop(); root.items = []; root.answered = ({}) }
    }
    Connections {
        target: voice
        function onTranscribed(text) {
            input.text = input.text.trim() === "" ? text : input.text.trim() + " " + text
            input.forceActiveFocus()
            input.cursorPosition = input.text.length
        }
    }
    // คีย์ลัด F9 (การ์ด 0024 · Pakon เลือก: ถอดเสร็จทำทันที): ตอบการ์ดที่รอยืนยัน → คำสั่งเว็บ → แชทตามเดิม
    Connections {
        target: voice
        function onHeardHandsFree(text) { root.voiceCommand(text) }
        function onMicChanged() {
            if (voice.handsFree && voice.listening) root.voicePhase("listening")
            else if (voice.handsFree && voice.transcribing) root.voicePhase("transcribing")
            else if (root.vc.phase === "listening" || root.vc.phase === "transcribing") {
                // จบโดยไม่มีข้อความ (ไม่ได้ยินเสียงพูด · เปิดไมค์ไม่ได้) = บอกเหตุผลแล้วปิดเอง · มีข้อความ = voiceCommand แทนที่
                root.vc = { heard: "", card: null, text: voice.micMessage, busy: false, phase: "", ok: false }
                voiceClose.restart()
            }
        }
    }
    Connections {
        target: browser
        function onFinished(say, ok) {
            if (root.vc.busy) {   // ผลของคำสั่งเสียง (หน้าต่างเด้ง)
                root.voiceShow(root.vc.heard, null, say, false, ok)
                if (voice.available) voice.speak(-4, say)
                return
            }
            const i = root.items.slice()
            if (i.length > 0 && i[i.length - 1].ai && !i[i.length - 1].done)
                i[i.length - 1] = Object.assign({}, i[i.length - 1], { text: say, sys: true, note: ok ? "" : Tr.t("ทำไม่สำเร็จ"), done: true })
            root.items = i
            if (voice.available) voice.speak(i.length - 1, say)
        }
    }
    // เปิดเว็บจากปุ่ม/พิมพ์/สกิล (การ์ด 0031) เสร็จทีหลัง · ไม่แก้ข้อความล่าสุดในแชท (ต่างจาก onFinished ของคำสั่งเสียง) ·
    // ไม่สำเร็จต้องบอก (H5): หน้าแรก = ใต้ปุ่ม · ในแชท = เพิ่มข้อความใหม่
    Connections {
        target: browser
        function onOpened(say, ok) {
            if (root.home) appsNote.text = ok ? "" : say
            else if (!ok) root.push({ ai: true, text: say, sys: true, note: Tr.t("ทำไม่สำเร็จ"), done: true })
        }
    }
    function pendingConfirm() {
        for (let k = items.length - 1; k >= 0; k--) {
            const c = items[k].card
            if (c && c.confirmToken && !answered[c.confirmToken]) return c.confirmToken
            if (items[k].user) break   // การ์ดเก่ากว่าข้อความล่าสุดของผู้ใช้ไม่นับ
        }
        return ""
    }
    // การ์ดยืนยันที่เด้งจากคำสั่งเสียงและยังไม่ตอบ (มาก่อนการ์ดในแชท)
    function voiceToken() {
        const c = vc.card
        return voicePopup.opened && c && c.confirmToken && !answered[c.confirmToken] ? c.confirmToken : ""
    }
    // กล่องคำสั่งเสียงขึ้นตลอดที่กดคีย์ลัด ทุกหน้า (Pakon 2026-10-20) · ไม่ได้กด = ไม่แสดง
    function voicePhase(phase) {
        vc = { heard: "", card: null, text: "", busy: false, phase: phase }
        voiceClose.stop()
        voicePopup.open()
    }
    function voiceShow(heard, card, text, busy, ok) {
        vc = { heard: heard, card: card || null, text: text || "", busy: !!busy, phase: "", ok: ok !== false }
        if (card && card.page) AppState.page = card.page   // เช่น "เปิดหน้าตั้งค่า"
        voicePopup.open()
        voiceClose.restart()
    }
    function speakVoice() {
        if (!voice.available) return
        const c = vc.card
        const say = c ? [c.title].concat((c.lines || []).slice(0, 2)).join(" · ") : vc.text
        if (say) voice.speak(-4, say)
    }
    // การ์ดจากคำสั่งเสียง: คำตอบของ AI (สกิลที่ LLM ทำ) ยังไปแชท · อย่างอื่นเด้งบนจอ
    function voiceDispatch(card, heard) {
        if (card.llm === true) {
            voicePopup.close()
            dispatch(card, heard)
            speakNext = true
            return
        }
        voiceShow(heard, card, "", false)
        speakVoice()
    }
    function answerVoice(token, yes, heard) {
        const a = Object.assign({}, answered)
        a[token] = true
        answered = a
        const card = skills.confirm(token, yes)
        if (card.redo) {       // การ์ด 0045: "หมายถึง … ใช่ไหม" ตอบใช่ = สั่งประโยคคำสั่งที่ถูกต้อง
            voiceCommand(card.redo)
            return
        }
        if (card.siteRun) {    // การ์ด 0046: ยืนยันคำสั่งของสกิลประจำเว็บแล้ว
            siteRun(card, heard)
            return
        }
        if (card.appInstall) {   // การ์ด 0054: ใช่ แล้วกด ตกลง/ยกเลิก ที่จอ (ยืนยันอีกชั้นก่อนติดตั้งจริง)
            voicePopup.close()
            AppState.page = "workspace"
            showCard(card)
            return
        }
        if (card.chatText) {   // การ์ด 0042 รอบ 3: ถามในแชท = เหมือนพิมพ์เอง
            voicePopup.close()
            AppState.page = "workspace"
            sendText(card.chatText)
            return
        }
        if (card.llm && card.llmText && chat.send(card.llmText, card.prompt || "")) {
            // งานที่ใช้ AI จากคีย์ลัด (การ์ด 0042): ไปหน้าแชท · เห็นข้อความที่ส่ง + คำตอบที่กำลังมา
            voicePopup.close()
            AppState.page = "workspace"
            items = items.concat([{ user: true, text: card.llmText },
                                  { ai: true, text: "", note: "", done: false, skill: (card.badge || {}).name || "" }])
            return
        }
        voiceShow(heard, card, "", false)
        speakVoice()
    }
    // ค่าตั้งของแอปจากคีย์ลัด (การ์ด 0042 รอบ 3) · คืนข้อความผล
    function appCommand(cmd) {
        if (cmd.kind === "theme") {
            uiSettings.setTheme(cmd.value)
            return cmd.value === "dark" ? Tr.t("เปลี่ยนเป็นโหมดมืดแล้ว") : Tr.t("เปลี่ยนเป็นโหมดสว่างแล้ว")
        }
        if (cmd.kind === "font") {
            const steps = [1.0, 1.25, 1.5, 1.75, 2.0]
            const i = Math.max(0, steps.indexOf(uiSettings.fontScale))
            const j = Math.min(steps.length - 1, Math.max(0, i + (cmd.value === "up" ? 1 : -1)))
            if (j === i)
                return cmd.value === "up" ? Tr.t("ตัวอักษรใหญ่สุดแล้ว (200%)") : Tr.t("ตัวอักษรเล็กสุดแล้ว (100%)")
            uiSettings.setFontScale(steps[j])
            return Tr.t("ขนาดตัวอักษร ") + Math.round(steps[j] * 100) + "%"
        }
        if (cmd.kind === "lang") {
            uiSettings.setLanguage(cmd.value)
            return cmd.value === "en" ? "Switched to English" : "เปลี่ยนเป็นภาษาไทยแล้ว"
        }
        if (cmd.kind === "newchat") {
            voice.stop(); chat.newChat(false); root.items = []; root.answered = ({})
            AppState.page = "workspace"
            return Tr.t("เริ่มแชทใหม่แล้ว")
        }
        return ""
    }
    // คำสั่งของสกิลประจำเว็บ (การ์ด 0046): กดคีย์/คลิกในเบราว์เซอร์ของผู้ช่วย · ผลมาทาง onFinished
    function siteRun(card, heard) {
        const r = card.siteRun
        if (browser.runSite(r.kind, r.arg, r.site)) voiceShow(heard, null, Tr.t("กำลังทำ…"), true)
        else voiceSay(heard, Tr.t("ยังสั่งในเว็บไม่ได้ · เปิดเว็บนั้นในเบราว์เซอร์ของผู้ช่วยก่อน"))
    }
    function voiceSay(heard, say) {   // บอกว่าทำไม่ได้/ไม่รู้จัก (กล่องสีส้ม)
        voiceShow(heard, null, say, false, false)
        if (voice.available) voice.speak(-4, say)
    }
    function voiceCommand(text) {
        const t = text.trim().replace(/[.!?。\s]+$/, "")
        const vt = voiceToken()
        const tok = vt !== "" ? vt : pendingConfirm()
        // งานที่ลบ/แตะเครื่องยังต้องยืนยัน · พูด "ใช่" / "ไม่" แทนการกดปุ่ม · ตัดสินในโค้ด Python (handsfree.yes_no):
        // มีคำปฏิเสธ = ไม่ · "ใช่" ต้องไม่มีคำอื่นต่อ ("ตกลงไม่ลบแล้ว" เคยนับเป็นใช่ · ตรวจทั้งระบบ 2.1)
        const yn = tok !== "" ? browser.yesNo(t) : ""
        if (yn === "yes" || yn === "no") {
            if (vt !== "") answerVoice(tok, yn === "yes", t)
            else { answer(tok, yn === "yes"); speakLastCard() }   // การ์ดในแชท (จากที่พิมพ์) ตอบในแชท
            return
        }
        if (yn === "unclear") {
            const again = Tr.t("ยังไม่ได้ทำ · ตอบว่า “ใช่” หรือ “ไม่” อย่างเดียว")
            if (vt !== "") { vc = Object.assign({}, vc, { heard: t }); voiceClose.restart() }
            else voiceShow(t, null, again, false)
            if (voice.available) voice.speak(-4, again)
            return
        }
        // เบราว์เซอร์ยังทำคำสั่งก่อนอยู่ → บอกให้รอ (เดิมหลุดไปแชท: "ย้อนกลับ" กลายเป็นคำสั่งของแอป · พบใน 0025)
        if (browser.busy) { voiceSay(t, Tr.t("ยังทำคำสั่งก่อนหน้าอยู่ รอสักครู่แล้วสั่งใหม่")); return }
        // การ์ด 0027: คีย์ลัด = สั่งงานอย่างเดียว ไม่ส่งให้ AI ในเครื่องคุย (BRIEF 5.6 ข้อ 1) · ทางตัดสินใน handsfree.route
        const way = browser.route(t)
        if (way === "skill") {          // การ์ด 0028: ตรงเป๊ะกับสกิลที่ทำด้วยโค้ด = การ์ดสกิลเดียวกับตอนพิมพ์ (ยืนยันตามกติกาเดิม)
            voiceDispatch(skills.handleAs(skills.voiceSkill(t), t), t)
            return
        }
        if ((way === "browser" && browser.handle(t)) || (way === "open_browser" && browser.openHome())) {
            voiceShow(t, null, Tr.t("กำลังทำ…"), true)   // ผลมาทาง onFinished
            return
        }
        if (way === "app") {            // การ์ด 0042 รอบ 3: ค่าตั้งของแอป (กลับคืนได้ทันที)
            voiceShow(t, null, appCommand(browser.appCommand(t)), false, true)
            return
        }
        // การ์ด 0046: คำสั่งของสกิลประจำเว็บที่เปิดอยู่ (คีย์ลัด/ปุ่มของเว็บนั้น) · มาหลังคำสั่งของระบบ:
        // คำเดียวกันทำแบบเดิมทุกเว็บ และ "หยุด"/"เล่นต่อ" ของระบบไม่สลับไปมาเหมือนคีย์ k/Space ·
        // มาก่อนทางที่ AI เดา (นัด · งานภาษา) เช่น "ย้อนสิบวิ" ไม่กลายเป็นนัด
        const url = browser.currentUrl()
        if (url !== "" && way !== "command") {
            const own = skills.siteCommand(t, url)
            if (own.siteRun) { siteRun(own, t); return }
            if (own.confirmToken) { voiceDispatch(own, t); return }   // คำสั่งที่มี "ยืนยันก่อน"
        }
        if (way === "reminder") {       // การ์ด 0042: ตั้งเตือนด้วยเสียง = การ์ดสกิลนัดเดิม (ยืนยันก่อนบันทึก)
            voiceDispatch(skills.voiceReminder(t), t)
            return
        }
        if (way === "llm_skill") {      // การ์ด 0042: งานที่ใช้ AI = ถามก่อนส่งไปแชท (คีย์ลัดไม่คุยกับ AI เอง)
            voiceDispatch(skills.voiceToChat(t), t)
            return
        }
        if (way === "command") {        // คำสั่งเครื่อง: ทางเดิมของแชททำคำสั่งก่อนถึง AI (ยืนยันตามกติกาเดิม)
            // ไม่ผ่าน send(): send() ส่งข้อความไปให้ Claude แก้สกิล (เมื่อกด "ไม่ใช่แบบนี้" ค้างไว้) หรือถามไฟล์ที่แนบ
            // และเขียนทับข้อความที่ผู้ใช้พิมพ์ค้างในช่อง (ตรวจทั้งระบบ 2.2 · 2.7)
            voiceDispatch(skills.handle(t), t)
            return
        }
        if (way === "unknown") {
            // การ์ด 0029: คำถามที่โค้ดตอบเองได้ (เวลา นัด ไฟล์ สุขภาพเครื่อง) = ตอบแล้วอ่านออกเสียง · ไม่ใช้ AI
            const answerCard = skills.voiceAnswer(t)
            if (answerCard.kind !== undefined) { voiceDispatch(answerCard, t); return }
            // การ์ด 0046: ได้ยินใกล้คำสั่งของเว็บที่เปิดอยู่ = "หมายถึง … ใช่ไหม"
            const near = url !== "" ? skills.siteNear(t, url) : ({})
            if (near.confirmToken) { voiceDispatch(near, t); return }
            // การ์ด 0028 ทาง ก: ได้ยินใกล้เคียงสกิล = ถาม "หมายถึง … ใช่ไหม" ไม่ทำเองจนตอบ "ใช่"
            const ask = skills.voiceConfirm(t)
            if (ask.confirmToken) { voiceDispatch(ask, t); return }
            // การ์ด 0030: ขอโหมดใหม่ = การ์ดยืนยันข้อความก่อนส่ง Claude (ไม่มี Claude/ปิดสวิตช์ = การ์ดอธิบาย)
            const create = skills.voiceCreate(t)
            if (create.kind !== undefined) { voiceDispatch(create, t); return }
            // การ์ด 0046: อยู่ในเว็บที่คุมได้ + ยังไม่มีคำสั่งนี้ = ถามว่าให้ Claude เพิ่มเข้าสกิลของเว็บนั้นไหม
            const learn = url !== "" ? skills.siteLearn(t, url) : ({})
            if (learn.confirmToken) { voiceDispatch(learn, t); return }
            // การ์ด 0042 รอบ 3: ไม่ใช่คำสั่งทันที = ถามว่าส่งไปถามในแชทไหม (แทน "ไม่รู้จักคำสั่ง")
            const toChat = skills.voiceAsk(t)
            if (toChat.confirmToken) { voiceDispatch(toChat, t); return }
        }
        const say = way === "needs_browser"
            ? browser.hint(t)   // คุมเพลงก่อนเปิดเพลง = บอกให้เปิดเพลงก่อน (การ์ด 0035)
            : Tr.t("ไม่รู้จักคำสั่ง \"") + t + Tr.t("\" · คุยกับผู้ช่วยให้พิมพ์ หรือกดปุ่มไมค์ในหน้าแชท")
        voiceSay(t, say)
    }
    function speakLastCard() {
        const last = items[items.length - 1]
        if (!voice.available || !last || !last.card) return
        const c = last.card
        voice.speak(items.length - 1, [c.title].concat((c.lines || []).slice(0, 2)).join(" · "))
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
            i[i.length - 1] = Object.assign({}, i[i.length - 1], { text: text, note: note, done: true, why: chat.lastTrace })
            root.items = i
            // อ่านคำตอบเองเมื่อเปิดในหน้าตั้งค่า (การ์ด 0019) · ตอบไม่จบ/หยุด (มีหมายเหตุ) ไม่อ่าน
            const spoken = root.speakNext
            root.speakNext = false
            if ((uiSettings.speakAnswers || spoken) && voice.available && note === "" && text !== "")
                voice.speak(i.length - 1, root.tidy(text))
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
            if (card.voice === true)    // การ์ด 0030: สร้างจากเสียง = อ่านผลออกเสียง (ไม่ได้มองจอก็รู้)
                root.speakLastCard()
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
    // แถว 1: ปุ่มเปิด-ปิด/คำสั่ง ชิดขวา (Flow ขวาไปซ้าย · ตัวอักษรใหญ่แล้วขึ้นแถวใหม่ · ตัวแรกในไฟล์อยู่ขวาสุด)
    // แถว 2: เลือกโหมดแชท/โมเดล/ระดับความคิด เป็นแถบแบ่งช่อง (การ์ด 0053)
    ColumnLayout {
        id: tools
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        spacing: 10
        Flow {
            Layout.fillWidth: true
            layoutDirection: Qt.RightToLeft
            spacing: 8
            AppButton {
                text: chat.temporary ? Tr.t("แชทชั่วคราว ✓") : Tr.t("แชทชั่วคราว"); kind: "secondary"
                ToolTip.visible: hovered; ToolTip.text: Tr.t("ไม่บันทึกประวัติของบทสนทนานี้")
                onClicked: { voice.stop(); chat.newChat(!chat.temporary); root.items = []; root.answered = ({}) }
            }
            AppButton {
                visible: !root.home
                text: Tr.t("แชทใหม่"); kind: "secondary"; iconPath: Icons.plus
                onClicked: { voice.stop(); chat.newChat(false); root.items = []; root.answered = ({}) }
            }
            AppButton {
                id: historyButton
                text: Tr.t("ประวัติ"); kind: "secondary"; iconPath: Icons.chat
                onClicked: historyPopup.open()
            }
            // อ่านคำตอบออกเสียง เปิด/ปิด (Pakon เลือกไว้แถวบน 2026-10-02) · สถานะเขียนเป็นคำ ไม่ใช่แค่สี · ค่าเริ่มต้นเปิด
            AppButton {
                objectName: "speakSwitch"
                visible: voice.available
                kind: uiSettings.speakAnswers ? "primary" : "secondary"
                iconPath: uiSettings.speakAnswers ? Icons.speaker : Icons.speakerOff
                text: Tr.t("อ่านคำตอบออกเสียง: ") + (uiSettings.speakAnswers ? Tr.t("เปิด") : Tr.t("ปิด"))
                Accessible.name: text + Tr.t(" · แตะเพื่อ") + (uiSettings.speakAnswers ? Tr.t("ปิด") : Tr.t("เปิด"))
                onClicked: {
                    const on = !uiSettings.speakAnswers
                    uiSettings.setSpeakAnswers(on)
                    if (!on) voice.stop()
                }
            }
        }
        // แชท 2 แบบ (การ์ด 0053) · แถวของตัวเอง แยกจากปุ่มเปิด-ปิดด้านบน (Pakon 2026-10-22: เดิมหน้าตาเหมือนปุ่มเสียงอ่าน)
        // ทั่วไป = AI ในเครื่องก่อน (ไม่รู้ = ส่ง Claude เอง) · งาน = Claude ทุกข้อความ เลือกโมเดลและระดับความคิดได้
        Flow {
            objectName: "chatSetup"
            Layout.fillWidth: true
            spacing: 16
            Segmented {
                objectName: "modeSwitch"
                label: Tr.t("โหมดแชท")
                current: chat.mode
                options: [
                    { value: "general", text: Tr.t("แชททั่วไป"), hint: Tr.t("ในเครื่องก่อน") },
                    { value: "work", text: Tr.t("แชทงาน"), hint: Tr.t("Claude ทุกข้อความ") }
                ]
                onPicked: (v) => { if (!chat.setMode(v)) modeNote.text = Tr.t("แชทงานใช้ไม่ได้: ") + chat.workBlocked }
            }
            Segmented {
                objectName: "modelSwitch"
                visible: chat.mode === "work"
                label: Tr.t("โมเดล")
                current: uiSettings.cloudModel
                options: [
                    { value: "haiku", text: "Haiku", hint: Tr.t("เร็ว") },
                    { value: "sonnet", text: "Sonnet", hint: Tr.t("สมดุล") },
                    { value: "opus", text: "Opus", hint: Tr.t("ละเอียดสุด") }
                ]
                onPicked: (v) => uiSettings.setCloudModel(v)
            }
            Segmented {
                objectName: "effortSwitch"
                visible: chat.mode === "work"
                label: Tr.t("ระดับความคิด")
                current: uiSettings.cloudEffort
                options: [
                    { value: "low", text: "Low" }, { value: "medium", text: "Medium" },
                    { value: "high", text: "High" }, { value: "xhigh", text: "Extra" }, { value: "max", text: "Max" }
                ]
                onPicked: (v) => uiSettings.setCloudEffort(v)
            }
            AppText {
                id: modeNote
                objectName: "modeNote"
                visible: text !== "" && chat.mode === "general"
                text: ""
                color: Theme.warnInk; size: Theme.fontSmall
                height: Theme.touch; verticalAlignment: Text.AlignVCenter
            }
        }
    }
    // กล่องคำสั่งเสียง (Pakon 2026-10-20): หน้าต่างแยกของตัวเอง ลอยบนสุดเหนือทุกหน้าต่าง รวมเบราว์เซอร์เต็มจอ
    // (กฎ labwc ใน scripts/pi/session/labwc/rc.xml จับจากชื่อหน้าต่าง "aipc-voice-box": บนสุด · ไม่มีกรอบ · ขอบบนกลางจอ) ·
    // ไม่มีการ์ดรอยืนยัน = ปิดเองใน 8 วิ · รอยืนยัน = ค้างจนตอบ (พูด "ใช่/ไม่" หรือกดปุ่ม) หรือครบ 30 วิ ·
    // หน้าตา (การ์ด 0041 ระยะ 2 · Pakon: "ขึ้นแล้วแต่ยังไม่สวย"): มุมมน · แถบสีบอกสถานะ (คราม = กำลังทำ · เขียว = ทำแล้ว ·
    // ส้ม = ทำไม่ได้) · ตอนฟังมีแท่งเสียงขยับ (ภาพเคลื่อนไหวเฉพาะตอนฟัง/ถอดเสียง = บอกว่ากำลังทำงาน) · คำที่ได้ยินตัวใหญ่
    Window {
        id: voicePopup
        objectName: "voicePopup"
        readonly property bool opened: visible
        function open() { visible = true }
        title: "aipc-voice-box"
        flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
        visible: false
        color: "transparent"   // มุมมน: พื้นหน้าต่างโปร่ง วาดกล่องเองข้างใน (labwc รองรับหน้าต่างโปร่ง)
        width: Math.min(600, Screen.width - 32)
        height: voiceCol.implicitHeight + 44
        readonly property bool listening: root.vc.phase === "listening"
        readonly property bool working: root.vc.phase === "transcribing" || !!root.vc.busy
        readonly property bool failed: !listening && !working && !root.vc.card && root.vc.ok === false
        readonly property color tone: listening || working || !!root.vc.card ? Theme.accent : failed ? Theme.warn : Theme.ok
        Shortcut { sequence: "Esc"; onActivated: voicePopup.close() }  // labwc ให้กล่องรับคีย์บอร์ดตอนเปิด · กลับเบราว์เซอร์เมื่อปิด
        Rectangle {
            anchors.fill: parent
            radius: 22
            color: Theme.surface
            border.width: 1
            border.color: Theme.lineStrong
            Rectangle {   // แถบสีสถานะด้านบน
                anchors.top: parent.top
                anchors.topMargin: 0
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width - 44
                height: 3
                radius: 2
                color: voicePopup.tone
            }
        }
        ColumnLayout {
            id: voiceCol
            x: 22; y: 22
            width: parent.width - 44
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                Item {   // วงไมค์ · ตอนฟังมีวงกระเพื่อม
                    implicitWidth: 48; implicitHeight: 48
                    Rectangle {
                        id: ripple
                        anchors.centerIn: parent
                        width: 48; height: 48; radius: 24
                        color: Theme.accent
                        opacity: 0
                        visible: voicePopup.listening
                        SequentialAnimation on scale {
                            running: voicePopup.listening && voicePopup.visible
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.85; to: 1.35; duration: 900; easing.type: Easing.OutCubic }
                        }
                        SequentialAnimation on opacity {
                            running: voicePopup.listening && voicePopup.visible
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.35; to: 0; duration: 900; easing.type: Easing.OutCubic }
                        }
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 44; height: 44; radius: 22
                        color: voicePopup.listening ? Theme.accentFill : Theme.surface2
                        Icon {
                            anchors.centerIn: parent
                            width: 22; height: 22
                            path: voicePopup.listening || voicePopup.working ? Icons.mic
                                  : root.vc.card ? Icons.sparkle : voicePopup.failed ? Icons.alert : Icons.check
                            color: voicePopup.listening ? Theme.textOnAccent : voicePopup.tone
                        }
                    }
                }
                ColumnLayout {
                    objectName: "voiceListening"
                    visible: voicePopup.listening || root.vc.phase === "transcribing"
                    Layout.fillWidth: true
                    spacing: 2
                    AppText {
                        Layout.fillWidth: true
                        strong: true
                        size: Theme.fontHeading
                        text: voicePopup.listening ? Tr.t("กำลังฟัง…") : Tr.t("กำลังถอดเสียง…")
                    }
                    AppText {
                        Layout.fillWidth: true
                        size: Theme.fontSmall; color: Theme.inkMuted
                        text: voicePopup.listening ? Tr.t("พูดคำสั่งได้เลย · ไทยหรืออังกฤษ · กดคีย์ลัดอีกครั้ง = หยุด")
                                                   : Tr.t("รอสักครู่")
                    }
                }
                ColumnLayout {   // ผล: หัวสั้น ๆ บอกสถานะ
                    visible: !voicePopup.listening && root.vc.phase !== "transcribing"
                    Layout.fillWidth: true
                    spacing: 2
                    // ทำแล้ว = ผลเป็นหัวเรื่อง ("เปิด YouTube แล้ว") · ทำไม่ได้ = "ยังทำไม่ได้" + เหตุผลข้างล่าง
                    AppText {
                        objectName: "voiceStatus"
                        Layout.fillWidth: true
                        strong: true
                        size: Theme.fontHeading
                        maximumLineCount: 2; elide: Text.ElideRight
                        text: root.vc.busy ? Tr.t("กำลังทำ…") : root.vc.card ? Tr.t("รอยืนยันก่อนทำ")
                              : voicePopup.failed ? Tr.t("ยังทำไม่ได้") : (Tr.x(root.vc.text || "") || Tr.t("เรียบร้อย"))
                    }
                    AppText {
                        Layout.fillWidth: true
                        size: Theme.fontSmall; color: Theme.inkMuted
                        text: root.vc.card ? Tr.t("กดปุ่ม หรือกด F9 แล้วพูดว่า “ใช่” / “ไม่”")
                              : Tr.t("คำสั่งเสียง · Esc = ปิด")
                    }
                }
                Row {   // แท่งเสียง (ตอนฟัง) · จุดรอ (ตอนถอดเสียง/กำลังทำ)
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 4
                    visible: voicePopup.listening || voicePopup.working
                    Repeater {
                        model: 4
                        Rectangle {
                            required property int index
                            anchors.verticalCenter: parent.verticalCenter
                            width: 5; radius: 3
                            height: voicePopup.listening ? 10 : 6
                            color: Theme.accent
                            opacity: voicePopup.listening ? 1 : 0.5
                            SequentialAnimation on height {
                                running: voicePopup.listening && voicePopup.visible
                                loops: Animation.Infinite
                                NumberAnimation { to: 26 - index * 3; duration: 260 + index * 90; easing.type: Easing.InOutSine }
                                NumberAnimation { to: 8; duration: 260 + index * 90; easing.type: Easing.InOutSine }
                            }
                            SequentialAnimation on opacity {
                                running: voicePopup.working && voicePopup.visible
                                loops: Animation.Infinite
                                PauseAnimation { duration: index * 150 }
                                NumberAnimation { to: 1; duration: 300 }
                                NumberAnimation { to: 0.3; duration: 300 }
                            }
                        }
                    }
                }
            }
            // คำที่ได้ยิน: ตัวใหญ่ในกล่องรอง (ผู้ใช้ตรวจได้ทันทีว่าระบบได้ยินถูกไหม)
            Rectangle {
                visible: (root.vc.heard || "") !== ""
                Layout.fillWidth: true
                implicitHeight: heardCol.implicitHeight + 20
                radius: 14
                color: Theme.surface2
                ColumnLayout {
                    id: heardCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 14; anchors.rightMargin: 14
                    spacing: 2
                    AppText { text: Tr.t("ได้ยินว่า"); size: Theme.fontCaption; color: Theme.inkFaint; oneLine: true }
                    AppText {
                        objectName: "voiceHeard"
                        Layout.fillWidth: true
                        text: "“" + (root.vc.heard || "") + "”"
                        size: Theme.px(18); strong: true
                        maximumLineCount: 3; elide: Text.ElideRight
                    }
                }
            }
            AppText {
                objectName: "voiceSay"
                visible: voicePopup.failed && (root.vc.text || "") !== ""   // ทำแล้ว: ผลอยู่ในหัวเรื่องแล้ว
                Layout.fillWidth: true
                text: Tr.x(root.vc.text || "")
                color: Theme.warnInk
            }
            SkillCard {
                objectName: "voiceCard"
                visible: !!root.vc.card
                Layout.fillWidth: true
                info: root.vc.card || ({})
                answered: !!root.answered[(root.vc.card || {}).confirmToken]
                onAnswer: (yes) => root.answerVoice(root.vc.card.confirmToken, yes, root.vc.heard)
                undone: !!root.answered[(root.vc.card || {}).undoToken]
                onUndo: {
                    const t = root.vc.card.undoToken
                    const a = Object.assign({}, root.answered)
                    a[t] = true
                    root.answered = a
                    root.voiceShow(root.vc.heard, skills.undo(t), "", false)
                }
            }
        }
    }
    Timer {
        id: voiceClose
        // การ์ด 0052: ปิด/รีสตาร์ตเครื่องรอคำตอบแค่ 10 วิ (ไม่ตอบ = ไม่ทำ) · การ์ดยืนยันอื่น 30 วิ
        interval: root.voiceToken() !== "" ? (root.vc.card && root.vc.card.power ? 10000 : 30000) : 8000
        onTriggered: voicePopup.close()
    }

    // ---------- ติดตั้งแอปที่ไม่มีในเครื่อง (การ์ด 0054) · ตกลง/ยกเลิก (ไม่ต้องใส่รหัส · Pakon 2026-10-23) ·
    // ตัวติดตั้ง root ตรวจเองว่าอยู่ในรายการและดิสก์พอ ----------
    Connections {
        target: skills
        function onAppInstallDone(card) { installPopup.close(); root.showCard(card) }
    }
    Popup {
        id: installPopup
        objectName: "installPopup"
        property string key: ""
        property string name: ""
        function openFor(k, n) { key = k; name = n; installError.text = ""; open() }
        anchors.centerIn: Overlay.overlay
        width: Math.min(520, root.width - 32)
        modal: true
        closePolicy: skills.installing !== "" ? Popup.NoAutoClose : Popup.CloseOnEscape
        padding: 20
        background: Rectangle { radius: Theme.radiusLarge; color: Theme.surface; border.width: 1; border.color: Theme.line }
        contentItem: ColumnLayout {
            spacing: 12
            AppText { text: Tr.t("ติดตั้ง ") + installPopup.name + Tr.t(" ไหม?"); strong: true; Layout.fillWidth: true }
            AppText {
                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                text: Tr.t("ติดตั้งแล้วทุกบัญชีในเครื่องใช้ได้ · ใช้เวลาหลายนาทีและต้องต่ออินเทอร์เน็ต")
            }
            AppText { id: installError; visible: text !== ""; color: Theme.warnInk; size: Theme.fontSmall; Layout.fillWidth: true }
            AppText {
                visible: skills.installing !== ""
                text: Tr.t("กำลังติดตั้ง ") + skills.installing + Tr.t(" … อย่าปิดเครื่อง")
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                AppButton {
                    text: Tr.t("ยกเลิก"); kind: "secondary"
                    enabled: skills.installing === ""
                    onClicked: installPopup.close()
                }
                AppButton {
                    objectName: "installGo"
                    text: Tr.t("ตกลง"); kind: "primary"
                    enabled: skills.installing === ""
                    onClicked: if (!skills.installApp(installPopup.key))
                                   installError.text = Tr.t("เริ่มติดตั้งไม่ได้ (มีการติดตั้งอื่นอยู่)")
                }
            }
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
            AppText { text: Tr.t("ประวัติบทสนทนา"); strong: true }
            AppText {
                Layout.fillWidth: true
                visible: chat.history.length === 0
                text: Tr.t("ยังไม่มีบทสนทนาที่บันทึกไว้")
                size: Theme.fontSmall; color: Theme.inkMuted
            }
            Repeater {
                model: chat.history.slice(0, 12)
                AppButton {
                    required property var modelData
                    Layout.fillWidth: true
                    kind: "ghost"
                    text: modelData.title || Tr.t("(ไม่มีชื่อ)")
                    onClicked: { root.loadChat(chat.openChat(modelData.id)); historyPopup.close() }
                }
            }
        }
    }

    // ---------- ขั้นตอนเชื่อมต่อ Claude (การ์ด 0021) · หน้าต่างกลางจอ เลื่อนได้เมื่อตัวอักษรใหญ่ ----------
    Popup {
        id: guidePopup
        objectName: "claudeGuidePopup"
        modal: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(720, root.width - 48)
        height: Math.min(guideCol.implicitHeight + 2 * padding, root.height - 48)
        padding: 24
        onClosed: Qt.callLater(root.focusInput)
        background: Rectangle { radius: Theme.radiusLarge; color: Theme.surface; border.width: 1; border.color: Theme.line }
        contentItem: Flickable {
            contentWidth: width
            contentHeight: guideCol.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            ColumnLayout {
                id: guideCol
                width: parent.width
                spacing: 16
                RowLayout {
                    Layout.fillWidth: true
                    AppText { text: Tr.t("เชื่อมต่อ Claude"); size: Theme.fontHeading; strong: true; Layout.fillWidth: true }
                    AppButton { objectName: "claudeGuideClose"; kind: "secondary"; text: Tr.t("ปิด", "หน้าต่าง"); onClicked: guidePopup.close() }
                }
                AppText {
                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                    text: Tr.t("ทำครั้งเดียวต่อบัญชี · การเข้าสู่ระบบ Claude เป็นของบัญชีนี้คนเดียว คนอื่นในเครื่องใช้ไม่ได้")
                }
                // ทางที่ 2 (การ์ด 0021 หัวข้อ 10): เปิดหน้าต่างคำสั่งบนจอนี้ · ไม่ต้องใช้คอมพิวเตอร์อีกเครื่อง
                Rectangle {
                    objectName: "claudeConnectHereBox"
                    visible: cloudUsage.canConnectHere
                    Layout.fillWidth: true
                    implicitHeight: hereCol.implicitHeight + 32
                    radius: Theme.radiusCard
                    color: Theme.accentSoft
                    ColumnLayout {
                        id: hereCol
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 16
                        spacing: 8
                        AppText { text: Tr.t("เชื่อมต่อที่เครื่องนี้ (ง่ายที่สุด)"); strong: true; color: Theme.accentInk; Layout.fillWidth: true }
                        AppText {
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.accentInk
                            text: Tr.t("กดปุ่มแล้วหน้าต่างเชื่อมต่อจะเปิดขึ้น ติดตั้งให้เอง แล้วหน้าเข้าสู่ระบบ Claude จะเปิดใน Chromium · ")
                                  + Tr.t("เข้าสู่ระบบเสร็จ กลับมาที่หน้าต่างเชื่อมต่อ พิมพ์ /exit แล้วกด Enter")
                        }
                        AppButton {
                            objectName: "claudeConnectHere"
                            enabled: !cloudUsage.connecting
                            iconPath: Icons.terminal
                            text: cloudUsage.connecting ? Tr.t("หน้าต่างเชื่อมต่อเปิดอยู่…") : Tr.t("เชื่อมต่อที่เครื่องนี้")
                            onClicked: cloudUsage.connectHere()
                        }
                        AppText {
                            objectName: "claudeConnectedNow"
                            visible: cloudUsage.connectedNow
                            Layout.fillWidth: true; strong: true; color: Theme.okInk
                            text: Tr.t("เชื่อมต่อแล้ว · ออกจากระบบแล้วเข้าใหม่ เพื่อเริ่มใช้ Claude")
                        }
                    }
                }
                AppText {
                    visible: cloudUsage.canConnectHere
                    text: Tr.t("หรือใช้คอมพิวเตอร์อีกเครื่อง"); strong: true; Layout.fillWidth: true; Layout.topMargin: 4
                }
                ClaudeGuide { Layout.fillWidth: true }
            }
        }
    }

    // ---------- นัดที่พลาดขณะปิดเครื่อง/ไม่ได้เข้าใช้ และคำเตือนเรื่องไฟล์/นาฬิกา (การ์ด 0001, H2) ----------
    Rectangle {
        id: notice
        property bool dismissed: false
        readonly property string missedText: skills.missed.length === 0 ? ""
            : Tr.t("พลาดการเตือน ") + skills.missed.length + Tr.t(" รายการขณะไม่ได้ใช้เครื่อง: ")
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
            AppButton { text: Tr.t("รับทราบ"); kind: "secondary"; onClicked: notice.dismissed = true }
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
        width: root.wideWidth
        spacing: 12   // การ์ด 0041: แผง 3 ช่องต้องพอดีจอ 1280×720 ที่ตัวอักษร 100%

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
                // แชทงานส่งออกนอกเครื่อง → ห้ามเขียนว่า "ทำในเครื่อง" (H5 · การ์ด 0053)
                text: chat.mode === "work"
                      ? Tr.t("แชทงาน · ข้อความที่พิมพ์ส่งให้ Claude (") + uiSettings.cloudModel + Tr.t(") นอกเครื่อง")
                      : chat.workReady   // ไฮบริด: ถามยาก/ข้อมูลสดจะส่ง Claude (H5 · ห้ามบอกว่าทำในเครื่องทั้งหมด)
                        ? Tr.t("วันนี้ให้ช่วยอะไรดี · AI ในเครื่องตอบก่อน ถ้าต้องใช้ข้อมูลสดจะถาม Claude")
                        : Tr.t("วันนี้ให้ช่วยอะไรดี · ทุกอย่างทำในเครื่องนี้")
                color: Theme.inkMuted; oneLine: true
            }
            // อ่านสรุปวันนี้ให้ฟัง (การ์ด 0019) · สำหรับคนที่ไม่สะดวกอ่านจอ · ใช้ข้อมูลเดียวกับการ์ดข้างล่าง
            AppButton {
                objectName: "briefingButton"
                Layout.alignment: Qt.AlignHCenter
                visible: voice.available
                kind: "ghost"
                iconPath: Icons.chat
                text: voice.speakingKey === -2 ? Tr.t("หยุดอ่าน") : Tr.t("อ่านสรุปวันนี้ให้ฟัง")
                onClicked: voice.speakingKey === -2 ? voice.stop() : voice.speak(-2, root.briefingText())
            }
        }

        // ที่ว่างให้ช่องพิมพ์วางทับ (ช่องพิมพ์ตัวจริงอยู่ข้างล่าง ตำแหน่งผูกกับ Item นี้)
        Item { id: composerSlot; Layout.fillWidth: true; Layout.preferredHeight: composer.height + hint.height + 6 }

        // คีย์ลัดพูดสั่งงาน (การ์ด 0024/0040) · แสดงเฉพาะเมื่อคีย์ลัดใช้ได้จริงในเซสชันนี้ (H5)
        RowLayout {
            objectName: "hotkeyHint"
            visible: hotkeyReady
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            Rectangle {
                implicitWidth: f9.implicitWidth + 16; implicitHeight: f9.implicitHeight + 6
                radius: 6; color: Theme.surface2; border.width: 1; border.color: Theme.line
                AppText { id: f9; anchors.centerIn: parent; text: "F9"; strong: true; size: Theme.fontCaption; oneLine: true }
            }
            AppText { text: Tr.t("กดแล้วพูดได้ทุกหน้า · ไทยหรืออังกฤษก็ได้"); size: Theme.fontSmall; color: Theme.inkFaint; oneLine: true }
        }

        // ---------- แผงหน้าแรก (การ์ด 0041): นัด · เปิดเว็บ · ลองถาม · จอกว้าง = 3 ช่องเรียงกัน · ตัวอักษรใหญ่/จอแคบ = เรียงลง ----------
        GridLayout {
            id: bento
            objectName: "homePanels"
            readonly property bool wide: homeCol.width >= 960 && Theme.fontScale <= 1.25
            Layout.fillWidth: true
            columns: wide ? 3 : 1
            columnSpacing: 16
            rowSpacing: 16

            // นัดถัดไป (จาก skills.upcoming จริง · การ์ด 0001) · 3 รายการแรก · "ดูทั้งหมด" = หน้าปฏิทิน
            Card {
                objectName: "nextReminderCard"
                Layout.fillWidth: !bento.wide
                Layout.preferredWidth: bento.wide ? 300 : -1
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignTop
                implicitHeight: remCol.implicitHeight + 36
                ColumnLayout {
                    id: remCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 18
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Icon { path: skills.reminderWarning !== "" ? Icons.alert : Icons.calendar; color: Theme.accent; width: 20; height: 20 }
                        AppText { text: Tr.t("นัดถัดไป"); size: Theme.px(18); strong: true; oneLine: true; Layout.fillWidth: true }
                        AppButton { objectName: "agendaAll"; text: Tr.t("ดูทั้งหมด"); kind: "ghost"; onClicked: AppState.open("calendar") }
                    }
                    AppText {
                        visible: skills.reminderWarning !== ""
                        Layout.fillWidth: true
                        text: skills.reminderWarning; color: Theme.warnInk; size: Theme.fontSmall
                    }
                    AppText {
                        visible: skills.reminderWarning === "" && skills.upcoming.length === 0
                        Layout.fillWidth: true
                        text: Tr.t("ยังไม่มีนัด") + " · " + Tr.t("ลองพิมพ์ “เตือน…” ในช่องด้านบน"); size: Theme.fontSmall; color: Theme.inkMuted
                    }
                    Repeater {
                        model: skills.reminderWarning === "" ? skills.upcoming.slice(0, 3) : []
                        Rectangle {
                            required property var modelData
                            required property int index
                            objectName: "upcomingItem"
                            Layout.fillWidth: true
                            implicitHeight: upCol.implicitHeight + 20
                            radius: Theme.radiusCard
                            color: Theme.surface2
                            Rectangle { x: 0; y: 10; width: 3; height: parent.height - 20; radius: 2; color: index === 0 ? Theme.accent : Theme.line }
                            ColumnLayout {
                                id: upCol
                                anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 14; anchors.rightMargin: 10
                                spacing: 2
                                AppText { text: modelData.when; size: Theme.fontCaption; color: Theme.accentInk; oneLine: true }
                                AppText { text: modelData.what; strong: index === 0; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                            }
                        }
                    }
                    // นัดแรกแบบอ่านอย่างเดียว (เทสต์ของการ์ด 0001 อ่านจากสองชื่อนี้ · ไม่แสดงซ้ำบนจอ)
                    AppText {
                        objectName: "nextReminderWhat"
                        visible: false
                        text: skills.upcoming.length > 0 ? skills.upcoming[0].what : Tr.t("ยังไม่มีนัด")
                    }
                    Chip { objectName: "nextReminderWhen"; visible: false; text: skills.upcoming.length > 0 ? skills.upcoming[0].when : "" }
                    AppButton {
                        objectName: "addReminder"
                        kind: "outline"; iconPath: Icons.plus
                        text: Tr.t("เพิ่มนัด/เตือน")
                        onClicked: root.putInInput(Tr.t("เตือน", "ช่องพิมพ์"))
                    }
                }
            }

            // แอปเว็บที่ใช้บ่อย (การ์ด 0031) · ไอคอนทั่วไป ไม่ใช้โลโก้ของบริษัท · กดแล้วไปทางเดียวกับพิมพ์ "เปิด…"
            // (เบราว์เซอร์ของผู้ช่วย = เข้าสู่ระบบครั้งเดียว ใช้ได้ทั้งปุ่ม พิมพ์ และเสียง) · ผู้ใช้ใส่รหัสในหน้าเว็บของบริการเอง
            Card {
                objectName: "webAppsCard"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignTop
                implicitHeight: appsCol.implicitHeight + 36
                ColumnLayout {
                    id: appsCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 18
                    spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Icon { path: Icons.globe; color: Theme.accent; width: 20; height: 20 }
                        AppText { text: Tr.t("เปิดเว็บและแอป"); size: Theme.px(18); strong: true; oneLine: true; Layout.fillWidth: true }
                        AppText { visible: bento.wide; text: Tr.t("แตะเพื่อเปิด · หรือพูด “เปิด…”"); size: Theme.fontCaption; color: Theme.inkFaint; oneLine: true }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: Math.max(2, Math.min(4, Math.floor(appsCol.width / 116)))
                        columnSpacing: 10
                        rowSpacing: 10
                        Repeater {
                            model: [
                                { key: "youtube", name: "YouTube", icon: Icons.play },
                                { key: "gmail", name: "Gmail", icon: Icons.mail },
                                { key: "calendar", name: Tr.t("ปฏิทิน Google"), glyph: "31" },
                                { key: "drive", name: Tr.t("ไดรฟ์ Google"), icon: Icons.folder },
                                { key: "docs", name: Tr.t("เอกสาร Google"), icon: Icons.file },
                                { key: "news", name: Tr.t("ข่าว Thai PBS"), icon: Icons.globe },
                                { key: "netflix", name: "Netflix", icon: Icons.play },
                                { key: "spotify", name: "Spotify", icon: Icons.speaker }
                            ]
                            AppTile {
                                required property var modelData
                                objectName: "webApp_" + modelData.key
                                Layout.fillWidth: true
                                // สูงเท่ากันทุกไทล์ (ชื่อยาวขึ้น 2 บรรทัดได้): ไอคอน 44 + ระยะ 8 + ชื่อ 2 บรรทัด + ขอบ
                                Layout.preferredHeight: Math.ceil(72 + 2 * Theme.fontSmall * 1.62)
                                iconPath: modelData.icon || ""
                                glyph: modelData.glyph || ""
                                text: modelData.name
                                onClicked: appsNote.text = skills.openSite(modelData.key)
                            }
                        }
                    }
                    // ผลการเปิด: เปิดด้วยเบราว์เซอร์ปกติแทน / จำลอง (เครื่องพัฒนา) / ไม่สำเร็จ · สำเร็จ = เบราว์เซอร์ขึ้นจอแล้ว ล้างข้อความ
                    AppText {
                        id: appsNote
                        objectName: "webAppsNote"
                        visible: text !== ""
                        Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                    }
                }
            }

            // ลองถาม · แตะ = ใส่ข้อความในช่องพิมพ์ (แก้ได้ก่อนส่ง · ไม่ส่งเอง · การ์ด 0041)
            Card {
                objectName: "askPanel"
                Layout.fillWidth: !bento.wide
                Layout.preferredWidth: bento.wide ? 260 : -1
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignTop
                implicitHeight: askCol.implicitHeight + 36
                ColumnLayout {
                    id: askCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 18
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Icon { path: Icons.sparkle; color: Theme.accent; width: 20; height: 20 }
                        AppText { text: Tr.t("ลองถาม"); size: Theme.px(18); strong: true; oneLine: true; Layout.fillWidth: true }
                    }
                    Repeater {
                        model: [
                            "วันนี้ต้องทำอะไรบ้าง",
                            "เตือนส่งรายงานพรุ่งนี้บ่ายสอง",
                            "ทำไมเครื่องช้า",
                            "สรุปข้อความนี้ให้หน่อย: ",
                        ].concat(skills.canForge ? ["เปิดโหมดทำงานให้หน่อย"] : [])
                        Button {
                            id: ask
                            required property string modelData
                            objectName: "askItem"
                            Layout.fillWidth: true
                            hoverEnabled: true
                            padding: 12
                            implicitHeight: Math.max(Theme.touch, askText.implicitHeight + 2 * padding)
                            text: "“" + Tr.t(modelData).replace(/: $/, "") + "”"
                            Accessible.name: text
                            Keys.onReturnPressed: (event) => { ask.clicked(); event.accepted = true }
                            onClicked: root.putInInput(Tr.t(modelData))
                            background: Rectangle {
                                radius: Theme.radiusCard
                                color: ask.down ? Theme.accentSoft : Theme.surface2
                                border.width: ask.visualFocus ? 2 : ask.hovered ? 1 : 0
                                border.color: Theme.accent
                            }
                            contentItem: AppText { id: askText; text: ask.text; size: Theme.px(15); maximumLineCount: 2; elide: Text.ElideRight }
                        }
                    }
                }
            }
        }

        // ยังไม่ได้เชื่อมต่อ Claude (การ์ด 0021) · แถบสั้นใต้คำทักทาย · กดแล้วขั้นตอนขึ้นเป็นหน้าต่างกลางจอ ·
        // "ไว้ทีหลัง" ซ่อนแค่ในเซสชันนี้ (เข้าใหม่ขึ้นอีกจนกว่าจะเชื่อมต่อ) · มี claude แล้ว = ไม่แสดง (H5)
        Card {
            id: connectCard
            objectName: "claudeConnectCard"
            property bool later: false
            visible: !cloudUsage.available && !later
            Layout.fillWidth: true
            implicitHeight: visible ? connectRow.implicitHeight + 28 : 0
            RowLayout {
                id: connectRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                spacing: 12
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    implicitWidth: 40; implicitHeight: 40; radius: 20
                    color: Theme.accentSoft
                    Icon { anchors.centerIn: parent; path: Icons.globe; color: Theme.accentInk; width: 20; height: 20 }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    AppText { text: Tr.t("เชื่อมต่อ Claude เพื่อถามข่าวและข้อมูลสด"); strong: true; Layout.fillWidth: true }
                    AppText {
                        Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                        text: cloudUsage.connectedNow
                              ? Tr.t("เชื่อมต่อแล้ว · ออกจากระบบแล้วเข้าใหม่ เพื่อเริ่มใช้ Claude")
                              : Tr.t("ตอนนี้ตอบได้เฉพาะ AI ในเครื่อง · เชื่อมต่อครั้งเดียวต่อบัญชี แล้ว Claude ช่วยสร้างสกิลใหม่ได้ด้วย")
                    }
                }
                AppButton {
                    objectName: "claudeConnectLater"
                    kind: "ghost"
                    text: Tr.t("ไว้ทีหลัง")
                    onClicked: connectCard.later = true
                }
                AppButton {
                    objectName: "claudeConnectOpen"
                    text: Tr.t("ดูวิธีเชื่อมต่อ")
                    onClicked: { cloudUsage.refreshGuide(); guidePopup.open() }
                }
            }
        }

        // แนะนำการใช้งานครั้งแรก (ฟีเจอร์ข้อ 8) · ตัวอย่างอยู่ในแผง "ลองถาม" (การ์ด 0041) · "เข้าใจแล้ว" = ไม่ขึ้นอีก (จำในไฟล์ตั้งค่า)
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
                AppText { text: Tr.t("ยินดีต้อนรับ · เริ่มจากแผงด้านบนได้เลย"); strong: true; Layout.fillWidth: true }
                AppText {
                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                    text: Tr.t("แชท นัด และไฟล์เก็บในเครื่องนี้ในโฟลเดอร์ของคุณ · คำสั่งเครื่องกับคำถามทั่วไป AI ในเครื่องทำเอง")
                          + (skills.canForge ? Tr.t(" · ข้อมูลสด (อากาศ ข่าว) และงานใหม่ที่ยังไม่มีสกิล จะส่งเฉพาะประโยคนั้นให้ Claude") : "")
                          + Tr.t(" · ตั้งเข้าเครื่องด้วยใบหน้าได้ที่หน้าตั้งค่า")
                }
                AppButton {
                    objectName: "onboardingDone"
                    text: Tr.t("เข้าใจแล้ว")
                    onClicked: uiSettings.finishOnboarding()
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
        // · เลื่อนหลังวาดรอบนี้เสร็จ (callLater): พบ 2026-10-12 วางข้อความยาวมาก → ค้างบนสุด ไม่เห็นคำตอบใหม่
        onContentHeightChanged: Qt.callLater(positionViewAtEnd)
        onCountChanged: Qt.callLater(positionViewAtEnd)
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
                        // ตอบโดย Claude = หัวต้องบอกว่า Claude (พบบนจอ Pi: หัวเขียน "AI ในเครื่อง" แต่หมายเหตุบอก Claude)
                        text: ((row.modelData.note || "").indexOf("ตอบโดย Claude") === 0 ? "Claude (cloud)" : Tr.t("AI ในเครื่อง"))
                              + (row.modelData.skill ? " · " + Tr.x(row.modelData.skill) : "")
                        size: Theme.fontCaption; color: Theme.inkMuted
                    }
                    AppText {
                        objectName: "aiText"
                        Layout.fillWidth: true
                        textFormat: Text.PlainText  // ค่าเริ่มต้น AutoText เดาเป็น HTML ได้ถ้าคำตอบหน้าตาเหมือนแท็ก
                        // sys = ข้อความของระบบ (ผลคำสั่งเบราว์เซอร์) แปลตามภาษา · คำตอบของ AI แสดงตามที่ AI เขียน
                        text: root.tidy(row.modelData.done ? (row.modelData.sys ? Tr.x(row.modelData.text) : row.modelData.text)
                                                           : (chat.streamText !== "" ? chat.streamText : Tr.t("กำลังอ่านข้อความ…")))
                    }
                    AppText {
                        visible: !!row.modelData.note
                        Layout.fillWidth: true
                        text: Tr.x(row.modelData.note || "")
                        size: Theme.fontSmall; color: Theme.warnInk
                    }
                    // เอาคำตอบไปใช้ต่อ (เช่น จดหมายที่ร่าง) · คลิปบอร์ดอยู่ในเครื่อง ไม่ได้ส่งไปไหน
                    RowLayout {
                        spacing: 4
                        visible: !!row.modelData.done && (row.modelData.text || "") !== ""
                        AppButton {
                            objectName: "copyAnswer"
                            text: root.copiedRow === row.index ? Tr.t("คัดลอกแล้ว") : Tr.t("คัดลอก")
                            kind: "ghost"
                            onClicked: { chat.copyText(row.modelData.text); root.copiedRow = row.index }
                        }
                        // อ่านออกเสียงในเครื่อง (การ์ด 0019) · ไม่ได้ติดตั้งตัวอ่าน = ไม่มีปุ่ม
                        AppButton {
                            objectName: "speakAnswer"
                            visible: voice.available
                            text: voice.speakingKey === row.index ? Tr.t("หยุดอ่าน") : Tr.t("ฟังคำตอบนี้")
                            kind: "ghost"
                            onClicked: {
                                root.speakRow = row.index
                                voice.speakingKey === row.index ? voice.stop() : voice.speak(row.index, root.tidy(row.modelData.text))
                            }
                        }
                    }
                    WhyPanel {
                        visible: !!row.modelData.done && (row.modelData.why || []).length > 0
                        rows: row.modelData.why || []
                        Layout.fillWidth: true
                    }
                    AppText {
                        objectName: "speakError"
                        visible: root.speakRow === row.index && voice.message !== ""
                        Layout.fillWidth: true
                        text: Tr.x(voice.message)
                        size: Theme.fontSmall; color: Theme.warnInk
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
                undone: !!root.answered[(row.modelData.card || {}).undoToken]
                onUndo: {
                    const t = row.modelData.card.undoToken
                    const a = Object.assign({}, root.answered)
                    a[t] = true
                    root.answered = a
                    root.showCard(skills.undo(t))
                }
                onRemoveSkill: (skillId) => root.showCard(skills.removeSkill(skillId))
                onSummarizeFile: (path) => {
                    const err = chat.attachFile(path)
                    if (err !== "") { root.showCard({ kind: "chat", title: err, chips: [], lines: [], confirmToken: "", page: "", badge: {} }); return }
                    input.text = Tr.t("สรุปเนื้อหาไฟล์นี้เป็นข้อ ๆ สั้น ๆ")
                    root.send()
                }
                onAskFile: (path) => {
                    const err = chat.attachFile(path)
                    if (err === "") input.forceActiveFocus()
                    else root.showCard({ kind: "chat", title: err, chips: [], lines: [], confirmToken: "", page: "", badge: {} })
                }
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
                                     ? Tr.t("บอกว่าสกิล “") + root.feedbackFor.name + Tr.t("” ผิดตรงไหน เช่น ให้เปิด Gmail แทน · Esc = ยกเลิก")
                                     : chat.mode === "work" ? Tr.t("พิมพ์ข้อความถึง Claude (แชทงาน · ส่งออกนอกเครื่อง)")
                                     : Tr.t("พิมพ์ข้อความถึงผู้ช่วย AI")
                    placeholderTextColor: Theme.inkFaint
                    color: Theme.ink
                    font.family: Theme.family
                    font.pixelSize: Theme.fontBody
                    wrapMode: TextEdit.Wrap
                    verticalAlignment: TextEdit.AlignVCenter
                    background: null
                    Accessible.name: Tr.t("ข้อความ")
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
                // แตะครั้งเดียวเพื่อพูด (การ์ด 0019 ข้อ 10 · Pakon เลือก) · พูดจบแล้วเงียบ ~1 วิ = หยุดเอง · แตะซ้ำ = หยุดทันที
                // ข้อความที่ถอดได้ใส่ช่องพิมพ์ ไม่ส่งเอง
                objectName: "micButton"
                visible: voice.micAvailable
                enabled: !voice.transcribing && !chat.busy
                kind: voice.listening ? "warn" : "secondary"
                iconPath: Icons.mic
                text: voice.listening ? Tr.t("กำลังฟัง · แตะเพื่อหยุด") : voice.transcribing ? Tr.t("กำลังถอด…") : ""
                Accessible.name: Tr.t("แตะเพื่อพูด")
                onClicked: voice.listening ? voice.stopListening() : voice.startListening()
            }
            AppButton {
                objectName: "sendButton"
                text: chat.busy ? Tr.t("หยุด") : Tr.t("ส่ง"); iconPath: chat.busy ? Icons.stop : Icons.send
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
                      ? Tr.t("ข้อความถัดไปจะส่งให้ Claude แก้สกิล “") + root.feedbackFor.name + Tr.t("” · บอกว่าผิดตรงไหน")
                      : ""
                size: Theme.fontSmall; color: Theme.warnInk
            }
            AppButton { text: Tr.t("ยกเลิก"); kind: "ghost"; onClicked: root.feedbackFor = null }
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
                text: Tr.t("ถามเกี่ยวกับไฟล์ “") + chat.attachedFile + Tr.t("” · AI ในเครื่องอ่าน ไม่ส่งไฟล์ออกนอกเครื่อง")
                size: Theme.fontSmall; color: Theme.accentInk
            }
            AppButton { text: Tr.t("เลิกแนบ"); kind: "ghost"; onClicked: chat.detachFile() }
        }
    }
    AppText {
        id: hint
        parent: composer.parent
        anchors.top: composer.bottom
        anchors.topMargin: 6
        anchors.horizontalCenter: parent.horizontalCenter
        objectName: "chatHint"
        text: chat.notice !== "" ? Tr.x(chat.notice)
              : voice.listening ? Tr.t("กำลังฟัง · พูดจบแล้วเงียบสักครู่ ระบบหยุดเอง (หรือแตะไมค์อีกครั้ง)")
              : voice.micMessage !== "" ? Tr.x(voice.micMessage)
              : chat.busy ? Tr.t("Esc หรือปุ่มหยุด = หยุดตอบ") : Tr.t("Enter ส่ง · Shift+Enter ขึ้นบรรทัดใหม่")
        size: Theme.fontCaption; color: chat.notice !== "" ? Theme.warnInk : Theme.inkFaint; oneLine: true
    }
}
