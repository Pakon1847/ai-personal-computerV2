// ระบบดีไซน์ทั้งหมดอยู่ที่นี่ที่เดียว (บอร์ด "ระบบดีไซน์" บน canvas ใช้ชื่อเดียวกันทุกตัว)
// หน้าจอทุกหน้าอ้างแค่ชื่อ token เช่น Theme.accent ห้ามพิมพ์เลขสีตรง ๆ ในหน้าจอ
// สลับธีมด้วย Theme.dark = true/false แล้วทุกสีเปลี่ยนตามทันที เพราะ QML ผูกค่าไว้ (binding)
pragma Singleton
import QtQuick

QtObject {
    property bool dark: false
    property real fontScale: 1.0   // BRIEF 5.7: ขนาดตัวอักษร 100–200%

    readonly property string family: "IBM Plex Sans Thai"
    readonly property string mono: "IBM Plex Mono"

    // --- สี: พื้นและเส้น · ธีมมืด = โทนดำ (การ์ด 0041 · สกิล ui-ux-pro-max: Dark Mode OLED) ·
    // ตัวหนังสือทุกสีบนพื้นทุกชั้น contrast ≥ 4.5:1 (ตรวจโดย tests/test_theme_contrast.py) ---
    readonly property color bg: dark ? "#050506" : "#F6F7F9"
    readonly property color surface: dark ? "#111113" : "#FFFFFF"
    readonly property color surface2: dark ? "#1A1A1E" : "#EEF0F4"
    readonly property color line: dark ? "#26262C" : "#E3E6EC"
    readonly property color lineSoft: dark ? "#1C1C21" : "#ECEEF2"
    readonly property color lineStrong: dark ? "#3F3F48" : "#C9CDD6"
    // --- ตัวอักษร ---
    readonly property color ink: dark ? "#F2F2F4" : "#15171C"
    readonly property color inkMuted: dark ? "#A1A1AA" : "#4B5160"
    readonly property color inkFaint: dark ? "#8B8B94" : "#636978"
    readonly property color inkFill: dark ? "#F2F2F4" : "#15171C"
    readonly property color textOnInk: dark ? "#050506" : "#FFFFFF"
    // --- สีหลัก (คราม) · การ์ด 0002: teal เดิมใกล้สีเขียว "ในเครื่อง/ผ่าน" เกินไป จึงเปลี่ยนเป็นครามที่ไม่ชนสีความหมาย ---
    readonly property color accent: dark ? "#A5B4FC" : "#4338CA"
    readonly property color accentFill: accent
    readonly property color textOnAccent: dark ? "#14123A" : "#FFFFFF"
    readonly property color accentSoft: dark ? "#1C1D38" : "#ECEBFB"
    readonly property color accentInk: dark ? "#C7D2FE" : "#3730A3"
    readonly property color bubbleInk: dark ? "#E0E7FF" : "#1E1B4B"
    // --- ความหมาย: เขียว = ในเครื่อง/ผ่าน, ส้ม = ออกนอกเครื่อง/เตือน, แดง = อันตราย ---
    readonly property color ok: dark ? "#6CCB7E" : "#1F7A3A"
    readonly property color okSoft: dark ? "#12241A" : "#E4F2E8"
    readonly property color okInk: dark ? "#A7E0B2" : "#17602D"
    readonly property color warn: dark ? "#F0B45C" : "#8A5300"
    readonly property color warnFill: warn
    readonly property color textOnWarn: dark ? "#2B1A00" : "#FFFFFF"
    readonly property color warnSoft: dark ? "#2E220C" : "#FBF0DC"
    readonly property color warnInk: dark ? "#F5D39B" : "#5C3800"
    readonly property color danger: dark ? "#F28B80" : "#B42318"
    readonly property color dangerFill: danger
    readonly property color textOnDanger: dark ? "#3A0B06" : "#FFFFFF"
    readonly property color dangerSoft: dark ? "#33181A" : "#FBE7E5"
    readonly property color dangerInk: dark ? "#F6B8B0" : "#7A1810"
    // กรอบกล้องเป็นสีเข้มเสมอทั้งสองธีม เพื่อให้เห็นภาพชัด
    readonly property color camera: "#1D2027"
    readonly property color cameraText: "#F4F3EF"
    readonly property color scanFound: "#3FB950"
    readonly property color scanUnknown: "#E8A33D"
    readonly property color scanLine: "#A5B4FC"

    // --- ขนาดตัวอักษร (คูณด้วย fontScale ทั้งหมด) · ต่ำสุด 13 ---
    function px(n) { return Math.round(n * fontScale) }
    readonly property int fontCaption: px(13)
    readonly property int fontSmall: px(14)
    readonly property int fontBody: px(16)
    readonly property int fontHeading: px(20)
    readonly property int fontTitle: px(28)
    readonly property int fontDisplay: px(36)
    // BRIEF 5.7 ข้อ 4 ขอระยะบรรทัด >= 1.4 เท่าของขนาดตัวอักษร กันสระบน/ล่างถูกตัด
    // วัดแล้ว IBM Plex Sans Thai มีระยะบรรทัดของตัวเอง 1.62 เท่า (lineSpacing 26 px ที่ 16 px)
    // Qt คูณจากค่านั้น จึงใช้ 1.0 = ได้ 1.62 เท่าอยู่แล้ว · ถ้าใส่ 1.4 จะกลายเป็น 2.3 เท่าและล้นจอ
    readonly property real lineHeight: 1.0

    // --- ระยะ มุม และขนาดกดได้ ---
    readonly property int radiusControl: 8     // ช่องเล็ก เช่น checkbox · ปุ่มและช่องพิมพ์เป็นทรงแคปซูล (สูง/2)
    readonly property int radiusCard: 12
    readonly property int radiusLarge: 16
    readonly property int touch: 44        // ปุ่มและแถวที่กดได้สูงอย่างน้อย 44
    readonly property int animMs: 150      // ภาพเคลื่อนไหวสั้น เฉพาะ opacity/ตำแหน่ง (ถนอม GPU ของ Pi)
}
