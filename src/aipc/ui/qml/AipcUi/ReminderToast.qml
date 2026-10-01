// การเตือนเมื่อถึงเวลานัด (การ์ด 0001) · มาจาก signal skills.reminderDue ใน Python
// ค้างไว้จนกว่าผู้ใช้กด "รับทราบ" — การเตือนที่หายไปเองคือการเตือนที่พลาดได้ (H2)
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: toast
    property var queue: []
    readonly property var current: queue.length > 0 ? queue[0] : null
    visible: current !== null
    width: 380
    height: col.implicitHeight + 32
    radius: Theme.radiusLarge
    color: Theme.surface
    border.width: 2
    border.color: Theme.accent

    function show(r) { queue = queue.concat([r]) }

    Connections {
        target: skills
        function onReminderDue(r) {
            toast.show(r)
            // อ่านเตือนออกเสียง (การ์ด 0019) · เปิดเองในหน้าตั้งค่า · ไม่ขัดคำตอบที่กำลังอ่านอยู่
            if (uiSettings.speakReminders && voice.available && voice.speakingKey === -1)
                voice.speak(-3, "ถึงเวลาแล้ว " + r.what + " " + r.when)
        }
    }

    ColumnLayout {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 16
        spacing: 8
        RowLayout {
            spacing: 8
            Icon { path: Icons.alert; color: Theme.accentInk }
            AppText { text: "ถึงเวลาแล้ว"; strong: true; color: Theme.accentInk; oneLine: true }
            Item { Layout.fillWidth: true }
            AppText { visible: toast.queue.length > 1; text: "อีก " + (toast.queue.length - 1) + " รายการ"; size: Theme.fontCaption; color: Theme.inkMuted; oneLine: true }
        }
        AppText { text: toast.current ? toast.current.what : ""; size: Theme.fontHeading; strong: true; Layout.fillWidth: true }
        AppText { text: toast.current ? toast.current.when : ""; color: Theme.inkMuted; oneLine: true }
        AppButton { text: "รับทราบ"; onClicked: toast.queue = toast.queue.slice(1) }
    }
}
