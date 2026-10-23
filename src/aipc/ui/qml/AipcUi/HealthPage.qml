// หน้าสุขภาพเครื่อง · ผลตรวจจริงจาก aipc.doctor ตัวเดียวกับที่ใช้เก็บหลักฐานใน docs/benchmarks
// "ไม่รู้" = อ่านค่าไม่ได้ ไม่ได้แปลว่าผ่าน
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    spacing: 16

    PageHeader {
        title: Tr.t("สุขภาพเครื่อง")
        subtitle: Tr.t("เช็กให้ทุก 10 วินาที · ดูอย่างเดียว ไม่แก้อะไรในเครื่อง")
        AppButton { text: Tr.t("ตรวจตอนนี้"); kind: "secondary"; onClicked: system.refresh() }
        AppButton {
            objectName: "readyButton"
            text: system.readyBusy ? Tr.t("กำลังตรวจ…") : Tr.t("ตรวจความพร้อมก่อนสาธิต")
            kind: "primary"; iconPath: Icons.check
            enabled: !system.readyBusy
            onClicked: system.checkReady()
        }
    }

    // สรุปค่าหลักของเครื่อง (การ์ด 0041 ระยะ 2) · แถบบนรวมค่าเหล่านี้เป็นป้าย "เครื่องปกติ" แล้ว →
    // หน้านี้ต้องเห็นตัวเลขจริงครบในแวบเดียว · ค่าที่อ่านไม่ได้แสดง "—" (H5) · มีปัญหา = กรอบสีตามระดับ
    GridLayout {
        objectName: "healthSummary"
        Layout.fillWidth: true
        columns: Theme.fontScale > 1.25 ? 2 : 4
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
            model: [
                { label: Tr.t("อุณหภูมิ"), value: system.tempText, icon: Icons.thermo,
                  level: system.alerts.some(a => a.id === "temp") ? "danger" : "" },
                { label: Tr.t("พื้นที่ว่าง"), value: system.storageText, icon: Icons.hdd,
                  level: system.alerts.some(a => a.id === "storage") ? "warn" : "" },
                { label: Tr.t("เครือข่าย"), icon: Icons.globe,
                  value: ({ on: Tr.t("ต่ออยู่"), off: Tr.t("ออฟไลน์"), unknown: Tr.t("ไม่รู้") })[system.networkState],
                  level: system.networkState === "off" ? "warn" : "" },
                { label: Tr.t("โมเดลภาษา"), value: chat.statusText.replace(Tr.t("โมเดล: "), ""), icon: Icons.cpu,
                  level: chat.ready || chat.status === "off" ? "" : "warn" }
            ]
            Card {
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                implicitHeight: tileCol.implicitHeight + 32
                border.width: modelData.level !== "" ? 1 : 0
                border.color: modelData.level === "danger" ? Theme.danger : Theme.warn
                ColumnLayout {
                    id: tileCol
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 6
                    RowLayout {
                        spacing: 8
                        Rectangle {
                            implicitWidth: 32; implicitHeight: 32; radius: 10
                            color: Theme.accentSoft
                            Icon { anchors.centerIn: parent; path: modelData.icon; color: Theme.accentInk; width: 18; height: 18 }
                        }
                        AppText { text: modelData.label; size: Theme.fontSmall; color: Theme.inkMuted; oneLine: true }
                    }
                    AppText {
                        Layout.fillWidth: true
                        text: modelData.value
                        size: Theme.fontHeading; strong: true
                        color: modelData.level === "danger" ? Theme.danger : modelData.level === "warn" ? Theme.warnInk : Theme.ink
                        maximumLineCount: 2; elide: Text.ElideRight
                    }
                }
            }
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
                        Chip { text: Tr.t(rc.modelData.status); kind: rc.modelData.level }
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

    // อุปกรณ์ที่ต่ออยู่ (การ์ด 0051) · ตรวจตอนเปิดหน้าและตอนกด "ตรวจใหม่" · ตรวจไม่ได้ ≠ ไม่มี
    Card {
        objectName: "devicesCard"
        Layout.fillWidth: true
        implicitHeight: devCol.implicitHeight + 32
        radius: Theme.radiusCard
        Component.onCompleted: system.scanDevices()
        ColumnLayout {
            id: devCol
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
            anchors.margins: 16
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                AppText { text: Tr.t("อุปกรณ์ที่ต่ออยู่"); strong: true; Layout.fillWidth: true }
                AppButton {
                    objectName: "scanDevices"
                    text: system.devicesBusy ? Tr.t("กำลังตรวจ…") : Tr.t("ตรวจใหม่")
                    kind: "secondary"
                    enabled: !system.devicesBusy
                    onClicked: system.scanDevices()
                }
            }
            // การ์ด 0062: การ์ดเล็กต่ออุปกรณ์ · ไอคอน + ชื่อ + สิ่งที่เจอ · สถานะอยู่ขวา (จุดสี + คำ · ไม่ใช้สีอย่างเดียว)
            GridLayout {
                Layout.fillWidth: true
                columns: Theme.fontScale > 1.4 ? 2 : 3
                columnSpacing: 10
                rowSpacing: 10
                Repeater {
                    model: system.devices
                    delegate: Rectangle {
                        id: dv
                        required property var modelData
                        objectName: "deviceTile"
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        implicitHeight: Math.max(Theme.touch + 20, tileRow.implicitHeight + 24)
                        radius: Theme.radiusCard
                        color: Theme.surface2
                        RowLayout {
                            id: tileRow
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12
                            Rectangle {
                                Layout.alignment: Qt.AlignTop
                                implicitWidth: Math.round(36 * Theme.fontScale); implicitHeight: implicitWidth
                                radius: Theme.radiusControl
                                color: dv.modelData.state === "ok" ? Theme.accentSoft : Theme.surface
                                Icon {
                                    anchors.centerIn: parent
                                    width: Math.round(20 * Theme.fontScale); height: width
                                    path: ({ display: Icons.monitor, usb: Icons.hdd, camera: Icons.camera, audio_out: Icons.speaker,
                                             audio_in: Icons.mic, bluetooth: Icons.bluetooth })[dv.modelData.kind] || Icons.activity
                                    color: dv.modelData.state === "ok" ? Theme.accentInk : Theme.inkMuted
                                }
                            }
                            ColumnLayout {
                                id: tileCol
                                Layout.fillWidth: true
                                spacing: 2
                                AppText { text: Tr.t(dv.modelData.label); strong: true; Layout.fillWidth: true }
                                AppText {
                                    // " · ใช้อยู่" มาจาก Python เป็นไทย · แปลที่นี่ให้สลับภาษาแล้วเปลี่ยนตาม (การ์ด 0039)
                                    visible: text !== ""
                                    text: dv.modelData.items.map(x => x.replace(" · ใช้อยู่", Tr.t(" · ใช้อยู่"))).join(" · ")
                                    size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true
                                    maximumLineCount: 2; elide: Text.ElideRight
                                }
                            }
                            Chip {
                                Layout.alignment: Qt.AlignTop
                                text: ({ ok: Tr.t("เจอ"), none: Tr.t("ไม่มี"), unknown: Tr.t("ตรวจไม่ได้") })[dv.modelData.state]
                                kind: dv.modelData.state === "ok" ? "ok" : "neutral"
                                dot: true
                            }
                        }
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
                        Chip { Layout.alignment: Qt.AlignTop; text: Tr.t(parent.parent.parent.modelData.status); kind: parent.parent.parent.modelData.level }
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
