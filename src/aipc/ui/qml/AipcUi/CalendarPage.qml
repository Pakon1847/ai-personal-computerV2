// หน้าปฏิทินแบบตารางเดือน (การ์ด 0038) · อ่านอย่างเดียว · ข้อมูลจาก skills.monthItems ตัวเดียวกับคำตอบ "…มีนัดอะไร"
// จุดสี: นัดในเครื่อง · ปฏิทิน Google · วันหยุดราชการ · วันสำคัญ (ไม่ได้หยุด) · กดวัน = รายการของวันนั้น
// การ์ด 0041 ระยะ 2: จอกว้าง = ตารางซ้าย + รายการของวันขวา · ตัวอักษรใหญ่/จอแคบ = เรียงลง ·
// ช่องในตารางกว้างเท่ากันด้วย fillWidth + preferredWidth เท่ากัน (เดิมคำนวณจากความกว้างของตารางเอง = วนผูกค่ากัน ตารางหดแคบ)
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    objectName: "calendarPage"
    spacing: 16
    property int year: 0
    property int month: 0
    // ไม่ตั้งชื่อว่า data: ชื่อนี้ Qt สงวนไว้เก็บลูกของทุกชิ้นบนจอ (ตั้งทับแล้วตารางว่าง · พบ 2026-10-15)
    property var info: ({ cells: [], title: "", note: "", todayIso: "" })
    property string selected: ""
    readonly property bool wide: width >= 980 && Theme.fontScale <= 1.25
    readonly property var weekdays: [Tr.t("จ."), Tr.t("อ."), Tr.t("พ."), Tr.t("พฤ."), Tr.t("ศ."), Tr.t("ส."), Tr.t("อา.")]
    readonly property var picked: {
        for (let i = 0; i < info.cells.length; i++)
            if (info.cells[i].iso === selected) return info.cells[i]
        return null
    }

    function reload() {
        info = skills.monthItems(year, month)
        year = info.year
        month = info.month
        if (selected === "") selected = info.todayIso
    }
    function shift(n) {
        let m = month + n, y = year
        if (m < 1) { m = 12; y -= 1 }
        if (m > 12) { m = 1; y += 1 }
        year = y; month = m
        reload()
    }
    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload()
    // นัดเปลี่ยน / ดึงปฏิทิน Google เสร็จ / เปิดวันหยุด = วาดใหม่
    Connections {
        target: skills
        function onRemindersChanged() { root.reload() }
        function onGcalChanged() { root.reload() }
    }

    PageHeader {
        title: Tr.t("ปฏิทิน")
        subtitle: Tr.t("นัดของคุณ ปฏิทิน Google และวันหยุด · จดนัดใหม่ได้ที่หน้าผู้ช่วย")
    }

    // เดือน + ปุ่มเปลี่ยนเดือน
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        AppText {
            objectName: "calendarMonthTitle"
            text: root.info.title
            size: Theme.fontTitle; strong: true
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
        AppButton { objectName: "calendarPrev"; text: Tr.t("เดือนก่อน"); kind: "secondary"; iconPath: Icons.back; onClicked: root.shift(-1) }
        AppButton { objectName: "calendarToday"; text: Tr.t("เดือนนี้"); kind: "outline"; onClicked: { root.year = 0; root.month = 0; root.selected = ""; root.reload() } }
        AppButton { objectName: "calendarNext"; text: Tr.t("เดือนถัดไป"); kind: "secondary"; onClicked: root.shift(1) }
    }

    // คำอธิบายสี
    Flow {
        Layout.fillWidth: true
        spacing: 16
        Repeater {
            model: [
                { label: Tr.t("นัดในเครื่อง"), color: Theme.accent },
                { label: Tr.t("ปฏิทิน Google"), color: Theme.ok },
                { label: Tr.t("วันหยุดราชการ"), color: Theme.danger },
                { label: Tr.t("วันสำคัญ (ไม่ได้หยุด)"), color: Theme.warn }
            ]
            delegate: Row {
                required property var modelData
                spacing: 6
                Rectangle { width: 10; height: 10; radius: 5; color: modelData.color; anchors.verticalCenter: parent.verticalCenter }
                AppText { text: modelData.label; size: Theme.fontSmall; color: Theme.inkMuted }
            }
        }
    }

    GridLayout {
        Layout.fillWidth: true
        columns: root.wide ? 2 : 1
        columnSpacing: 16
        rowSpacing: 16

        // ---------- ตารางเดือน ----------
        Card {
            Layout.fillWidth: true
            Layout.preferredWidth: 3
            Layout.alignment: Qt.AlignTop
            implicitHeight: grid.implicitHeight + 32
            GridLayout {
                id: grid
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 16
                columns: 7
                columnSpacing: 6
                rowSpacing: 6

                Repeater {
                    model: root.weekdays
                    delegate: AppText {
                        required property string modelData
                        required property int index
                        text: modelData
                        size: Theme.fontSmall; strong: true
                        color: index >= 5 ? Theme.accentInk : Theme.inkMuted   // เสาร์-อาทิตย์
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.bottomMargin: 4
                    }
                }
                Repeater {
                    model: root.info.cells
                    delegate: Rectangle {
                        id: cell
                        required property var modelData
                        objectName: "calendarCell"
                        readonly property bool chosen: modelData.iso === root.selected
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.preferredHeight: Math.max(Theme.touch + 8, dayText.implicitHeight + 26)
                        radius: Theme.radiusCard
                        color: chosen ? Theme.accentSoft : hover.hovered ? Theme.surface2 : "transparent"
                        border.width: chosen ? 1 : 0
                        border.color: Theme.accent
                        opacity: modelData.inMonth ? 1 : 0.45
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.label + (modelData.lines.length ? " · " + modelData.lines.length + Tr.t(" รายการ") : "")
                        HoverHandler { id: hover }

                        // เลขวัน · วันนี้ = วงกลมสีคราม · วันหยุด = ตัวเลขสีแดง
                        Rectangle {
                            anchors.top: parent.top; anchors.left: parent.left
                            anchors.topMargin: 6; anchors.leftMargin: 6
                            width: Math.max(28, dayText.implicitWidth + 12); height: width
                            radius: width / 2
                            color: cell.modelData.today ? Theme.accentFill : "transparent"
                            AppText {
                                id: dayText
                                anchors.centerIn: parent
                                text: cell.modelData.day
                                strong: cell.modelData.today || cell.chosen
                                oneLine: true
                                color: cell.modelData.today ? Theme.textOnAccent
                                     : cell.modelData.holiday ? Theme.danger : Theme.ink
                            }
                        }
                        Row {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.margins: 8
                            spacing: 4
                            Rectangle { visible: cell.modelData.local; width: 8; height: 8; radius: 4; color: Theme.accent }
                            Rectangle { visible: cell.modelData.google; width: 8; height: 8; radius: 4; color: Theme.ok }
                            Rectangle { visible: cell.modelData.holiday; width: 8; height: 8; radius: 4; color: Theme.danger }
                            Rectangle { visible: cell.modelData.observance; width: 8; height: 8; radius: 4; color: Theme.warn }
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.selected = cell.modelData.iso }
                    }
                }
            }
        }

        // ---------- รายการของวันที่เลือก (บรรทัดเดียวกับคำตอบ "…มีนัดอะไร") ----------
        Card {
            Layout.fillWidth: true
            Layout.preferredWidth: 2
            Layout.alignment: Qt.AlignTop
            visible: root.picked !== null
            implicitHeight: dayCol.implicitHeight + 36
            ColumnLayout {
                id: dayCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 18
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Icon { path: Icons.calendar; color: Theme.accent; width: 20; height: 20 }
                    AppText { objectName: "calendarDayTitle"; text: root.picked ? root.picked.label : ""; strong: true; size: Theme.px(18); Layout.fillWidth: true }
                }
                AppText {
                    visible: root.picked !== null && root.picked.lines.length === 0
                    text: Tr.t("ไม่มีนัดในวันนี้")
                    color: Theme.inkMuted
                    Layout.fillWidth: true
                }
                // การ์ด 0062: วันที่เลือกว่าง = แสดงนัดถัดไป 5 รายการ (ข้อมูลเดียวกับแผง "นัดถัดไป" ของหน้าผู้ช่วย)
                ColumnLayout {
                    objectName: "calendarUpcoming"
                    visible: root.picked !== null && root.picked.lines.length === 0
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    spacing: 8
                    AppText { text: Tr.t("นัดถัดไป"); strong: true; size: Theme.fontSmall; color: Theme.inkMuted }
                    AppText {
                        visible: skills.upcoming.length === 0
                        text: Tr.t("ยังไม่มีนัดล่วงหน้า · จดนัดได้ที่หน้าผู้ช่วย เช่น “เตือนส่งรายงานพรุ่งนี้บ่ายสอง”")
                        size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true
                    }
                    Repeater {
                        model: skills.upcoming.slice(0, 5)
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle { Layout.alignment: Qt.AlignTop; Layout.topMargin: 7; width: 8; height: 8; radius: 4; color: Theme.accent }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                AppText { text: modelData.what; Layout.fillWidth: true }
                                AppText { text: modelData.when; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                            }
                        }
                    }
                }
                Repeater {
                    model: root.picked ? root.picked.lines : []
                    delegate: Rectangle {
                        required property string modelData
                        Layout.fillWidth: true
                        implicitHeight: lineText.implicitHeight + 20
                        radius: Theme.radiusCard
                        color: Theme.surface2
                        Rectangle { x: 0; y: 10; width: 3; height: parent.height - 20; radius: 2; color: Theme.accent }
                        AppText {
                            id: lineText
                            objectName: "calendarDayLine"
                            anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 14; anchors.rightMargin: 10
                            text: modelData
                        }
                    }
                }
                AppText {
                    visible: root.picked !== null && root.picked.google
                    text: Tr.t("นัดจาก Google แก้หรือลบได้ในแอป Google Calendar เท่านั้น (เครื่องนี้อ่านอย่างเดียว)")
                    size: Theme.fontSmall; color: Theme.inkMuted
                    Layout.fillWidth: true
                }
            }
        }
    }

    AppText {
        objectName: "calendarNote"
        visible: text !== ""
        text: root.info.note
        size: Theme.fontSmall; color: Theme.warnInk
        Layout.fillWidth: true
    }
}
