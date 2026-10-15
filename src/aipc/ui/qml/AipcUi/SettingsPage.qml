// หน้าตั้งค่า · ธีมและขนาดตัวอักษรทำงานจริงและบันทึกลง ~/.config/aipc/ui.json
// ใบหน้าของฉัน (การ์ด 0006) ลงทะเบียน/ทดลอง/ลบได้จริง · การตรวจเจ้าของ (ปิดบัง/ล็อก) ไม่มีในรุ่นนี้ (ขอบเขตรอบ 3)
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    spacing: 16

    PageHeader { title: "ตั้งค่า" }

    Card {
        Layout.fillWidth: true
        Layout.preferredHeight: themeCol.implicitHeight + 40
        radius: Theme.radiusCard
        ColumnLayout {
            id: themeCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    AppText { text: "ธีม"; strong: true }
                    AppText { text: "เปลี่ยนทั้งระบบทันที รวมหน้า Login"; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                }
                AppCheck { text: "สว่าง"; radio: true; autoExclusive: true; checked: uiSettings.theme === "light"; onClicked: uiSettings.setTheme("light") }
                AppCheck { text: "มืด"; radio: true; autoExclusive: true; checked: uiSettings.theme === "dark"; onClicked: uiSettings.setTheme("dark") }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.lineSoft }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    AppText { text: "ขนาดตัวอักษร"; strong: true }
                    AppText { text: "100–200% ตาม BRIEF 5.7"; size: Theme.fontSmall; color: Theme.inkMuted }
                }
                Repeater {
                    model: [1.0, 1.25, 1.5, 1.75, 2.0]
                    AppButton {
                        required property real modelData
                        text: Math.round(modelData * 100) + "%"
                        kind: uiSettings.fontScale === modelData ? "primary" : "secondary"
                        onClicked: uiSettings.setFontScale(modelData)
                    }
                }
            }
        }
    }

    FacePanel { Layout.fillWidth: true }
    LoginFacePanel { Layout.fillWidth: true }

    // ประวัติแชทอยู่ใน home ของคุณเท่านั้น · ลบทั้งหมดได้ทันที (การ์ด 0013 ข้อ 4)
    Card {
        Layout.fillWidth: true
        implicitHeight: chatRow.implicitHeight + 40
        RowLayout {
            id: chatRow
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                AppText { text: "ประวัติแชท"; strong: true }
                AppText { id: chatDeleted; Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                          text: "เก็บในเครื่องนี้ในโฟลเดอร์ของคุณ · " + chat.history.length + " บทสนทนา" }
            }
            AppButton {
                objectName: "deleteChats"
                text: "ลบประวัติแชททั้งหมด"; kind: "secondary"; iconPath: Icons.trash
                enabled: chat.history.length > 0 && !chat.busy
                onClicked: chatDeleted.text = "ลบแล้ว " + chat.deleteAll() + " บทสนทนา"
            }
        }
    }

    // สำรอง/กู้ลงไดรฟ์ USB (ฟีเจอร์ข้อ 7 · ADR-012)
    Card {
        objectName: "backupCard"
        Layout.fillWidth: true
        implicitHeight: bkCol.implicitHeight + 40
        property int confirmRestore: -1
        id: bkCard
        ColumnLayout {
            id: bkCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    AppText { text: "สำรองข้อมูลลงไดรฟ์ USB"; strong: true }
                    AppText {
                        Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                        text: "แชท นัด สกิล ตั้งค่า และไฟล์ของฉัน · ไม่รวมใบหน้า (สมัครใหม่ได้) · ไฟล์ในไดรฟ์ไม่เข้ารหัส เก็บไดรฟ์ให้ดี"
                    }
                }
                AppButton { text: "หาไดรฟ์"; kind: "secondary"; enabled: !backupCtl.busy; onClicked: backupCtl.refresh() }
            }
            AppText {
                visible: backupCtl.drives.length === 0
                text: "ยังไม่เจอไดรฟ์ · เสียบไดรฟ์ USB แล้วกด “หาไดรฟ์”"
                size: Theme.fontSmall; color: Theme.inkFaint; Layout.fillWidth: true
            }
            Repeater {
                model: backupCtl.drives
                RowLayout {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    spacing: 8
                    AppText {
                        Layout.fillWidth: true; size: Theme.fontSmall
                        text: modelData.name + (modelData.count > 0 ? " · ชุดล่าสุด " + modelData.latest : " · ยังไม่มีชุดสำรอง")
                    }
                    AppButton { text: "สำรองลงไดรฟ์นี้"; enabled: !backupCtl.busy; onClicked: backupCtl.backupTo(index) }
                    AppButton {
                        visible: modelData.count > 0
                        enabled: !backupCtl.busy
                        text: bkCard.confirmRestore === index ? "กดอีกครั้งเพื่อกู้" : "กู้จากชุดล่าสุด"
                        kind: bkCard.confirmRestore === index ? "danger" : "secondary"
                        onClicked: {
                            if (bkCard.confirmRestore === index) { bkCard.confirmRestore = -1; backupCtl.restoreLatest(index) }
                            else bkCard.confirmRestore = index
                        }
                    }
                }
            }
            AppText {
                objectName: "backupMessage"
                visible: backupCtl.message !== ""
                text: backupCtl.message
                size: Theme.fontSmall; color: backupCtl.busy ? Theme.accentInk : Theme.inkMuted; Layout.fillWidth: true
            }
        }
    }

    // Claude (ไฮบริด + สกิลอัตโนมัติ): ใช้ไปเท่าไรวันนี้ + เพดานต่อวัน · ครบแล้วไม่เรียก Claude จนวันใหม่
    Card {
        objectName: "cloudUsageCard"
        Layout.fillWidth: true
        implicitHeight: cloudCol.implicitHeight + 40
        ColumnLayout {
            id: cloudCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    AppText { text: "ส่งข้อมูลออกนอกเครื่อง: Claude (ถามข้อมูลสด · สร้างสกิล) และอากาศ"; strong: true }
                    AppText {
                        objectName: "cloudUsageText"
                        Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                        text: !cloudUsage.available
                              ? "บัญชีนี้ยังไม่ได้ติดตั้งหรือเข้าสู่ระบบ Claude Code · ใช้ได้แค่ AI ในเครื่อง · กดดูวิธีเชื่อมต่อข้างล่าง"
                              : "วันนี้ใช้ไป $" + cloudUsage.spentToday.toFixed(2) + " จากเพดาน $" + cloudUsage.limit.toFixed(2)
                                + " · " + cloudUsage.callsToday + " ครั้ง · ราคาอ้างอิงที่ Claude รายงาน"
                    }
                }
                Chip {
                    visible: cloudUsage.available
                    text: cloudUsage.spentToday >= cloudUsage.limit ? "ครบเพดานวันนี้" : "ใช้ได้"
                    kind: cloudUsage.spentToday >= cloudUsage.limit ? "warn" : "ok"
                    dot: true
                }
            }
            // คู่มือเชื่อมต่อ Claude (การ์ด 0021): ติดตั้งและเข้าสู่ระบบแยกต่อบัญชีผ่าน SSH · มี claude แล้ว = ไม่แสดง (H5)
            AppButton {
                id: guideButton
                objectName: "claudeGuideButton"
                property bool open: false
                visible: !cloudUsage.available
                kind: "secondary"
                text: open ? "ซ่อนวิธีเชื่อมต่อ" : "วิธีเชื่อมต่อ Claude"
                onClicked: {
                    if (!open)
                        cloudUsage.refreshGuide()
                    open = !open
                }
            }
            ClaudeGuide {
                objectName: "claudeGuide"
                visible: guideButton.visible && guideButton.open
                Layout.fillWidth: true
            }
            AppCheck {
                objectName: "useClaudeCheck"
                visible: cloudUsage.available
                text: "ส่งคำถามที่ยากหรือต้องใช้ข้อมูลสดให้ Claude และให้ Claude สร้างสกิลใหม่"
                detail: uiSettings.useClaude
                        ? "ส่งเฉพาะคำถามและข้อความล่าสุดไม่เกิน 4 ข้อความ · ไม่ส่งไฟล์ นัด ใบหน้า · ดูสิ่งที่ส่งจริงได้ข้างล่าง"
                        : "ปิดอยู่: ใช้แค่ AI ในเครื่อง · ไม่มีข้อมูลออกไป Anthropic"
                checked: uiSettings.useClaude
                onClicked: uiSettings.setUseClaude(checked)
            }
            // สวิตช์อากาศ (แผงความเป็นส่วนตัว 2026-10-07): ทุกทางที่ข้อมูลออกนอกเครื่อง ผู้ใช้ปิดได้เอง
            AppCheck {
                objectName: "useWeatherCheck"
                text: "ถามพยากรณ์อากาศ: ส่งชื่อเมืองไป Open-Meteo"
                detail: uiSettings.useWeather
                        ? "ส่งแค่ชื่อเมืองหรือพิกัด · ไม่ส่งชื่อบัญชีหรือแชท"
                        : "ปิดอยู่: ถามอากาศแล้วไม่ส่งอะไรออกไป"
                checked: uiSettings.useWeather
                onClicked: uiSettings.setUseWeather(checked)
            }
            RowLayout {
                visible: cloudUsage.available && uiSettings.useClaude
                spacing: 8
                AppText { text: "เพดานต่อวัน"; size: Theme.fontSmall; color: Theme.inkMuted }
                Repeater {
                    model: cloudUsage.limits
                    AppButton {
                        required property real modelData
                        text: "$" + modelData.toFixed(2)
                        kind: cloudUsage.limit === modelData ? "primary" : "secondary"
                        onClicked: cloudUsage.setLimit(modelData)
                    }
                }
            }
        }
    }

    // ปฏิทิน Google แบบอ่านอย่างเดียว (การ์ด 0014): วางลิงก์ iCal ลับ → นัดจาก Google ขึ้นในคำตอบนัด หน้าแรก และเสียง
    // ลิงก์ผิด/ดึงไม่ได้ = ไม่จำลิงก์ · เครื่องไม่เห็นรหัสผ่าน Google · เลิกเชื่อมต่อต้องกดสองครั้ง
    Card {
        id: gcalCard
        objectName: "gcalCard"
        visible: skills.gcalAvailable
        Layout.fillWidth: true
        implicitHeight: gcalCol.implicitHeight + 40
        property bool guideOpen: false
        property bool confirmOff: false
        readonly property var steps: [
            "ใช้เบราว์เซอร์บนคอมพิวเตอร์เปิด calendar.google.com แล้วเข้าสู่ระบบบัญชี Google ของคุณ",
            "กดรูปเฟือง (การตั้งค่า) มุมขวาบน → “การตั้งค่า” → ด้านซ้ายกดชื่อปฏิทินของคุณ ใต้ “การตั้งค่าสำหรับปฏิทินของฉัน”",
            "เลื่อนลงไปที่ “ผสานรวมปฏิทิน” (Integrate calendar) → คัดลอก “ที่อยู่ลับในรูปแบบ iCal” (Secret address in iCal format)",
            "วางลิงก์ในช่องข้างล่างแล้วกด “เชื่อมต่อ” · ถ้าเผลอส่งลิงก์ให้คนอื่น ให้กด “รีเซ็ต” ใน Google แล้วนำลิงก์ใหม่มาวาง"
        ]
        Connections {
            target: skills
            // เชื่อมต่อสำเร็จ = ล้างลิงก์ออกจากช่อง (ไม่ค้างบนจอ)
            function onGcalChanged() { if (skills.gcalConnected) gcalLink.text = "" }
        }
        ColumnLayout {
            id: gcalCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    AppText { text: "ปฏิทิน Google (อ่านอย่างเดียว)"; strong: true }
                    AppText {
                        Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                        text: "นัดจาก Google จะขึ้นในคำตอบ “พรุ่งนี้มีนัดอะไร” หน้าแรก และคำถามด้วยเสียง · ใช้ได้แม้ไม่มีเน็ต (ใช้ข้อมูลที่ดึงไว้ล่าสุด) · เครื่องนี้แก้หรือลบนัดใน Google ไม่ได้"
                    }
                }
                Chip {
                    visible: skills.gcalConnected
                    text: "เชื่อมต่อแล้ว " + skills.gcalHint
                    kind: "ok"
                    dot: true
                }
            }
            // วันหยุดไทย (การ์ด 0033): ปฏิทินสาธารณะของ Google · ค่าเริ่มต้นปิด · ไม่ขึ้นกับปฏิทินส่วนตัว
            AppCheck {
                objectName: "holidaysCheck"
                visible: skills.holidaysAvailable
                enabled: !skills.holidaysBusy
                text: "วันหยุดไทย (ปฏิทินสาธารณะของ Google)"
                detail: skills.holidaysStatus !== "" ? skills.holidaysStatus
                        : skills.holidaysOn ? "เปิดอยู่" : "ปิดอยู่: ไม่ดึงอะไร · เปิดแล้วถามได้ เช่น “วันหยุดถัดไปคือวันอะไร”"
                checked: skills.holidaysOn
                // เปิดต้องรอดึงเสร็จ (ไม่มีเน็ต = เปิดไม่สำเร็จ) → ผูกช่องติ๊กกลับกับสถานะจริงทุกครั้ง ไม่ให้ติ๊กค้างทั้งที่ปิด (H5)
                onClicked: {
                    skills.setHolidays(checked)
                    checked = Qt.binding(function() { return skills.holidaysOn })
                }
            }
            // เตือนก่อนนัด (การ์ด 0032) · อ่านจากสำเนาในเครื่อง เตือนได้แม้ไม่มีเน็ต
            RowLayout {
                visible: skills.gcalConnected
                spacing: 8
                AppText { text: "เตือนก่อนนัด"; size: Theme.fontSmall; color: Theme.inkMuted }
                Repeater {
                    model: uiSettings.gcalAlertChoices
                    AppButton {
                        required property int modelData
                        objectName: "gcalAlert" + modelData
                        text: modelData === 0 ? "ไม่เตือน" : modelData + " นาที"
                        kind: uiSettings.gcalAlertMin === modelData ? "primary" : "secondary"
                        onClicked: uiSettings.setGcalAlertMin(modelData)
                    }
                }
            }
            AppText {
                objectName: "gcalStatus"
                visible: text !== ""
                Layout.fillWidth: true; size: Theme.fontSmall
                color: skills.gcalBusy ? Theme.accentInk : Theme.inkMuted
                text: skills.gcalStatus
            }
            AppButton {
                objectName: "gcalGuideButton"
                visible: !skills.gcalConnected
                kind: "secondary"
                text: gcalCard.guideOpen ? "ซ่อนวิธีรับลิงก์" : "วิธีรับลิงก์จาก Google (4 ขั้น)"
                onClicked: gcalCard.guideOpen = !gcalCard.guideOpen
            }
            Repeater {
                model: gcalCard.guideOpen && !skills.gcalConnected ? gcalCard.steps : []
                delegate: AppText {
                    required property string modelData
                    required property int index
                    objectName: "gcalGuideStep"
                    Layout.fillWidth: true
                    size: Theme.fontSmall
                    text: (index + 1) + ". " + modelData
                }
            }
            AppField {
                id: gcalLink
                objectName: "gcalLinkField"
                visible: !skills.gcalConnected
                Layout.fillWidth: true
                mono: true
                placeholder: "วางลิงก์ที่ขึ้นต้นด้วย https://calendar.google.com/…"
                hint: "ลิงก์นี้เป็นความลับ ใครได้ไปจะเห็นนัดของคุณ · อย่าส่งให้ใคร"
            }
            RowLayout {
                spacing: 8
                AppButton {
                    objectName: "gcalConnect"
                    visible: !skills.gcalConnected
                    text: "เชื่อมต่อ"
                    enabled: gcalLink.text.trim() !== "" && !skills.gcalBusy
                    onClicked: skills.gcalConnect(gcalLink.text)
                }
                AppButton {
                    objectName: "gcalSyncNow"
                    visible: skills.gcalConnected
                    kind: "secondary"
                    text: "ดึงตอนนี้"
                    enabled: !skills.gcalBusy
                    onClicked: skills.gcalSyncNow()
                }
                AppButton {
                    objectName: "gcalDisconnect"
                    visible: skills.gcalConnected
                    kind: gcalCard.confirmOff ? "danger" : "ghost"
                    text: gcalCard.confirmOff ? "กดอีกครั้งเพื่อเลิกเชื่อมต่อ" : "เลิกเชื่อมต่อ"
                    enabled: !skills.gcalBusy
                    onClicked: {
                        if (gcalCard.confirmOff) { skills.gcalDisconnect(); gcalCard.confirmOff = false }
                        else gcalCard.confirmOff = true
                    }
                }
            }
        }
    }

    // บัญชีเว็บในเครื่องนี้ (การ์ด 0031): การเข้าสู่ระบบ Facebook/Instagram/Gmail… อยู่ในโปรไฟล์เบราว์เซอร์ของผู้ช่วย (โฟลเดอร์ของผู้ใช้)
    // ออกจากบัญชีเว็บทั้งหมด = ลบโปรไฟล์นั้นของคนที่กด · ต้องกดสองครั้ง · backend ตรวจเจ้าของเซสชันเอง (H7)
    Card {
        id: webCard
        objectName: "webAccountsCard"
        Layout.fillWidth: true
        implicitHeight: webCol.implicitHeight + 40
        property bool confirmOut: false
        property string result: ""
        ColumnLayout {
            id: webCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10
            AppText { text: "บัญชีเว็บในเครื่องนี้"; strong: true }
            AppText {
                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                text: "ปุ่มแอปที่ใช้บ่อยในหน้าแรกเปิดเว็บในเบราว์เซอร์ของผู้ช่วย · ใส่รหัสผ่านในหน้าเว็บของบริการเอง ระบบไม่เห็นและไม่เก็บรหัสผ่าน"
            }
            AppText {
                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                text: "ใครเข้าบัญชีเครื่องนี้ของคุณได้ จะเปิดเว็บที่เข้าสู่ระบบค้างไว้ได้ด้วย · ใช้เครื่องร่วมกับคนอื่นหรือจะคืนเครื่อง ให้กดปุ่มนี้"
            }
            AppButton {
                objectName: "webSignOut"
                kind: webCard.confirmOut ? "danger" : "secondary"
                iconPath: Icons.globe   // ไม่ใช้ไอคอนออกจากระบบ: นี่คือออกจากบัญชีเว็บ ไม่ใช่ออกจากเครื่อง (BRIEF 4)
                text: webCard.confirmOut ? "กดอีกครั้งเพื่อออกจากบัญชีเว็บทั้งหมด" : "ออกจากบัญชีเว็บทั้งหมด"
                enabled: !browser.busy
                onClicked: {
                    if (webCard.confirmOut) { webCard.result = browser.signOutAll(); webCard.confirmOut = false }
                    else { webCard.confirmOut = true; webCard.result = "" }
                }
            }
            AppText {
                objectName: "webSignOutResult"
                visible: webCard.result !== ""
                Layout.fillWidth: true; size: Theme.fontSmall
                text: webCard.result
            }
        }
    }

    // ล็อกเมื่อไม่ได้ใช้เครื่อง (aipc.ui.idle · ขั้น A 2026-10-06): ลืมออกแล้วลุกไป → ล็อกทุกหน้าต่าง → ออกเอง
    Card {
        objectName: "idleLockCard"
        Layout.fillWidth: true
        implicitHeight: idleCol.implicitHeight + 40
        ColumnLayout {
            id: idleCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10
            AppText { text: "ล็อกเมื่อไม่ได้ใช้เครื่อง"; strong: true }
            AppText {
                objectName: "idleLockText"
                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                text: uiSettings.lockMin === 0
                      ? "ปิดอยู่: ถ้าลืมกดออกแล้วลุกไป คนต่อไปจะเห็นงาน แชท และบัญชีเว็บที่เข้าไว้"
                      : "ไม่ได้แตะคีย์บอร์ดหรือเมาส์ " + uiSettings.lockMin + " นาที → ล็อกทุกหน้าต่าง (ปลดด้วยรหัสผ่าน) · ล็อกค้างอีก "
                        + uiSettings.logoutMin + " นาที → ออกจากระบบเอง งานที่ยังไม่บันทึกจะหาย"
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                AppText { text: "ล็อกหลังไม่ได้ใช้"; size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                Repeater {
                    model: uiSettings.lockChoices
                    AppButton {
                        required property int modelData
                        objectName: "lockMin" + modelData
                        text: modelData === 0 ? "ปิด" : modelData + " นาที"
                        kind: uiSettings.lockMin === modelData ? "primary" : "secondary"
                        onClicked: uiSettings.setLockMin(modelData)
                    }
                }
            }
            Flow {
                Layout.fillWidth: true
                visible: uiSettings.lockMin !== 0
                spacing: 8
                AppText { text: "ออกจากระบบหลังล็อก"; size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                Repeater {
                    model: uiSettings.logoutChoices
                    AppButton {
                        required property int modelData
                        objectName: "logoutMin" + modelData
                        text: modelData + " นาที"
                        kind: uiSettings.logoutMin === modelData ? "primary" : "secondary"
                        onClicked: uiSettings.setLogoutMin(modelData)
                    }
                }
            }
            // ขั้น C: กล้องช่วยดูว่าเจ้าของยังอยู่ · ต้องลงทะเบียน "ใบหน้าของฉัน" ก่อน · เปิดเอง
            AppCheck {
                objectName: "presenceCheck"
                enabled: face.state === "enrolled" || uiSettings.presence
                text: "ใช้กล้องช่วยดูว่าฉันยังนั่งอยู่"
                detail: face.state !== "enrolled" && !uiSettings.presence
                        ? "ต้องลงทะเบียน \"ใบหน้าของฉัน\" ด้านบนก่อน"
                        : "ไม่ได้แตะเครื่อง 10 วินาที → กล้องเปิด · ไม่เห็นหน้าคุณ " + uiSettings.presenceLockS
                          + " วินาที หรือเห็นคนอื่นแทน → ล็อก · ล็อกแล้วไม่มีใครอยู่อีก " + uiSettings.presenceLogoutS
                          + " วินาที → ออกจากระบบ · ไม่บันทึกภาพ · ไฟกล้องติดเฉพาะตอนกล้องเปิด"
                checked: uiSettings.presence
                onClicked: uiSettings.setPresence(checked)
            }
            Flow {
                Layout.fillWidth: true
                visible: uiSettings.presence
                spacing: 8
                AppText { text: "ล็อกเมื่อไม่เห็นหน้า"; size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                Repeater {
                    model: uiSettings.presenceChoices
                    AppButton {
                        required property int modelData
                        objectName: "presenceLock" + modelData
                        text: modelData + " วินาที"
                        kind: uiSettings.presenceLockS === modelData ? "primary" : "secondary"
                        onClicked: uiSettings.setPresenceLockS(modelData)
                    }
                }
            }
            Flow {
                Layout.fillWidth: true
                visible: uiSettings.presence
                spacing: 8
                AppText { text: "ออกหลังล็อกถ้าไม่มีใคร"; size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                Repeater {
                    model: uiSettings.presenceChoices
                    AppButton {
                        required property int modelData
                        objectName: "presenceLogout" + modelData
                        text: modelData + " วินาที"
                        kind: uiSettings.presenceLogoutS === modelData ? "primary" : "secondary"
                        onClicked: uiSettings.setPresenceLogoutS(modelData)
                    }
                }
            }
            AppText {
                objectName: "presenceStatusText"
                visible: uiSettings.presence && presenceStatus.text !== ""
                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                text: "สถานะ: " + presenceStatus.text
            }
        }
    }

    // เสียง (การ์ด 0019): อ่านออกเสียงในเครื่อง · ตั้งให้อ่านเตือนนัดได้
    Card {
        objectName: "voiceCard"
        Layout.fillWidth: true
        implicitHeight: voiceCol.implicitHeight + 40
        ColumnLayout {
            id: voiceCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 8
            AppText { text: "เสียง"; strong: true }
            AppText {
                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                text: voice.available
                      ? "อ่านออกเสียงในเครื่อง (Piper เสียงไทย tsync2) · กดอ่านครั้งแรกรอราว 7 วิ ครั้งต่อไปราว 1 วิ · ไม่ส่งเสียงออกนอกเครื่อง"
                      : "ยังไม่ได้ติดตั้งตัวอ่านออกเสียง (sudo ./scripts/pi/install-voice.sh --apply) หรือไม่มีตัวเล่นเสียง"
            }
            AppCheck {
                objectName: "speakAnswersCheck"
                visible: voice.available
                text: "อ่านคำตอบของ AI ออกเสียงเองทุกครั้ง (ปิด/เปิดได้จากปุ่มลำโพงในหน้าผู้ช่วย)"
                detail: "สำหรับคนที่ไม่สะดวกอ่านจอ · กดหยุดอ่านที่คำตอบได้"
                checked: uiSettings.speakAnswers
                onClicked: uiSettings.setSpeakAnswers(checked)
            }
            AppCheck {
                objectName: "speakRemindersCheck"
                visible: voice.available
                text: "อ่านเตือนนัดออกเสียงเมื่อถึงเวลา"
                detail: "ใช้ลำโพงของจอหรือที่ต่อกับเครื่อง"
                checked: uiSettings.speakReminders
                onClicked: uiSettings.setSpeakReminders(checked)
            }
        }
    }

    // สิ่งที่ส่งออกนอกเครื่อง: ทุกครั้งที่ส่งข้อความไป Claude (ข้อความที่ส่งจริง เวลา ค่าใช้จ่าย) · ล้างได้
    Card {
        id: outCard
        objectName: "outboundCard"
        visible: cloudUsage.available || cloudUsage.outboundTotal > 0  // สกิลอากาศส่งออกได้แม้ไม่มี Claude
        Layout.fillWidth: true
        implicitHeight: outCol.implicitHeight + 40
        property bool confirmClear: false
        property int openRow: -1
        ColumnLayout {
            id: outCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    AppText { text: "สิ่งที่ส่งออกนอกเครื่อง"; strong: true }
                    AppText {
                        objectName: "outboundSummary"
                        Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                        text: cloudUsage.outboundTotal === 0
                              ? "ยังไม่เคยส่งอะไรออกไป · แชท นัด และไฟล์อยู่ในเครื่องนี้เท่านั้น"
                              : "ส่งออกนอกเครื่องแล้ว " + cloudUsage.outboundTotal + " ครั้ง · แสดงข้อความที่ส่งจริงตามตัวอักษร · แชทอื่น นัด และไฟล์ไม่เคยถูกส่ง"
                    }
                }
                AppButton {
                    objectName: "clearOutbound"
                    visible: cloudUsage.outboundTotal > 0
                    kind: "ghost"
                    text: outCard.confirmClear ? "กดอีกครั้งเพื่อล้าง" : "ล้างประวัติ"
                    onClicked: {
                        if (outCard.confirmClear) { cloudUsage.clearOutbound(); outCard.confirmClear = false }
                        else outCard.confirmClear = true
                    }
                }
            }
            Repeater {
                model: cloudUsage.outbound
                delegate: ColumnLayout {
                    id: outRow
                    required property var modelData
                    required property int index
                    objectName: "outboundRow"
                    Layout.fillWidth: true
                    spacing: 2
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        AppText { text: outRow.modelData.when; size: Theme.fontSmall; color: Theme.inkMuted }
                        AppText { text: outRow.modelData.kind; size: Theme.fontSmall; strong: true }
                        AppText {
                            Layout.fillWidth: true
                            text: outRow.modelData.chars + " ตัวอักษร · $" + outRow.modelData.cost.toFixed(3)
                                  + (outRow.modelData.ok ? "" : " · ไม่สำเร็จ")
                            size: Theme.fontSmall; color: Theme.inkMuted
                        }
                        AppButton {
                            kind: "ghost"
                            text: outCard.openRow === outRow.index ? "ย่อ" : "ดูข้อความที่ส่ง"
                            onClicked: outCard.openRow = outCard.openRow === outRow.index ? -1 : outRow.index
                        }
                    }
                    AppText {
                        Layout.fillWidth: true
                        text: outCard.openRow === outRow.index ? outRow.modelData.sent : outRow.modelData.preview
                        size: Theme.fontSmall
                    }
                    AppText {
                        visible: outRow.modelData.note !== "" && outCard.openRow === outRow.index
                        Layout.fillWidth: true
                        text: outRow.modelData.note
                        size: Theme.fontCaption; color: Theme.inkMuted
                    }
                }
            }
        }
    }

    Item { Layout.fillHeight: true }
}
