// หน้าสุขภาพเครื่อง · ผลตรวจจริงจาก aipc.doctor ตัวเดียวกับที่ใช้เก็บหลักฐานใน docs/benchmarks
// "ไม่รู้" = อ่านค่าไม่ได้ ไม่ได้แปลว่าผ่าน
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    spacing: 16

    PageHeader {
        title: "สุขภาพเครื่อง"
        subtitle: "ตรวจจริงทุก 10 วินาที · อ่านอย่างเดียว ไม่แก้อะไรบนเครื่อง"
        AppButton { text: "ตรวจตอนนี้"; kind: "secondary"; onClicked: system.refresh() }
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
