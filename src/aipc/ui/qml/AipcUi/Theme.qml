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

    // --- สี: พื้นและเส้น ---
    readonly property color bg: dark ? "#121417" : "#F4F3EF"
    readonly property color surface: dark ? "#1B1E23" : "#FFFFFF"
    readonly property color surface2: dark ? "#22262C" : "#F9F8F5"
    readonly property color line: dark ? "#32373E" : "#E2E0D9"
    readonly property color lineSoft: dark ? "#292D33" : "#EEECE6"
    readonly property color lineStrong: dark ? "#4A5059" : "#C9C6BD"
    // --- ตัวอักษร ---
    readonly property color ink: dark ? "#ECEAE4" : "#1B1E23"
    readonly property color inkMuted: dark ? "#B9BDC4" : "#4F5561"
    readonly property color inkFaint: dark ? "#9CA2AA" : "#646A75"
    readonly property color inkFill: dark ? "#ECEAE4" : "#1B1E23"
    readonly property color textOnInk: dark ? "#121417" : "#FFFFFF"
    // --- สีหลัก (teal) ---
    readonly property color accent: dark ? "#7FD1CB" : "#0E6B66"
    readonly property color accentFill: accent
    readonly property color textOnAccent: dark ? "#0B2E2C" : "#FFFFFF"
    readonly property color accentSoft: dark ? "#173634" : "#E3F0EE"
    readonly property color accentInk: dark ? "#A8E3DE" : "#0B524E"
    readonly property color bubbleInk: dark ? "#DDF3F0" : "#0B2E2C"
    // --- ความหมาย: เขียว = ในเครื่อง/ผ่าน, ส้ม = ออกนอกเครื่อง/เตือน, แดง = อันตราย ---
    readonly property color ok: dark ? "#5BBF60" : "#2F7D32"
    readonly property color okSoft: dark ? "#1B2F1C" : "#E6F2E6"
    readonly property color okInk: dark ? "#A3DCA6" : "#1F5E22"
    readonly property color warn: dark ? "#F0B45C" : "#8A5300"
    readonly property color warnFill: warn
    readonly property color textOnWarn: dark ? "#2B1A00" : "#FFFFFF"
    readonly property color warnSoft: dark ? "#36290F" : "#FBF0DC"
    readonly property color warnInk: dark ? "#F5D39B" : "#5C3800"
    readonly property color danger: dark ? "#F28B80" : "#B42318"
    readonly property color dangerFill: danger
    readonly property color textOnDanger: dark ? "#3A0B06" : "#FFFFFF"
    readonly property color dangerSoft: dark ? "#3B1D1A" : "#FBE7E5"
    readonly property color dangerInk: dark ? "#F6B8B0" : "#7A1810"
    // กรอบกล้องเป็นสีเข้มเสมอทั้งสองธีม เพื่อให้เห็นภาพชัด
    readonly property color camera: "#2A2E34"
    readonly property color cameraText: "#F4F3EF"
    readonly property color scanFound: "#3FB950"
    readonly property color scanUnknown: "#E8A33D"

    // --- ขนาดตัวอักษร (คูณด้วย fontScale ทั้งหมด) · ต่ำสุด 13 ---
    function px(n) { return Math.round(n * fontScale) }
    readonly property int fontCaption: px(13)
    readonly property int fontSmall: px(14)
    readonly property int fontBody: px(16)
    readonly property int fontHeading: px(20)
    readonly property int fontTitle: px(28)
    readonly property int fontDisplay: px(36)
    readonly property real lineHeight: 1.4   // กันสระบน/ล่างของภาษาไทยถูกตัด (BRIEF 5.7 ข้อ 4)

    // --- ระยะ มุม และขนาดกดได้ ---
    readonly property int radiusControl: 8
    readonly property int radiusCard: 12
    readonly property int radiusLarge: 16
    readonly property int touch: 44        // ปุ่มและแถวที่กดได้สูงอย่างน้อย 44
    readonly property int animMs: 150      // ภาพเคลื่อนไหวสั้น เฉพาะ opacity/ตำแหน่ง (ถนอม GPU ของ Pi)
}
