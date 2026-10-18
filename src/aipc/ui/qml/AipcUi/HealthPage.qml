// หน้าสุขภาพเครื่อง · ผลตรวจจริงจาก aipc.doctor ตัวเดียวกับที่ใช้เก็บหลักฐานใน docs/benchmarks
// "ไม่รู้" = อ่านค่าไม่ได้ ไม่ได้แปลว่าผ่าน
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    spacing: 16

    PageHeader {
        title: Tr.t("สุขภาพเครื่อง")
        subtitle: Tr.t("ตรวจจริงทุก 10 วินาที · อ่านอย่างเดียว ไม่แก้อะไรบนเครื่อง")
        AppButton { text: Tr.t("ตรวจตอนนี้"); kind: "secondary"; onClicked: system.refresh() }
        AppButton {
            objectName: "readyButton"
            text: system.readyBusy ? Tr.t("กำลังตรวจ…") : Tr.t("ตรวจความพร้อมก่อนสาธิต")
            kind: "primary"; iconPath: Icons.check
            enabled: !system.readyBusy
            onClicked: system.checkReady()
        }
    }

    // ผลตรวจความพร้อมก่อนสาธิต: เรื่องที่เจอจริง (ไฟเลี้ยง เน็ต นาฬิกา ความร้อน) พร้อมวิธีแก้
    Card {
        objectName: "readyCard"
        visible: system.readyChecks.length > 0
        Layout.fillWidth: true
        implicitHeight: readyCol.implicitHeight + 32
        radius: Theme.radiusCard
        ColumnLayout {
            id: readyCol
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
            anchors.margins: 16
            spacing: 8
            AppText { objectName: "readySummary"; text: system.readySummary; strong: true; Layout.fillWidth: true }
            Repeater {
                model: system.readyChecks
                delegate: ColumnLayout {
                    id: rc
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 2
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Chip { text: rc.modelData.status; kind: rc.modelData.level }
                        AppText { text: rc.modelData.title; strong: true }
                        AppText { text: rc.modelData.detail; size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true }
                    }
                    AppText {
                        visible: rc.modelData.fix !== "" && rc.modelData.level !== "ok"
                        text: Tr.t("วิธีแก้: ") + rc.modelData.fix
                        size: Theme.fontSmall; color: Theme.warnInk; Layout.fillWidth: true
                    }
                }
            }
        }
    }

    GridLayout {
        Layout.fillWidth: true
        // ตัวอักษรใหญ่ → 2 คอลัมน์ การ์ดกว้างขึ้น ข้อความไม่ต้องตัด (การ์ด 0002 ข้อ 6)
        columns: Theme.fontScale > 1.4 ? 2 : 3
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: system.checks
            Card {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1   // คอลัมน์กว้างเท่ากันไม่ว่าข้อความยาวแค่ไหน
                Layout.fillHeight: true
                // สูงตามข้อความจริง · ข้อความรายละเอียดแสดงครบ ไม่ตัดท้ายด้วย … (เดิมตัดที่ 2 บรรทัด)
                implicitHeight: Math.max(112, cardCol.implicitHeight + 28)
                radius: Theme.radiusCard
                ColumnLayout {
                    id: cardCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        AppText { text: parent.parent.parent.modelData.title; strong: true; Layout.fillWidth: true }
                        Chip { Layout.alignment: Qt.AlignTop; text: parent.parent.parent.modelData.status; kind: parent.parent.parent.modelData.level }
                    }
                    AppText {
                        Layout.fillWidth: true
                        text: parent.parent.modelData.detail
                        size: Theme.fontSmall
                        color: Theme.inkMuted
                    }
                }
            }
        }
    }
    Item { Layout.fillHeight: true }
}
