// แถบเตือน "โหมดพัฒนา" · กฎของโปรเจกต์: ห้ามแสดงผลจำลองให้ดูเหมือนทำงานสำเร็จ
// ในโหมดพัฒนาหน้าจอเดินต่อได้ครบโดยยังไม่มี backend จริง จึงต้องบอกผู้ใช้ตลอดเวลา
import QtQuick
import QtQuick.Layouts

Rectangle {
    visible: AppState.devMode
    implicitHeight: visible ? 28 : 0
    color: Theme.warnFill
    RowLayout {
        anchors.centerIn: parent
        spacing: 8
        Icon { path: Icons.alert; color: Theme.textOnWarn; Layout.preferredWidth: 16; Layout.preferredHeight: 16 }
        AppText {
            text: "โหมดพัฒนา — ยังไม่มีการยืนยันตัวตน การสร้างบัญชี หรือระบบใบหน้าจริง"
            size: Theme.fontSmall
            strong: true
            color: Theme.textOnWarn
            oneLine: true
        }
    }
}
