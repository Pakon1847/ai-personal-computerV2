// หน้าตั้งค่า · ธีมและขนาดตัวอักษรทำงานจริงและบันทึกลง ~/.config/aipc/ui.json
// การ์ด 0061 (Pakon 2026-10-24 "หน้าตั้งค่าดูรกตา"): แบ่ง 6 หมวด · เมนูหมวดด้านซ้าย แสดงทีละหมวด ·
// ภาพเคลื่อนไหว 2 จุด (เนื้อหาจางเข้า + แถบเน้นเลื่อน) 200 ms · ปิดได้ (uiSettings.animations) ·
// ตัวเลือกทุกตัวย้ายมาทั้งก้อน การทำงานเหมือนเดิม
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: page
    objectName: "settingsPage"
    spacing: 16
    property string section: "look"
    // การ์ด 0067: ปุ่มเชื่อมปฏิทินในหน้าปฏิทินพามาที่นี่ = เปิดหมวด AI และอินเทอร์เน็ต + ขั้นตอนเชื่อม
    Connections {
        target: AppState
        function onSettingsFocusChanged() {
            if (AppState.settingsFocus !== "gcal") return
            page.section = "ai"
            gcalCard.guideOpen = true
            AppState.settingsFocus = ""
        }
    }
    readonly property var sections: [
        { id: "look", text: Tr.t("หน้าตาและการใช้"), icon: Icons.sliders },
        { id: "face", text: Tr.t("ใบหน้าและการล็อก"), icon: Icons.lock },
        { id: "voice", text: Tr.t("เสียงและไมค์"), icon: Icons.mic },
        { id: "ai", text: Tr.t("AI และอินเทอร์เน็ต"), icon: Icons.globe },
        { id: "privacy", text: Tr.t("ความเป็นส่วนตัว"), icon: Icons.shield },
        { id: "backup", text: Tr.t("สำรองข้อมูล"), icon: Icons.archive }
    ]
    function go(id) {
        if (id === section) return
        section = id
        if (uiSettings.animations) enter.restart()
    }
    function step(d) {
        const i = sections.findIndex(s => s.id === section)
        go(sections[(i + d + sections.length) % sections.length].id)
    }

    PageHeader { title: Tr.t("ตั้งค่า"); subtitle: Tr.t("หน้าตา ใบหน้า เสียง และความเป็นส่วนตัว · เลือกหมวดทางซ้าย") }

    RowLayout {
        Layout.fillWidth: true
        spacing: 24

        // เมนูหมวด · แถบเน้นเลื่อนตามหมวดที่เลือก (ภาพเคลื่อนไหวจุดที่ 2)
        Rectangle {
            id: nav
            objectName: "settingsNav"
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: Math.round(200 + 60 * Theme.fontScale)
            implicitHeight: navCol.implicitHeight + 16
            radius: Theme.radiusCard
            color: Theme.surface
            border.width: 1
            border.color: nav.activeFocus ? Theme.accent : Theme.line
            activeFocusOnTab: true
            Accessible.role: Accessible.PageTabList
            Accessible.name: Tr.t("หมวดการตั้งค่า")
            Keys.onUpPressed: page.step(-1)
            Keys.onDownPressed: page.step(1)

            Rectangle {
                id: marker
                x: 8; width: nav.width - 16
                height: navCol.children.length > 0 ? navCol.children[0].height : 0
                y: 8 + page.sections.findIndex(s => s.id === page.section) * (height + navCol.spacing)
                radius: Theme.radiusControl
                color: Theme.accentSoft
                Behavior on y {
                    enabled: uiSettings.animations
                    NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                }
                Rectangle {   // ขีดสีเน้นด้านซ้าย = บอกหมวดที่เลือกโดยไม่ใช้สีพื้นอย่างเดียว
                    width: 4; height: parent.height - 16; radius: 2
                    anchors.verticalCenter: parent.verticalCenter
                    x: 4
                    color: Theme.accent
                }
            }
            Column {
                id: navCol
                x: 8; y: 8; width: nav.width - 16
                spacing: 4
                Repeater {
                    model: page.sections
                    Item {
                        id: navItem
                        required property var modelData
                        objectName: "settingsNav_" + modelData.id
                        width: navCol.width
                        height: Math.max(Theme.touch, navLabel.implicitHeight + 20)
                        readonly property bool current: page.section === modelData.id
                        Accessible.role: Accessible.PageTab
                        Accessible.name: modelData.text
                        Rectangle {   // พื้นตอนชี้เมาส์ (ไม่ขยับขนาด = ไม่กระตุก)
                            anchors.fill: parent
                            radius: Theme.radiusControl
                            color: Theme.surface2
                            opacity: navMouse.containsMouse && !navItem.current ? 1 : 0
                            Behavior on opacity { enabled: uiSettings.animations; NumberAnimation { duration: 150 } }
                        }
                        Row {
                            anchors.verticalCenter: parent.verticalCenter
                            x: 16
                            spacing: 12
                            Icon {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.round(20 * Theme.fontScale); height: width
                                path: navItem.modelData.icon
                                color: navItem.current ? Theme.accentInk : Theme.inkMuted
                            }
                            AppText {
                                id: navLabel
                                anchors.verticalCenter: parent.verticalCenter
                                width: navItem.width - 64
                                text: navItem.modelData.text
                                strong: navItem.current
                                color: navItem.current ? Theme.accentInk : Theme.ink
                                oneLine: true
                            }
                        }
                        MouseArea {
                            id: navMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { nav.forceActiveFocus(); page.go(navItem.modelData.id) }
                        }
                    }
                }
            }
        }

        // เนื้อหาของหมวด · เปลี่ยนหมวด = จางเข้า + เลื่อนขึ้น 12 px (ภาพเคลื่อนไหวจุดที่ 1)
        ColumnLayout {
            id: content
            objectName: "settingsContent"
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            spacing: 16
            transform: Translate { id: shift }
            ParallelAnimation {
                id: enter
                NumberAnimation { target: content; property: "opacity"; from: 0; to: 1; duration: 200; easing.type: Easing.OutCubic }
                NumberAnimation { target: shift; property: "y"; from: 12; to: 0; duration: 200; easing.type: Easing.OutCubic }
            }

            ColumnLayout {
                objectName: "settingsSection_look"
                visible: page.section === "look"
                Layout.fillWidth: true
                spacing: 16
                Card {
                    Layout.fillWidth: true
                    Layout.preferredHeight: themeCol.implicitHeight + 40
                    radius: Theme.radiusCard
                    ColumnLayout {
                        id: themeCol
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 14
                        // ภาษา (การ์ด 0039) · ชื่อหัวข้อแสดงสองภาษาเสมอ: คนที่อ่านไทยไม่ออกก็หาเจอ · ชื่อภาษาเขียนด้วยภาษานั้นเอง
                        RowLayout {
                            objectName: "languageRow"
                            Layout.fillWidth: true
                            spacing: 16
                            AppText { text: "ภาษา · Language"; strong: true; Layout.fillWidth: true }
                            AppCheck { objectName: "langTh"; text: "ไทย"; radio: true; autoExclusive: true; checked: uiSettings.language === "th"; onClicked: uiSettings.setLanguage("th") }
                            AppCheck { objectName: "langEn"; text: "English"; radio: true; autoExclusive: true; checked: uiSettings.language === "en"; onClicked: uiSettings.setLanguage("en") }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.lineSoft }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                AppText { text: Tr.t("ธีม"); strong: true }
                                AppText { text: Tr.t("เปลี่ยนทั้งระบบทันที รวมหน้า Login"); size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                            }
                            AppCheck { text: Tr.t("สว่าง"); radio: true; autoExclusive: true; checked: uiSettings.theme === "light"; onClicked: uiSettings.setTheme("light") }
                            AppCheck { text: Tr.t("มืด"); radio: true; autoExclusive: true; checked: uiSettings.theme === "dark"; onClicked: uiSettings.setTheme("dark") }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.lineSoft }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                AppText { text: Tr.t("ขนาดตัวอักษร"); strong: true }
                                AppText { text: Tr.t("100–200% ตาม BRIEF 5.7"); size: Theme.fontSmall; color: Theme.inkMuted }
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

                // ความเร็วเมาส์ (การ์ด 0060) · จำค่าไว้ใน ui.json · เข้าระบบครั้งหน้าก็ยังเป็นค่าเดิม
                Card {
                    Layout.fillWidth: true
                    implicitHeight: mouseRow.implicitHeight + 40
                    RowLayout {
                        id: mouseRow
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 8
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            AppText { text: Tr.t("ความเร็วเมาส์"); strong: true }
                            AppText {
                                objectName: "mouseSpeedNote"
                                Layout.fillWidth: true
                                text: uiSettings.mouseLive ? Tr.t("เปลี่ยนแล้วมีผลทันที · ปิดเครื่องแล้วยังจำค่าไว้")
                                                           : Tr.t("จำค่าไว้แล้ว · มีผลเมื่อเข้าระบบครั้งหน้า")
                                size: Theme.fontSmall; color: Theme.inkMuted
                            }
                        }
                        Repeater {
                            model: [{ v: 0.3, t: "ช้า" }, { v: 0.6, t: "ปกติ" }, { v: 0.9, t: "เร็ว" }, { v: 1.0, t: "เร็วสุด" }]
                            AppButton {
                                required property var modelData
                                objectName: "mouseSpeed" + Math.round(modelData.v * 10)
                                text: Tr.t(modelData.t)
                                kind: Math.abs(uiSettings.mouseSpeed - modelData.v) < 0.01 ? "primary" : "secondary"
                                onClicked: uiSettings.setMouseSpeed(modelData.v)
                            }
                        }
                    }
                }

                // ภาพเคลื่อนไหว (การ์ด 0061) · ปิดได้สำหรับคนที่เวียนหัวหรืออยากให้เปลี่ยนทันที
                Card {
                    Layout.fillWidth: true
                    implicitHeight: motionRow.implicitHeight + 40
                    RowLayout {
                        id: motionRow
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 16
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            AppText { text: Tr.t("ภาพเคลื่อนไหว"); strong: true }
                            AppText { text: Tr.t("เปลี่ยนหมวดแบบค่อย ๆ จางเข้า · ปิด = เปลี่ยนทันที"); size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                        }
                        AppCheck { objectName: "animationsOn"; text: Tr.t("เปิด"); radio: true; autoExclusive: true; checked: uiSettings.animations; onClicked: uiSettings.setAnimations(true) }
                        AppCheck { objectName: "animationsOff"; text: Tr.t("ปิด"); radio: true; autoExclusive: true; checked: !uiSettings.animations; onClicked: uiSettings.setAnimations(false) }
                    }
                }
            }
            ColumnLayout {
                objectName: "settingsSection_face"
                visible: page.section === "face"
                Layout.fillWidth: true
                spacing: 16
                FacePanel { Layout.fillWidth: true }
                LoginFacePanel { Layout.fillWidth: true }

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
                        AppText { text: Tr.t("ล็อกเมื่อไม่ได้ใช้เครื่อง"); strong: true }
                        AppText {
                            objectName: "idleLockText"
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: uiSettings.lockMin === 0
                                  ? Tr.t("ปิดอยู่: ถ้าลืมกดออกแล้วลุกไป คนต่อไปจะเห็นงาน แชท และบัญชีเว็บที่เข้าไว้")
                                  : Tr.t("ไม่ได้แตะคีย์บอร์ดหรือเมาส์ ") + uiSettings.lockMin + Tr.t(" นาที → ล็อกทุกหน้าต่าง (ปลดด้วยรหัสผ่าน) · ")
                                    + (uiSettings.logoutMin === 0
                                       ? Tr.t("ไม่ออกจากระบบเอง แอปและงานที่เปิดไว้ยังอยู่")
                                       : Tr.t("ล็อกค้างอีก ") + uiSettings.logoutMin + Tr.t(" นาที → ออกจากระบบเอง งานที่ยังไม่บันทึกจะหาย"))
                        }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 8
                            AppText { text: Tr.t("ล็อกหลังไม่ได้ใช้"); size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                            Repeater {
                                model: uiSettings.lockChoices
                                AppButton {
                                    required property int modelData
                                    objectName: "lockMin" + modelData
                                    text: modelData === 0 ? Tr.t("ปิด") : modelData + Tr.t(" นาที")
                                    kind: uiSettings.lockMin === modelData ? "primary" : "secondary"
                                    onClicked: uiSettings.setLockMin(modelData)
                                }
                            }
                        }
                        Flow {
                            Layout.fillWidth: true
                            visible: uiSettings.lockMin !== 0
                            spacing: 8
                            AppText { text: Tr.t("ออกจากระบบหลังล็อก"); size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                            Repeater {
                                model: uiSettings.logoutChoices
                                AppButton {
                                    required property int modelData
                                    objectName: "logoutMin" + modelData
                                    text: modelData === 0 ? Tr.t("ไม่ออกเอง") : modelData + Tr.t(" นาที")
                                    kind: uiSettings.logoutMin === modelData ? "primary" : "secondary"
                                    onClicked: uiSettings.setLogoutMin(modelData)
                                }
                            }
                        }
                        // ขั้น C: กล้องช่วยดูว่าเจ้าของยังอยู่ · ต้องลงทะเบียน "ใบหน้าของฉัน" ก่อน · เปิดเอง
                        AppCheck {
                            objectName: "presenceCheck"
                            // การ์ด 0051 ทาง ก: ใช้ใบหน้าที่ลงทะเบียนตอนสมัคร (เข้าด้วยใบหน้า) ได้เลย ไม่ต้องลงทะเบียนซ้ำ ·
                            // "ใบหน้าของฉัน" แบบเดิมยังใช้ได้สำหรับบัญชีที่ไม่ได้เปิดเข้าด้วยใบหน้า
                            readonly property bool hasFace: loginFace.state === "enabled" || face.state === "enrolled"
                            enabled: hasFace || uiSettings.presence
                            text: Tr.t("ใช้กล้องช่วยดูว่าฉันยังนั่งอยู่")
                            detail: !hasFace && !uiSettings.presence
                                    ? Tr.t("ต้องเปิด \"เข้าเครื่องด้วยใบหน้า\" ด้านบนก่อน (ใช้ใบหน้าที่ลงทะเบียนตอนสมัคร)")
                                    : (loginFace.state === "enabled" ? Tr.t("ใช้ใบหน้าที่ลงทะเบียนตอนสมัคร · ") : "")
                                      + Tr.t("ไม่ได้แตะเครื่อง 10 วินาที → กล้องเปิด · ไม่เห็นหน้าคุณ ") + uiSettings.presenceLockS
                                      + Tr.t(" วินาที หรือเห็นคนอื่นแทน → ล็อก · ")
                                      + (uiSettings.presenceLogoutS === 0
                                         ? Tr.t("ไม่ออกจากระบบเอง")
                                         : Tr.t("ล็อกแล้วไม่มีใครอยู่อีก ") + uiSettings.presenceLogoutS + Tr.t(" วินาที → ออกจากระบบ"))
                                      + Tr.t(" · ไม่บันทึกภาพ · ไฟกล้องติดเฉพาะตอนกล้องเปิด")
                            checked: uiSettings.presence
                            onClicked: uiSettings.setPresence(checked)
                        }
                        Flow {
                            Layout.fillWidth: true
                            visible: uiSettings.presence
                            spacing: 8
                            AppText { text: Tr.t("ล็อกเมื่อไม่เห็นหน้า"); size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                            Repeater {
                                model: uiSettings.presenceChoices
                                AppButton {
                                    required property int modelData
                                    objectName: "presenceLock" + modelData
                                    text: modelData + Tr.t(" วินาที")
                                    kind: uiSettings.presenceLockS === modelData ? "primary" : "secondary"
                                    onClicked: uiSettings.setPresenceLockS(modelData)
                                }
                            }
                        }
                        Flow {
                            Layout.fillWidth: true
                            visible: uiSettings.presence
                            spacing: 8
                            AppText { text: Tr.t("ออกหลังล็อกถ้าไม่มีใคร"); size: Theme.fontSmall; color: Theme.inkMuted; height: 44; verticalAlignment: Text.AlignVCenter }
                            Repeater {
                                model: uiSettings.presenceLogoutChoices
                                AppButton {
                                    required property int modelData
                                    objectName: "presenceLogout" + modelData
                                    text: modelData === 0 ? Tr.t("ไม่ออกเอง") : modelData + Tr.t(" วินาที")
                                    kind: uiSettings.presenceLogoutS === modelData ? "primary" : "secondary"
                                    onClicked: uiSettings.setPresenceLogoutS(modelData)
                                }
                            }
                        }
                        // การ์ด 0055: ปลดจอล็อกเองเมื่อเห็นหน้า · ใช้ใบหน้าที่ลงทะเบียนตอนสมัคร · กล้องเปิดตลอดตอนล็อก → เปิดเอง (ค่าเริ่มต้นปิด)
                        AppCheck {
                            objectName: "faceAutoUnlockCheck"
                            enabled: loginFace.state === "enabled" || uiSettings.faceAutoUnlock
                            text: Tr.t("ปลดจอล็อกเองเมื่อเห็นหน้าฉัน")
                            detail: loginFace.state !== "enabled" && !uiSettings.faceAutoUnlock
                                    ? Tr.t("ต้องเปิด \"เข้าเครื่องด้วยใบหน้า\" ด้านบนก่อน")
                                    : Tr.t("ตอนจอล็อก กล้องเปิดตลอด (ไฟกล้องติด) · มานั่งหน้าเครื่องแล้วเข้าได้เลย · ตรวจรูปปลอม · ผิด 5 ครั้งต้องใช้รหัสผ่าน · ไม่บันทึกภาพ")
                            checked: uiSettings.faceAutoUnlock
                            onClicked: uiSettings.setFaceAutoUnlock(checked)
                        }
                        AppText {
                            objectName: "presenceStatusText"
                            visible: uiSettings.presence && presenceStatus.text !== ""
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: Tr.t("สถานะ: ") + presenceStatus.text
                        }
                    }
                }
            }
            ColumnLayout {
                objectName: "settingsSection_voice"
                visible: page.section === "voice"
                Layout.fillWidth: true
                spacing: 16
                // ระดับเสียง (2026-10-27): ปุ่มเดียวกับคำสั่งเสียง เพิ่ม/ลด/ปิดเสียง · บอกว่าเสียงออกช่องไหน
                Card {
                    objectName: "volumeCard"
                    Layout.fillWidth: true
                    implicitHeight: volCol.implicitHeight + 40
                    Timer {   // คำสั่งเสียง "เพิ่มเสียง" เปลี่ยนจากที่อื่นได้ → อ่านใหม่ระหว่างเปิดหมวดนี้
                        interval: 3000; repeat: true; triggeredOnStart: true
                        running: page.visible && page.section === "voice" && audio.available
                        onTriggered: audio.refresh()
                    }
                    ColumnLayout {
                        id: volCol
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 8
                        AppText { text: Tr.t("ระดับเสียง"); strong: true }
                        AppText {
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: !audio.available ? Tr.t("ปรับได้เมื่อใช้งานบนเครื่องจริง")
                                  : audio.error !== "" ? Tr.t(audio.error)
                                  : Tr.t("เสียงออกทาง: ") + (audio.device || Tr.t("ไม่ทราบ"))
                        }
                        RowLayout {
                            visible: audio.available
                            spacing: 12
                            AppButton {
                                objectName: "volumeDown"
                                text: "−"
                                kind: "secondary"
                                Accessible.name: Tr.t("ลดเสียง")
                                onClicked: audio.step(-1)
                            }
                            AppText {
                                objectName: "volumeText"
                                Layout.preferredWidth: Math.round(120 * Theme.fontScale)
                                horizontalAlignment: Text.AlignHCenter
                                strong: true
                                text: audio.muted ? Tr.t("ปิดเสียงอยู่") : audio.percent + "%"
                                color: audio.muted ? Theme.danger : Theme.ink
                            }
                            AppButton {
                                objectName: "volumeUp"
                                text: "+"
                                kind: "secondary"
                                Accessible.name: Tr.t("เพิ่มเสียง")
                                onClicked: audio.step(1)
                            }
                            AppButton {
                                objectName: "volumeMute"
                                text: audio.muted ? Tr.t("เปิดเสียง") : Tr.t("ปิดเสียง")
                                kind: audio.muted ? "primary" : "secondary"
                                onClicked: audio.setMuted(!audio.muted)
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
                        AppText { text: Tr.t("เสียง"); strong: true }
                        AppText {
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: voice.available
                                  ? Tr.t("อ่านออกเสียงในเครื่อง (Piper เสียงไทย tsync2) · กดอ่านครั้งแรกรอราว 7 วิ ครั้งต่อไปราว 1 วิ · ไม่ส่งเสียงออกนอกเครื่อง")
                                  : Tr.t("ยังไม่ได้ติดตั้งตัวอ่านออกเสียง (sudo ./scripts/pi/install-voice.sh --apply) หรือไม่มีตัวเล่นเสียง")
                        }
                        AppText {   // การ์ด 0039 ระยะ B: ข้อความภาษาอังกฤษอ่านด้วยเสียงอังกฤษ
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            visible: voice.available
                            text: voice.englishVoice
                                  ? Tr.t("ข้อความภาษาอังกฤษอ่านด้วยเสียงอังกฤษ (Piper ljspeech) · อ่านภาษาอังกฤษครั้งแรกรอนานขึ้นเล็กน้อย")
                                  : Tr.t("ยังไม่ได้ติดตั้งเสียงอ่านภาษาอังกฤษ · ข้อความภาษาอังกฤษจะไม่ถูกอ่านออกเสียง")
                        }
                        AppCheck {
                            objectName: "speakAnswersCheck"
                            visible: voice.available
                            text: Tr.t("อ่านคำตอบของ AI ออกเสียงเองทุกครั้ง (ปิด/เปิดได้จากปุ่มลำโพงในหน้าผู้ช่วย)")
                            detail: Tr.t("สำหรับคนที่ไม่สะดวกอ่านจอ · กดหยุดอ่านที่คำตอบได้")
                            checked: uiSettings.speakAnswers
                            onClicked: uiSettings.setSpeakAnswers(checked)
                        }
                        AppCheck {
                            objectName: "speakRemindersCheck"
                            visible: voice.available
                            text: Tr.t("อ่านเตือนนัดออกเสียงเมื่อถึงเวลา")
                            detail: Tr.t("ใช้ลำโพงของจอหรือที่ต่อกับเครื่อง")
                            checked: uiSettings.speakReminders
                            onClicked: uiSettings.setSpeakReminders(checked)
                        }
                        // การ์ด 0058: ฟังคำสั่งเสียงเฉพาะตอนหันหน้าเข้าจอ (ใช้แค่หาหน้า ไม่ต้องลงทะเบียน) · ค่าเริ่มต้นปิด
                        AppCheck {
                            objectName: "faceToSpeakCheck"
                            text: Tr.t("ฟังคำสั่งเสียงเฉพาะตอนหันหน้าเข้าจอ")
                            detail: Tr.t("กด F9 แล้วกล้องเปิดระหว่างฟัง (ไฟกล้องติด) · หันไปคุยกับคนอื่น = ไม่นับเป็นคำสั่ง · ไม่บันทึกภาพ")
                            checked: uiSettings.faceToSpeak
                            onClicked: uiSettings.setFaceToSpeak(checked)
                        }
                    }
                }
            }
            ColumnLayout {
                objectName: "settingsSection_ai"
                visible: page.section === "ai"
                Layout.fillWidth: true
                spacing: 16
                // Claude (การ์ด 0061 รอบ 2 · Pakon 2026-10-24: "ผู้ใช้จะงงตรงที่บอกราคา · ทำให้เข้าใจง่าย"):
                // รอบ 3 (Pakon: "ไม่ควรมีราคา · มีแค่ติ๊กให้ถาม Claude ก็พอ") · ตัวจำกัดค่าใช้ต่อวันยังทำงานใน backend ($1 ค่าเริ่มต้น)
                Card {
                    id: claudeCard
                    objectName: "cloudUsageCard"
                    Layout.fillWidth: true
                    implicitHeight: cloudCol.implicitHeight + 40
                    ColumnLayout {
                        id: cloudCol
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 12
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                AppText { text: Tr.t("Claude · AI ออนไลน์ที่เก่งกว่า"); strong: true }
                                AppText {
                                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                    text: Tr.t("ปกติเครื่องตอบเองด้วย AI ในเครื่อง (ฟรี · ไม่ต้องใช้เน็ต) · เรื่องที่ตอบเองไม่ได้ เช่น ข่าววันนี้ ราคาทอง หรือให้สร้างสกิลใหม่ จะถาม Claude ทางอินเทอร์เน็ตแทน")
                                }
                            }
                            Chip {
                                visible: cloudUsage.available && cloudUsage.logoutState !== "done"
                                text: !uiSettings.useClaude ? Tr.t("ปิดอยู่")
                                      : cloudUsage.usedPercent >= 100 ? Tr.t("ครบวันนี้แล้ว") : Tr.t("เปิดอยู่")
                                kind: !uiSettings.useClaude ? "neutral" : cloudUsage.usedPercent >= 100 ? "warn" : "ok"
                                dot: true
                            }
                        }
                        // ยังไม่ได้เชื่อมต่อ (การ์ด 0021): บอกตรง ๆ + วิธีเชื่อมต่อ · มี claude แล้ว = ไม่แสดง (H5)
                        AppText {
                            objectName: "cloudUsageText"
                            visible: !cloudUsage.available
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.warnInk
                            text: Tr.t("บัญชีนี้ยังไม่ได้เชื่อมต่อ Claude · ตอนนี้ใช้ได้แค่ AI ในเครื่อง")
                        }
                        AppButton {
                            id: guideButton
                            objectName: "claudeGuideButton"
                            property bool open: false
                            visible: !cloudUsage.available || cloudUsage.logoutState === "done"
                            kind: "secondary"
                            text: open ? Tr.t("ซ่อนวิธีเชื่อมต่อ") : Tr.t("วิธีเชื่อมต่อจากคอมพิวเตอร์อีกเครื่อง")
                            onClicked: {
                                if (!open)
                                    cloudUsage.refreshGuide()
                                open = !open
                            }
                        }
                        // เชื่อมต่อที่เครื่องนี้ (การ์ด 0021 หัวข้อ 10 · Pakon 2026-10-28: "ทำให้เข้าผ่านเทอร์มินัลในเครื่องได้เลย")
                        // หน้าต่างคำสั่งรัน claude auth login ให้เอง · ไม่ใช่เทอร์มินัลเปล่า (การ์ด 0004 ไม่มี shell ทั่วไป)
                        AppText {
                            visible: guideButton.visible && cloudUsage.canConnectHere
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: Tr.t("ง่ายที่สุด: กดปุ่มนี้ หน้าต่างคำสั่งจะเปิดและเข้าสู่ระบบ Claude ให้เอง · ถ้าหน้าเว็บให้รหัสมา กด Copy Code แล้วกลับไปหน้าต่างคำสั่ง กด Ctrl+Shift+V แล้วกด Enter")
                        }
                        AppButton {
                            objectName: "settingsConnectHere"
                            visible: guideButton.visible && cloudUsage.canConnectHere
                            enabled: !cloudUsage.connecting
                            iconPath: Icons.terminal
                            text: cloudUsage.connecting ? Tr.t("หน้าต่างเชื่อมต่อเปิดอยู่…") : Tr.t("เชื่อมต่อที่เครื่องนี้")
                            onClicked: cloudUsage.connectHere()
                        }
                        AppText {
                            visible: cloudUsage.connectedNow
                            Layout.fillWidth: true; strong: true; color: Theme.okInk
                            text: Tr.t("เชื่อมต่อ Claude แล้ว · ใช้ได้เลย")
                        }
                        ClaudeGuide {
                            objectName: "claudeGuide"
                            visible: guideButton.visible && guideButton.open
                            Layout.fillWidth: true
                        }
                        AppCheck {
                            objectName: "useClaudeCheck"
                            visible: cloudUsage.available && cloudUsage.logoutState !== "done"
                            text: Tr.t("ให้ถาม Claude เมื่อ AI ในเครื่องตอบไม่ได้")
                            detail: uiSettings.useClaude
                                    ? Tr.t("ส่งไปแค่คำถามกับข้อความล่าสุด (ไม่เกิน 4 ข้อความ) · ไม่ส่งไฟล์ นัด หรือใบหน้า · ดูทุกอย่างที่ส่งไปได้ที่หมวด \"ความเป็นส่วนตัว\"")
                                    : Tr.t("ปิดอยู่: ใช้แค่ AI ในเครื่อง · ไม่มีอะไรส่งออกไป")
                            checked: uiSettings.useClaude
                            onClicked: uiSettings.setUseClaude(checked)
                        }
                        // ใช้ได้วันละเท่าไหร่ (Pakon 2026-10-28: เอาตัวเลือกกลับมา แต่ไม่ใช้เงิน) · เป็นระดับ + % ที่ใช้ไปวันนี้
                        ColumnLayout {
                            objectName: "cloudLevel"
                            visible: cloudUsage.available && uiSettings.useClaude && cloudUsage.logoutState !== "done"
                            Layout.fillWidth: true
                            spacing: 6
                            AppText {
                                objectName: "cloudLevelText"
                                Layout.fillWidth: true
                                text: Tr.t("วันนี้ถาม Claude ไป ") + cloudUsage.callsToday + Tr.t(" ครั้ง · ใช้ไปแล้ว ")
                                      + cloudUsage.usedPercent + Tr.t("% ของที่ตั้งไว้")
                            }
                            Rectangle {   // แถบที่ใช้วันนี้ (ครบ = สีเตือน · มีข้อความกำกับ ไม่ใช้สีอย่างเดียว)
                                Layout.fillWidth: true
                                implicitHeight: 8
                                radius: 4
                                color: Theme.surface2
                                Rectangle {
                                    height: parent.height
                                    radius: 4
                                    width: parent.width * cloudUsage.usedPercent / 100
                                    color: cloudUsage.usedPercent >= 100 ? Theme.warn : Theme.accent
                                }
                            }
                            RowLayout {
                                spacing: 8
                                AppText { text: Tr.t("ใช้ได้วันละ"); size: Theme.fontSmall; color: Theme.inkMuted }
                                Repeater {
                                    model: cloudUsage.levels
                                    AppButton {
                                        required property var modelData
                                        objectName: "cloudLevel_" + modelData.value
                                        text: Tr.t(modelData.name)
                                        kind: cloudUsage.limit === modelData.value ? "primary" : "secondary"
                                        onClicked: cloudUsage.setLimit(modelData.value)
                                    }
                                }
                            }
                            AppText {
                                Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                text: Tr.t("ระดับมากขึ้น = ถาม Claude ได้มากขึ้นต่อวัน และใช้โควตาบัญชี Claude ของคุณมากขึ้น · ใช้ครบแล้วเครื่องจะหยุดถาม Claude จนถึงพรุ่งนี้ และตอบด้วย AI ในเครื่องแทน")
                            }
                        }
                        // ออกจาก Claude (การ์ด 0070 · Pakon 2026-10-28) · กดสองครั้ง · ออกแล้วปิด "ให้ถาม Claude" ให้ (H2)
                        Connections {
                            target: cloudUsage
                            function onGuideChanged() {
                                if (cloudUsage.logoutState === "done" && uiSettings.useClaude)
                                    uiSettings.setUseClaude(false)
                            }
                        }
                        RowLayout {
                            visible: cloudUsage.available
                            Layout.fillWidth: true
                            spacing: 12
                            AppButton {
                                id: claudeLogout
                                objectName: "claudeLogoutButton"
                                property bool confirm: false
                                visible: cloudUsage.logoutState !== "done"
                                enabled: cloudUsage.logoutState !== "busy"
                                kind: confirm ? "danger" : "ghost"
                                text: cloudUsage.logoutState === "busy" ? Tr.t("กำลังออกจาก Claude…")
                                      : confirm ? Tr.t("กดอีกครั้งเพื่อออกจาก Claude") : Tr.t("ออกจาก Claude")
                                onClicked: {
                                    if (confirm) { confirm = false; cloudUsage.logout() }
                                    else confirm = true
                                }
                            }
                            AppText {
                                objectName: "claudeLogoutText"
                                visible: cloudUsage.logoutText !== ""
                                Layout.fillWidth: true; size: Theme.fontSmall
                                color: cloudUsage.logoutState === "failed" ? Theme.warnInk : Theme.inkMuted
                                text: cloudUsage.logoutText
                            }
                        }
                    }
                }

                // Gmail แบบอ่านอย่างเดียว (การ์ด 0072 · Pakon 2026-10-28) · สรุปด้วย AI ในเครื่อง · เนื้อหาเมลไม่ไป Claude (H3)
                // ไม่มีไฟล์ OAuth client ของเครื่อง = บอกตามจริง ไม่มีปุ่ม (H5) · เลิกเชื่อมต่อต้องกดสองครั้ง
                Card {
                    id: gmailCard
                    objectName: "gmailCard"
                    Layout.fillWidth: true
                    implicitHeight: gmailCol.implicitHeight + 40
                    property bool confirmOff: false
                    ColumnLayout {
                        id: gmailCol
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                AppText { text: Tr.t("Gmail · อ่านและสรุปเมลด้วยเสียง"); strong: true }
                                AppText {
                                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                    text: Tr.t("ขอสิทธิ์อ่านอย่างเดียวจาก Google (ส่ง ลบ หรือแก้เมลไม่ได้) · พูด “สรุปเมล” “มีเมลใหม่ไหม” · สรุปด้วย AI ในเครื่อง เนื้อหาเมลไม่ส่งไป Claude")
                                }
                            }
                            Chip {
                                visible: gmailLink.available
                                text: gmailLink.connected ? Tr.t("เชื่อมต่อแล้ว") : Tr.t("ยังไม่เชื่อมต่อ")
                                kind: gmailLink.connected ? "ok" : "neutral"
                                dot: true
                            }
                        }
                        AppText {
                            objectName: "gmailMissing"
                            visible: !gmailLink.available
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.warnInk
                            text: Tr.t("เครื่องนี้ยังไม่มีไฟล์ google_credentials.json ของบัญชีนี้ · ผู้ดูแลต้องใส่ไว้ที่ ~/.local/share/aipc ก่อน")
                        }
                        RowLayout {
                            visible: gmailLink.available
                            spacing: 12
                            AppButton {
                                objectName: "gmailConnect"
                                visible: !gmailLink.connected
                                enabled: !gmailLink.busy
                                text: gmailLink.busy ? Tr.t("รอการอนุญาตจาก Google…") : Tr.t("เชื่อมต่อ Gmail")
                                onClicked: gmailLink.connect()
                            }
                            AppButton {
                                objectName: "gmailDisconnect"
                                visible: gmailLink.connected
                                kind: gmailCard.confirmOff ? "danger" : "ghost"
                                text: gmailCard.confirmOff ? Tr.t("กดอีกครั้งเพื่อเลิกเชื่อมต่อ") : Tr.t("เลิกเชื่อมต่อ Gmail")
                                onClicked: {
                                    if (gmailCard.confirmOff) { gmailCard.confirmOff = false; gmailLink.disconnect() }
                                    else gmailCard.confirmOff = true
                                }
                            }
                        }
                        AppText {
                            objectName: "gmailText"
                            visible: gmailLink.text !== ""
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: gmailLink.text
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
                        Tr.t("ใช้เบราว์เซอร์บนคอมพิวเตอร์เปิด calendar.google.com แล้วเข้าสู่ระบบบัญชี Google ของคุณ"),
                        Tr.t("กดรูปเฟือง (การตั้งค่า) มุมขวาบน → “การตั้งค่า” → ด้านซ้ายกดชื่อปฏิทินของคุณ ใต้ “การตั้งค่าสำหรับปฏิทินของฉัน”"),
                        Tr.t("เลื่อนลงไปที่ “ผสานรวมปฏิทิน” (Integrate calendar) → คัดลอก “ที่อยู่ลับในรูปแบบ iCal” (Secret address in iCal format)"),
                        Tr.t("วางลิงก์ในช่องข้างล่างแล้วกด “เชื่อมต่อ” · ถ้าเผลอส่งลิงก์ให้คนอื่น ให้กด “รีเซ็ต” ใน Google แล้วนำลิงก์ใหม่มาวาง")
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
                                AppText { text: Tr.t("ปฏิทิน Google (อ่านอย่างเดียว)"); strong: true }
                                AppText {
                                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                    text: Tr.t("นัดจาก Google จะขึ้นในคำตอบ “พรุ่งนี้มีนัดอะไร” หน้าแรก และคำถามด้วยเสียง · ใช้ได้แม้ไม่มีเน็ต (ใช้ข้อมูลที่ดึงไว้ล่าสุด) · เครื่องนี้แก้หรือลบนัดใน Google ไม่ได้")
                                }
                            }
                            Chip {
                                visible: skills.gcalConnected
                                text: Tr.t("เชื่อมต่อแล้ว ") + skills.gcalHint
                                kind: "ok"
                                dot: true
                            }
                        }
                        // วันหยุดไทย (การ์ด 0033): ปฏิทินสาธารณะของ Google · ค่าเริ่มต้นปิด · ไม่ขึ้นกับปฏิทินส่วนตัว
                        AppCheck {
                            objectName: "holidaysCheck"
                            visible: skills.holidaysAvailable
                            enabled: !skills.holidaysBusy
                            text: Tr.t("วันหยุดไทย (ปฏิทินสาธารณะของ Google)")
                            detail: skills.holidaysStatus !== "" ? skills.holidaysStatus
                                    : skills.holidaysOn ? Tr.t("เปิดอยู่") : Tr.t("ปิดอยู่: ไม่ดึงอะไร · เปิดแล้วถามได้ เช่น “วันหยุดถัดไปคือวันอะไร”")
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
                            AppText { text: Tr.t("เตือนก่อนนัด"); size: Theme.fontSmall; color: Theme.inkMuted }
                            Repeater {
                                model: uiSettings.gcalAlertChoices
                                AppButton {
                                    required property int modelData
                                    objectName: "gcalAlert" + modelData
                                    text: modelData === 0 ? Tr.t("ไม่เตือน") : modelData + Tr.t(" นาที")
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
                            text: gcalCard.guideOpen ? Tr.t("ซ่อนวิธีรับลิงก์") : Tr.t("วิธีรับลิงก์จาก Google (4 ขั้น)")
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
                            placeholder: Tr.t("วางลิงก์ที่ขึ้นต้นด้วย https://calendar.google.com/…")
                            hint: Tr.t("ลิงก์นี้เป็นความลับ ใครได้ไปจะเห็นนัดของคุณ · อย่าส่งให้ใคร")
                        }
                        RowLayout {
                            spacing: 8
                            AppButton {
                                objectName: "gcalConnect"
                                visible: !skills.gcalConnected
                                text: Tr.t("เชื่อมต่อ")
                                enabled: gcalLink.text.trim() !== "" && !skills.gcalBusy
                                onClicked: skills.gcalConnect(gcalLink.text)
                            }
                            AppButton {
                                objectName: "gcalSyncNow"
                                visible: skills.gcalConnected
                                kind: "secondary"
                                text: Tr.t("ดึงตอนนี้")
                                enabled: !skills.gcalBusy
                                onClicked: skills.gcalSyncNow()
                            }
                            AppButton {
                                objectName: "gcalDisconnect"
                                visible: skills.gcalConnected
                                kind: gcalCard.confirmOff ? "danger" : "ghost"
                                text: gcalCard.confirmOff ? Tr.t("กดอีกครั้งเพื่อเลิกเชื่อมต่อ") : Tr.t("เลิกเชื่อมต่อ")
                                enabled: !skills.gcalBusy
                                onClicked: {
                                    if (gcalCard.confirmOff) { skills.gcalDisconnect(); gcalCard.confirmOff = false }
                                    else gcalCard.confirmOff = true
                                }
                            }
                        }
                    }
                }

                // บัญชีเว็บในเครื่องนี้ (การ์ด 0031): การเข้าสู่ระบบ Gmail/YouTube… อยู่ในโปรไฟล์เบราว์เซอร์ของผู้ช่วย (โฟลเดอร์ของผู้ใช้)
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
                        AppText { text: Tr.t("บัญชีเว็บในเครื่องนี้"); strong: true }
                        AppText {
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: Tr.t("ปุ่มแอปที่ใช้บ่อยในหน้าแรกเปิดเว็บในเบราว์เซอร์ของผู้ช่วย · ใส่รหัสผ่านในหน้าเว็บของบริการเอง ระบบไม่เห็นและไม่เก็บรหัสผ่าน")
                        }
                        AppText {
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                            text: Tr.t("ใครเข้าบัญชีเครื่องนี้ของคุณได้ จะเปิดเว็บที่เข้าสู่ระบบค้างไว้ได้ด้วย · ใช้เครื่องร่วมกับคนอื่นหรือจะคืนเครื่อง ให้กดปุ่มนี้ · ")
                                  + Tr.t("ลบเฉพาะเบราว์เซอร์ของผู้ช่วย รวมบุ๊กมาร์กและรหัสที่บันทึกไว้ในนั้น · หน้าเว็บที่เปิดอยู่จะถูกปิด (ข้อความที่พิมพ์ค้างในเว็บจะหาย)")
                        }
                        AppButton {
                            objectName: "webSignOut"
                            kind: webCard.confirmOut ? "danger" : "secondary"
                            iconPath: Icons.globe   // ไม่ใช้ไอคอนออกจากระบบ: นี่คือออกจากบัญชีเว็บ ไม่ใช่ออกจากเครื่อง (BRIEF 4)
                            text: webCard.confirmOut ? Tr.t("กดอีกครั้งเพื่อออกจากบัญชีเว็บทั้งหมด") : Tr.t("ออกจากบัญชีเว็บทั้งหมด")
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
                            text: Tr.x(webCard.result)
                        }
                        // การ์ด 0031 รอบ 3: ล้างเองทุกครั้งที่ออกจากระบบ (ทุกทาง: กดออก · ไม่ใช้เครื่องนาน · กล้อง) · ค่าเริ่มต้นปิด
                        AppCheck {
                            objectName: "clearWebOnLogout"
                            Layout.fillWidth: true
                            text: Tr.t("ออกจากบัญชีเว็บทุกครั้งที่ออกจากระบบ")
                            detail: Tr.t("เหมาะกับเครื่องที่ใช้บัญชีร่วมกัน · ทุกครั้งที่เข้าเครื่องต้องเข้าสู่ระบบ Gmail หรือเว็บดูหนังใหม่ · ไม่ลบเบราว์เซอร์ธรรมดาและไฟล์ดาวน์โหลด")
                            checked: uiSettings.clearWebOnLogout
                            onClicked: uiSettings.setClearWebOnLogout(checked)
                        }
                        AppText {
                            objectName: "webClearFailed"
                            visible: uiSettings.webClearFailed
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.warnInk
                            text: Tr.t("ออกจากระบบครั้งก่อน ล้างบัญชีเว็บไม่สำเร็จ · การเข้าสู่ระบบเว็บอาจยังอยู่ · กดปุ่มออกจากบัญชีเว็บทั้งหมดด้านบน")
                        }
                    }
                }
            }
            ColumnLayout {
                objectName: "settingsSection_privacy"
                visible: page.section === "privacy"
                Layout.fillWidth: true
                spacing: 16
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
                                AppText { text: Tr.t("สิ่งที่ส่งออกนอกเครื่อง"); strong: true }
                                AppText {
                                    objectName: "outboundSummary"
                                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                    text: cloudUsage.outboundTotal === 0
                                          ? Tr.t("ยังไม่เคยส่งอะไรออกไป · แชท นัด และไฟล์อยู่ในเครื่องนี้เท่านั้น")
                                          : Tr.t("ส่งออกนอกเครื่องแล้ว ") + cloudUsage.outboundTotal + Tr.t(" ครั้ง · แสดงข้อความที่ส่งจริงตามตัวอักษร · แชทอื่น นัด และไฟล์ไม่เคยถูกส่ง")
                                }
                            }
                            AppButton {
                                objectName: "clearOutbound"
                                visible: cloudUsage.outboundTotal > 0
                                kind: "ghost"
                                text: outCard.confirmClear ? Tr.t("กดอีกครั้งเพื่อล้าง") : Tr.t("ล้างประวัติ")
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
                                        text: outRow.modelData.chars + Tr.t(" ตัวอักษร · $") + outRow.modelData.cost.toFixed(3)
                                              + (outRow.modelData.ok ? "" : Tr.t(" · ไม่สำเร็จ"))
                                        size: Theme.fontSmall; color: Theme.inkMuted
                                    }
                                    AppButton {
                                        kind: "ghost"
                                        text: outCard.openRow === outRow.index ? Tr.t("ย่อ") : Tr.t("ดูข้อความที่ส่ง")
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

                // ความจำของผู้ใช้ (การ์ด 0079): จดเฉพาะที่สั่ง "จำไว้ว่า…" · อยู่ในเครื่อง บัญชีนี้เท่านั้น · ลบหมดได้
                Card {
                    id: memCard
                    objectName: "memoryCard"
                    visible: memoryCtl.available
                    Layout.fillWidth: true
                    implicitHeight: memCol.implicitHeight + 40
                    property bool confirmClear: false
                    ColumnLayout {
                        id: memCol
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                AppText { text: Tr.t("ความจำ"); strong: true }
                                AppText {
                                    objectName: "memorySummary"
                                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                    text: memoryCtl.count === 0
                                          ? Tr.t("ยังไม่มี · พิมพ์ในแชทว่า “จำไว้ว่า …” แล้วผู้ช่วยจะจำไว้ใช้ในแชทต่อ ๆ ไป")
                                          : Tr.t("จำไว้ ") + memoryCtl.count + Tr.t(" เรื่อง · อยู่ในเครื่องนี้ บัญชีของคุณเท่านั้น · ไม่จดรหัสผ่านหรือเลขบัตร")
                                }
                            }
                            AppButton {
                                objectName: "exportMemory"
                                visible: memoryCtl.count > 0
                                kind: "secondary"
                                text: Tr.t("ส่งออก")
                                onClicked: memoryCtl.exportFile()
                            }
                            AppButton {
                                objectName: "clearMemory"
                                visible: memoryCtl.count > 0
                                kind: memCard.confirmClear ? "danger" : "ghost"
                                text: memCard.confirmClear ? Tr.t("กดอีกครั้งเพื่อลบทั้งหมด") : Tr.t("ลบทั้งหมด")
                                onClicked: {
                                    if (memCard.confirmClear) { memoryCtl.clearAll(); memCard.confirmClear = false }
                                    else memCard.confirmClear = true
                                }
                            }
                        }
                        AppField {
                            objectName: "memorySearch"
                            visible: memoryCtl.count > 0
                            Layout.fillWidth: true
                            placeholder: Tr.t("ค้นความจำ")
                            field.onTextChanged: memoryCtl.search(field.text)
                        }
                        AppText {
                            visible: memoryCtl.message !== ""
                            text: memoryCtl.message
                            Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                        }
                        Repeater {
                            model: memoryCtl.facts
                            delegate: RowLayout {
                                id: memRow
                                required property var modelData
                                objectName: "memoryRow"
                                Layout.fillWidth: true
                                spacing: 8
                                AppText { Layout.fillWidth: true; text: memRow.modelData.text }
                                AppText { text: memRow.modelData.created; size: Theme.fontCaption; color: Theme.inkFaint }
                                AppButton {
                                    kind: memRow.modelData.pinned ? "primary" : "ghost"
                                    text: memRow.modelData.pinned ? Tr.t("ปักหมุดแล้ว") : Tr.t("ปักหมุด")
                                    onClicked: memoryCtl.pin(memRow.modelData.id, !memRow.modelData.pinned)
                                }
                                AppButton {
                                    objectName: "deleteMemory"
                                    kind: "ghost"; text: Tr.t("ลบ")
                                    onClicked: memoryCtl.remove(memRow.modelData.id)
                                }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                objectName: "settingsSection_backup"
                visible: page.section === "backup"
                Layout.fillWidth: true
                spacing: 16
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
                                AppText { text: Tr.t("สำรองข้อมูลลงไดรฟ์ USB"); strong: true }
                                AppText {
                                    Layout.fillWidth: true; size: Theme.fontSmall; color: Theme.inkMuted
                                    text: Tr.t("แชท นัด สกิล ตั้งค่า และไฟล์ของฉัน · ไม่รวมใบหน้า (สมัครใหม่ได้) · ไฟล์ในไดรฟ์ไม่เข้ารหัส เก็บไดรฟ์ให้ดี")
                                }
                            }
                            AppButton { text: Tr.t("หาไดรฟ์"); kind: "secondary"; enabled: !backupCtl.busy; onClicked: backupCtl.refresh() }
                        }
                        AppText {
                            visible: backupCtl.drives.length === 0
                            text: Tr.t("ยังไม่เจอไดรฟ์ · เสียบไดรฟ์ USB แล้วกด “หาไดรฟ์”")
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
                                    text: modelData.name + (modelData.count > 0 ? Tr.t(" · ชุดล่าสุด ") + modelData.latest : Tr.t(" · ยังไม่มีชุดสำรอง"))
                                }
                                AppButton { text: Tr.t("สำรองลงไดรฟ์นี้"); enabled: !backupCtl.busy; onClicked: backupCtl.backupTo(index) }
                                AppButton {
                                    visible: modelData.count > 0
                                    enabled: !backupCtl.busy
                                    text: bkCard.confirmRestore === index ? Tr.t("กดอีกครั้งเพื่อกู้") : Tr.t("กู้จากชุดล่าสุด")
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
            }
        }
    }

    Item { Layout.fillHeight: true }
}
