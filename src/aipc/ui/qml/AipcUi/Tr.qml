// แปลข้อความหน้าจอ (การ์ด 0039 ระยะ A) · ใช้ Tr.t("ข้อความไทย") แทนการเขียนข้อความตรง ๆ
// lang ผูกกับ uiSettings.language (Main.qml) · table = ตารางเดียวกับฝั่ง Python (aipc/i18n/en.json)
// ภาษาไทย หรือยังไม่มีคำแปล = คืนข้อความไทยเดิม · binding ที่เรียก t() อ่าน lang กับ table จึงเปลี่ยนตามทันทีที่สลับภาษา
// both(): หน้าเข้าสู่ระบบยังไม่รู้ว่าใครจะเข้า = แสดงสองภาษา (Pakon 2026-10-18)
pragma Singleton
import QtQuick

QtObject {
    property string lang: "th"
    property var table: ({})

    // ctx = คำเดียวกันแต่ความหมายต่างกัน ("ปิด" สวิตช์ = Off · "ปิด" หน้าต่าง = Close) → กุญแจ "ปิด#หน้าต่าง"
    function t(s, ctx) {
        if (lang !== "en") return s
        const v = table[ctx ? s + "#" + ctx : s]
        return v === undefined ? s : v
    }
    function both(s) {
        const v = table[s]
        return v === undefined || v === s ? s : s + " · " + v
    }
}
