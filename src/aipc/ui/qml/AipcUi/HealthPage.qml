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
        columns: 3
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: system.checks
            Card {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 112
                radius: Theme.radiusCard
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        AppText { text: parent.parent.parent.modelData.title; strong: true; oneLine: true; Layout.fillWidth: true; elide: Text.ElideRight }
                        Chip { text: parent.parent.parent.modelData.status; kind: parent.parent.parent.modelData.level }
                    }
                    AppText {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: parent.parent.modelData.detail
                        size: Theme.fontSmall
                        color: Theme.inkMuted
                        elide: Text.ElideRight
                        maximumLineCount: 2
                        verticalAlignment: Text.AlignTop
                    }
                }
            }
        }
    }
    Item { Layout.fillHeight: true }
}
