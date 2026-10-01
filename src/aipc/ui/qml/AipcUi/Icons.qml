// ไอคอนเส้น (stroke) ขนาดตาราง 24×24 เขียนเป็น SVG path ล้วน
// ใช้กับ Icon.qml · วาดเองจึงไม่ต้องพึ่งชุดไอคอนภายนอก และไม่มีเรื่องไลเซนส์
// วงกลมเขียนเป็นส่วนโค้งสองครึ่ง (a …) เพราะ PathSvg ของ Qt รับเฉพาะคำสั่ง path
pragma Singleton
import QtQuick

QtObject {
    readonly property string chat: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"
    readonly property string folder: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
    readonly property string sparkle: "M12 3l2.5 5.5L20 11l-5.5 2.5L12 19l-2.5-5.5L4 11l5.5-2.5z"
    readonly property string shield: "M12 3l8 3v6c0 4.5-3.4 8.2-8 9-4.6-.8-8-4.5-8-9V6z"
    readonly property string activity: "M3 12h4l3-8 4 16 3-8h4"
    readonly property string sliders: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M14 6a2 2 0 1 0 4 0a2 2 0 1 0-4 0M8 12a2 2 0 1 0 4 0a2 2 0 1 0-4 0M16 18a2 2 0 1 0 4 0a2 2 0 1 0-4 0"
    readonly property string eyeOff: "M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c5 0 9 4.5 10 7-.4 1-1.2 2.3-2.4 3.5M6.6 6.6C4.4 8 2.9 10.1 2 12c1 2.5 5 7 10 7 1.6 0 3.1-.5 4.4-1.2"
    readonly property string logout: "M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3"
    readonly property string camera: "M3 8a2 2 0 0 1 2-2h2l2-2h6l2 2h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM8.5 13a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0"
    readonly property string cameraOff: "M3 8a2 2 0 0 1 2-2h2l2-2h6l2 2h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM4 4l16 16"
    readonly property string mic: "M9 6a3 3 0 0 1 6 0v5a3 3 0 0 1-6 0zM5 11a7 7 0 0 0 14 0M12 18v3"
    readonly property string speaker: "M4 9h4l5-4v14l-5-4H4zM16.5 9.5a3.5 3.5 0 0 1 0 5M19 7a7 7 0 0 1 0 10"
    readonly property string speakerOff: "M4 9h4l5-4v14l-5-4H4zM17 9.5l5 5M22 9.5l-5 5"
    readonly property string send: "M4 12l16-8-6 16-2.5-6.5z"
    readonly property string clip: "M20 11.5l-8.2 8.2a5 5 0 0 1-7.1-7.1l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8"
    readonly property string back: "M15 18l-6-6 6-6"
    readonly property string plus: "M12 5v14M5 12h14"
    readonly property string search: "M4 11a7 7 0 1 0 14 0a7 7 0 1 0-14 0M20 20l-4-4"
    readonly property string cpu: "M8 6h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zM9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"
    readonly property string hdd: "M5 13h14a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2zM5 13l2-8h10l2 8M7 16.5h2"
    readonly property string thermo: "M10 14V5a2 2 0 0 1 4 0v9a4 4 0 1 1-4 0z"
    readonly property string archive: "M4 4h16a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"
    readonly property string check: "M5 12.5l4.5 4.5L19 7.5"
    readonly property string alert: "M12 4l9 16H3zM12 10v4M12 17.5v.01"
    readonly property string lock: "M7 11h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2zM8 11V7a4 4 0 0 1 8 0v4"
    readonly property string key: "M4 14a4 4 0 1 0 8 0a4 4 0 1 0-8 0M11 11l9-9M16 6l3 3"
    readonly property string userPlus: "M6 8a4 4 0 1 0 8 0a4 4 0 1 0-8 0M3 21a7 7 0 0 1 14 0M19 8v6M16 11h6"
    readonly property string power: "M12 3v9M6.3 6.3a8 8 0 1 0 11.4 0"
    readonly property string globe: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"
    readonly property string terminal: "M4 6l6 6-6 6M12 18h8"
    readonly property string file: "M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zM14 3v5h5"
    readonly property string trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"
    readonly property string download: "M12 4v11M7 10l5 5 5-5M5 20h14"
    readonly property string stop: "M8 6h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"
}
