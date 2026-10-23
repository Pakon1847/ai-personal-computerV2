// หน้าต่างเลือก Wi-Fi จากแถบบน (การ์ด 0063) · ค่าทั้งหมดมาจาก NetworkManager ผ่าน wifi (aipc.ui.wifi)
// กดชื่อ: เคยต่อแล้ว = ต่อเลย · มีรหัส = ช่องรหัส (ซ่อนตัวอักษร · ติ๊กเพื่อดู) · ไม่มีรหัส = ต่อเลย
// รหัสส่งให้ Python แล้วล้างช่องทันที · หน้าจอไม่เก็บรหัส (H1) · ต่อไม่ได้ = บอกเหตุผลตามจริง (H5)
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Popup {
    id: pop
    objectName: "wifiPopup"
    property string picked: ""      // เครือข่ายที่กำลังใส่รหัส
    width: Math.min(Theme.px(440), Overlay.overlay ? Overlay.overlay.width - 32 : Theme.px(440))  // กว้างตามตัวอักษร (200% ชื่อไม่ล้น)
    padding: 16
    background: Rectangle { radius: Theme.radiusLarge; color: Theme.surface; border.width: 1; border.color: Theme.line }
    onOpened: { picked = ""; wifi.clearMessage(); wifi.scan(false) }
    onClosed: { pass.text = ""; picked = "" }

    function choose(n) {
        if (n.active) return
        if (n.secure && !n.known) { picked = n.ssid; pass.text = ""; pass.field.forceActiveFocus(); return }
        wifi.join(n.ssid, "")
    }
    function send() {
        const pw = pass.text
        pass.text = ""                 // ไม่ค้างรหัสในช่อง
        if (wifi.join(picked, pw)) picked = ""
    }

    contentItem: ColumnLayout {
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            AppText { text: "Wi-Fi"; strong: true; Layout.fillWidth: true }
            AppButton {
                objectName: "wifiRescan"
                kind: "ghost"; iconPath: Icons.restart
                text: wifi.busy === "scan" ? Tr.t("กำลังค้นหา…") : Tr.t("ค้นหาใหม่")
                enabled: wifi.busy === ""
                onClicked: wifi.scan(true)
            }
        }
        AppText {
            objectName: "wifiMessage"
            visible: wifi.message !== "" || wifi.busy !== ""
            Layout.fillWidth: true
            size: Theme.fontSmall
            color: wifi.busy !== "" ? Theme.inkMuted : wifi.messageOk ? Theme.okInk : Theme.warnInk
            text: wifi.busy !== "" && wifi.busy !== "scan" ? Tr.t("กำลังต่อ ") + wifi.busy + "…" : wifi.message
        }
        AppText {
            visible: wifi.networks.length === 0 && wifi.busy === "" && wifi.message === ""
            text: Tr.t("ไม่เห็น Wi-Fi รอบ ๆ · กดค้นหาใหม่")
            size: Theme.fontSmall; color: Theme.inkMuted
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(list.implicitHeight, 360)
            clip: true
            ColumnLayout {
                id: list
                width: pop.availableWidth
                spacing: 2
                Repeater {
                    model: wifi.networks
                    RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 4
                        AppButton {
                            objectName: "wifiNet_" + modelData.ssid
                            Layout.fillWidth: true
                            kind: "ghost"
                            iconPath: modelData.secure ? Icons.lock : Icons.wifi
                            // สัญญาณเป็นคำ (ไม่ใช้สีหรือรูปอย่างเดียว)
                            text: modelData.ssid + " · " + (modelData.bars >= 3 ? Tr.t("สัญญาณแรง") : modelData.bars === 2 ? Tr.t("สัญญาณกลาง") : Tr.t("สัญญาณอ่อน"))
                                  + (modelData.active ? Tr.t(" · ต่ออยู่") : modelData.known ? Tr.t(" · เคยต่อ") : "")
                            enabled: wifi.busy === ""
                            onClicked: pop.choose(modelData)
                        }
                        AppButton {
                            visible: modelData.known
                            objectName: "wifiForget_" + modelData.ssid
                            kind: "ghost"; iconPath: Icons.trash; text: ""
                            Accessible.name: Tr.t("ลืมเครือข่ายนี้")
                            enabled: wifi.busy === ""
                            onClicked: wifi.forget(modelData.ssid)
                        }
                    }
                }
            }
        }
        ColumnLayout {
            visible: pop.picked !== ""
            Layout.fillWidth: true
            spacing: 6
            AppField {
                id: pass
                objectName: "wifiPassword"
                Layout.fillWidth: true
                label: Tr.t("รหัสของ ") + pop.picked
                password: !showPass.checked
                field.onAccepted: pop.send()
            }
            AppCheck { id: showPass; text: Tr.t("แสดงรหัส") }
            RowLayout {
                Layout.fillWidth: true
                AppButton { kind: "secondary"; text: Tr.t("ยกเลิก"); onClicked: { pass.text = ""; pop.picked = "" } }
                Item { Layout.fillWidth: true }
                AppButton {
                    objectName: "wifiJoin"
                    text: Tr.t("เชื่อมต่อ")
                    enabled: pass.text.length >= 8 && wifi.busy === ""
                    onClicked: pop.send()
                }
            }
        }
    }
}
