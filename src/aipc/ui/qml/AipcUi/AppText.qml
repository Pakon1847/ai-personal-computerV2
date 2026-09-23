// ข้อความมาตรฐาน: ฟอนต์ไทย ระยะบรรทัด 1.4 และตัดบรรทัดตามคำ
// บน Linux Qt ใช้ libthai หาจุดตัดคำไทย ต้องติดตั้ง libthai ไม่งั้นบรรทัดยาวจะตัดกลางคำ (BRIEF 5.7 ข้อ 4)
// oneLine = ป้ายบรรทัดเดียว (ปุ่ม ป้ายสถานะ) ใช้ระยะบรรทัดปกติ ไม่งั้นตัวอักษรจะลอยขึ้นบน
import QtQuick

Text {
    property int size: Theme.fontBody
    property bool strong: false
    property bool oneLine: false
    color: Theme.ink
    font.family: Theme.family
    font.pixelSize: size
    font.weight: strong ? Font.DemiBold : Font.Normal
    lineHeight: oneLine ? 1.0 : Theme.lineHeight
    lineHeightMode: Text.ProportionalHeight
    wrapMode: oneLine ? Text.NoWrap : Text.WordWrap
    verticalAlignment: Text.AlignVCenter
}
