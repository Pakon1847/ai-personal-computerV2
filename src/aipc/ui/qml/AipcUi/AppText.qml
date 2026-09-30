// ข้อความมาตรฐาน: ฟอนต์ไทย ระยะบรรทัดตาม Theme และตัดบรรทัดตามคำ
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
    // ตัดตามคำก่อน ถ้าหาจุดตัดไม่ได้ (เช่นภาษาไทยบนวินโดวส์ที่ไม่มีพจนานุกรมตัดคำ) ค่อยตัดกลางคำ
    // ดีกว่าปล่อยให้ข้อความล้นออกนอกกล่อง · บน Pi ที่มี libthai จะตัดตามคำไทยได้ถูก
    wrapMode: oneLine ? Text.NoWrap : Text.WrapAtWordBoundaryOrAnywhere
    verticalAlignment: Text.AlignVCenter
    // ข้อความธรรมดาเสมอ: ค่าเริ่มต้นของ Text (AutoText) เดาเป็น HTML ได้ · ข้อความจาก AI / Claude / สกิลที่นำเข้า
    // ต้องไม่ถูกตีความเป็นแท็ก (แท็กรูปจะทำให้ Qt ไปดึงรูปจากเว็บ = ข้อมูลรั่ว T6) · ไม่มีหน้าไหนตั้งใจใช้ rich text
    textFormat: Text.PlainText
}
