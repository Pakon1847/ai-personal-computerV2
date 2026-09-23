// กรอบเลื่อนของหน้าในแอป · เนื้อหายาวกว่าจอ (เช่น ตัวอักษร 200%) ต้องเลื่อนดูได้ ไม่ถูกตัดทิ้ง (BRIEF 5.7)
// ใส่หน้าเป็นลูกตัวเดียว ให้ลูกกำหนด width เอง · ผู้ใช้ตั้ง contentHeight จาก implicitHeight ของลูก
// (ใช้ childrenRect ไม่ได้ เพราะวนผูกค่ากับขนาดของ Flickable เอง)
import QtQuick
import QtQuick.Controls.Basic

Flickable {
    id: f
    clip: true
    contentWidth: width
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: f.contentHeight > f.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
}
