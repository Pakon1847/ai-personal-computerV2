// หน้าปฏิทินแบบตารางเดือน (การ์ด 0038) · อ่านอย่างเดียว · ข้อมูลจาก skills.monthItems ตัวเดียวกับคำตอบ "…มีนัดอะไร"
// จุดสี: นัดในเครื่อง · ปฏิทิน Google · วันหยุดราชการ · วันสำคัญ (ไม่ได้หยุด) · กดวัน = รายการของวันนั้นด้านล่าง
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
        subtitle: Tr.t("นัดในเครื่อง · ปฏิทิน Google · วันหยุดไทย · อ่านอย่างเดียว (จดนัดได้ที่หน้าผู้ช่วย เช่น “เตือนส่งรายงานพรุ่งนี้บ่ายสอง”)")
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        AppButton { objectName: "calendarPrev"; text: Tr.t("เดือนก่อน"); kind: "secondary"; onClicked: root.shift(-1) }
        AppText {
            objectName: "calendarMonthTitle"
            text: root.info.title
            size: Theme.fontHeading; strong: true
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
        }
        AppButton { objectName: "calendarToday"; text: Tr.t("เดือนนี้"); kind: "secondary"; onClicked: { root.year = 0; root.month = 0; root.selected = ""; root.reload() } }
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
        id: grid
        Layout.fillWidth: true
        columns: 7
        columnSpacing: 6
        rowSpacing: 6
        readonly property real cellWidth: (width - columnSpacing * 6) / 7

        Repeater {
            model: root.weekdays
            delegate: AppText {
                required property string modelData
                text: modelData
                size: Theme.fontSmall; color: Theme.inkMuted; strong: true
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: grid.cellWidth
            }
        }
        Repeater {
            model: root.info.cells
            delegate: Rectangle {
                id: cell
                required property var modelData
                objectName: "calendarCell"
                Layout.preferredWidth: grid.cellWidth
                Layout.preferredHeight: Math.max(Theme.touch + 12, dayText.implicitHeight + 26)
                radius: Theme.radiusControl
                color: modelData.iso === root.selected ? Theme.accentSoft : modelData.inMonth ? Theme.surface : Theme.bg
                border.width: modelData.today ? 2 : 1
                border.color: modelData.today ? Theme.accent : Theme.line
                Accessible.role: Accessible.Button
                Accessible.name: modelData.label + (modelData.lines.length ? " · " + modelData.lines.length + Tr.t(" รายการ") : "")

                AppText {
                    id: dayText
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.margins: 6
                    text: cell.modelData.day
                    strong: cell.modelData.today
                    color: cell.modelData.inMonth ? Theme.ink : Theme.inkFaint
                }
                Row {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: 6
                    spacing: 4
                    Rectangle { visible: cell.modelData.local; width: 8; height: 8; radius: 4; color: Theme.accent }
                    Rectangle { visible: cell.modelData.google; width: 8; height: 8; radius: 4; color: Theme.ok }
                    Rectangle { visible: cell.modelData.holiday; width: 8; height: 8; radius: 4; color: Theme.danger }
                    Rectangle { visible: cell.modelData.observance; width: 8; height: 8; radius: 4; color: Theme.warn }
                }
                MouseArea { anchors.fill: parent; onClicked: root.selected = cell.modelData.iso }
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

    // รายการของวันที่เลือก (บรรทัดเดียวกับคำตอบ "…มีนัดอะไร")
    Card {
        Layout.fillWidth: true
        visible: root.picked !== null
        implicitHeight: dayCol.implicitHeight + 32
        ColumnLayout {
            id: dayCol
            anchors.fill: parent
            anchors.margins: 16
            spacing: 6
            AppText { objectName: "calendarDayTitle"; text: root.picked ? root.picked.label : ""; strong: true; Layout.fillWidth: true }
            AppText {
                visible: root.picked !== null && root.picked.lines.length === 0
                text: Tr.t("ไม่มีนัดในวันนี้")
                color: Theme.inkMuted
            }
            Repeater {
                model: root.picked ? root.picked.lines : []
                delegate: AppText {
                    required property string modelData
                    objectName: "calendarDayLine"
                    text: modelData
                    Layout.fillWidth: true
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
