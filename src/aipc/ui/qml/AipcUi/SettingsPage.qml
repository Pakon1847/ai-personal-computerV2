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
                    AppText { text: "Claude (ถามข้อมูลสด · สร้างสกิล)"; strong: true }
                    AppText {
                        objectName: "cloudUsageText"
                        Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                        text: !cloudUsage.available
                              ? "บัญชีนี้ยังไม่ได้ติดตั้งหรือเข้าสู่ระบบ Claude Code · ใช้ได้แค่ AI ในเครื่อง"
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
            RowLayout {
                visible: cloudUsage.available
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
        visible: cloudUsage.available
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
                              : "ส่งไป Claude แล้ว " + cloudUsage.outboundTotal + " ครั้ง · แสดงข้อความที่ส่งจริงตามตัวอักษร · แชทอื่น นัด และไฟล์ไม่เคยถูกส่ง"
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
