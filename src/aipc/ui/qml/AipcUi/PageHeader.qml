// หัวหน้าเพจ: ปุ่มย้อนกลับ + ชื่อหน้า + คำอธิบาย (BRIEF 5.7 ข้อ 3: ปุ่มย้อนกลับทุกหน้า)
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root
    property string title: ""
    property string subtitle: ""
    default property alias actions: actionRow.data
    spacing: 12
    Layout.fillWidth: true

    AppButton {
        kind: "secondary"
        iconPath: Icons.back
        Accessible.name: Tr.t("ย้อนกลับ")
        onClicked: AppState.page = "workspace"
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        AppText { text: root.title; size: Theme.fontTitle; strong: true; Layout.fillWidth: true }
        AppText { text: root.subtitle; size: Theme.fontSmall; color: Theme.inkMuted; visible: root.subtitle !== ""; Layout.fillWidth: true }
    }
    RowLayout { id: actionRow; spacing: 8 }
}
