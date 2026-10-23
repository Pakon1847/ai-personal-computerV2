// ถามยืนยันก่อนปิด/รีสตาร์ตเครื่อง (การ์ด 0052) · ใช้ทั้งหน้า Login และในเซสชัน
// ผลจริงมาจาก power (Python · systemctl) · สั่งไม่สำเร็จ = ข้อความค้างในกล่อง (H2)
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AipcUi

Popup {
    id: dlg
    objectName: "powerDialog"
    property string action: ""   // "power_off" | "reboot"
    property string note: ""     // บรรทัดเพิ่ม (เช่น ในเซสชัน: งานในแอปอื่นที่ยังไม่บันทึกจะหาย)
    property bool twoLangs: false  // หน้า Login: ไทย · อังกฤษ คู่กัน (ยังไม่รู้ว่าใครจะเข้า)
    function ask(a) { action = a; open() }
    function tx(s) { return twoLangs ? Tr.both(s) : Tr.t(s) }
    readonly property string what: action === "reboot" ? tx("รีสตาร์ตเครื่อง") : tx("ปิดเครื่อง")
    anchors.centerIn: Overlay.overlay
    width: Math.min(460, (Overlay.overlay ? Overlay.overlay.width : 492) - 32)  // ทั้งจอ ไม่ใช่แถบซ้ายที่แคบ
    modal: true
    padding: 20
    closePolicy: power.busy ? Popup.NoAutoClose : Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { radius: Theme.radiusLarge; color: Theme.surface; border.width: 1; border.color: Theme.line }
    contentItem: ColumnLayout {
        spacing: 12
        AppText {
            text: dlg.action === "reboot" ? dlg.tx("รีสตาร์ตเครื่องเลยไหม?") : dlg.tx("ปิดเครื่องเลยไหม?")
            strong: true; Layout.fillWidth: true
        }
        AppText {
            visible: dlg.note !== ""
            text: dlg.note
            size: Theme.fontSmall; color: Theme.inkMuted; Layout.fillWidth: true
        }
        AppText {
            objectName: "powerError"
            visible: power.error !== ""
            text: power.error
            color: Theme.warnInk; size: Theme.fontSmall; Layout.fillWidth: true
        }
        AppText { visible: power.busy; text: dlg.tx("กำลังสั่ง… อย่าดึงปลั๊ก"); Layout.fillWidth: true }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            AppButton { text: dlg.tx("ยกเลิก"); kind: "secondary"; enabled: !power.busy; onClicked: dlg.close() }
            AppButton {
                objectName: "powerConfirm"
                text: dlg.what
                kind: "primary"
                iconPath: dlg.action === "reboot" ? Icons.restart : Icons.power
                enabled: !power.busy
                onClicked: power.request(dlg.action)
            }
        }
    }
}
