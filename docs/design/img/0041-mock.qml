// ภาพตัวอย่าง (mockup) การ์ด 0041 · ไม่ใช่โค้ดของแอป · ค่าทุกอย่างเป็นตัวอย่าง
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import AipcUi

Rectangle {
    id: root
    width: 1280; height: 720
    color: pal.bg
    property string variant: "home"

    QtObject {
        id: pal
        readonly property color bg: "#050506"
        readonly property color surface: "#111113"
        readonly property color surface2: "#1A1A1E"
        readonly property color line: "#26262C"
        readonly property color ink: "#F2F2F4"
        readonly property color inkMuted: "#A1A1AA"
        readonly property color inkFaint: "#8B8B94"
        readonly property color accent: "#A5B4FC"
        readonly property color accentSoft: "#1C1D38"
        readonly property color textOnAccent: "#14123A"
        readonly property color ok: "#6CCB7E"
        readonly property color okSoft: "#12241A"
        readonly property color warn: "#F0B45C"
        readonly property color warnSoft: "#2E220C"
    }
    component T: Text { color: pal.ink; font.family: "IBM Plex Sans Thai"; font.pixelSize: 16 }
    component Pill: Rectangle {
        property alias text: lbl.text
        property string icon: ""
        property color fg: pal.inkMuted
        property color bgc: pal.surface
        height: 32; radius: 16; color: bgc
        width: row.implicitWidth + 24
        RowLayout { id: row; anchors.centerIn: parent; spacing: 6
            Icon { visible: icon !== ""; path: icon; color: fg; Layout.preferredWidth: 16; Layout.preferredHeight: 16 }
            T { id: lbl; color: fg; font.pixelSize: 14 }
        }
    }
    component Nav: Rectangle {
        property string icon; property string label; property bool active: false
        width: 60; height: 60; radius: 16
        color: active ? pal.accentSoft : "transparent"
        Column { anchors.centerIn: parent; spacing: 4
            Icon { anchors.horizontalCenter: parent.horizontalCenter; path: icon; color: active ? pal.accent : pal.inkMuted; width: 22; height: 22 }
            T { anchors.horizontalCenter: parent.horizontalCenter; text: label; font.pixelSize: 13; color: active ? pal.ink : pal.inkFaint }
        }
    }
    component AppTile: Rectangle {
        property string mono; property string glyph: ""; property string label; property string note: ""
        Layout.fillWidth: true; Layout.preferredHeight: 96; radius: 16; color: pal.surface2
        border.width: hot ? 1 : 0; border.color: pal.accent
        property bool hot: false
        Column { anchors.centerIn: parent; spacing: 6
            Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 44; height: 44; radius: 12; color: pal.accentSoft
                T { visible: glyph === ""; anchors.centerIn: parent; text: mono; color: pal.accent; font.pixelSize: 18; font.weight: Font.DemiBold }
                Icon { visible: glyph !== ""; anchors.centerIn: parent; path: glyph; color: pal.accent; width: 22; height: 22 } }
            T { anchors.horizontalCenter: parent.horizontalCenter; text: label; font.pixelSize: 14; color: pal.inkMuted }
        }
    }

    // ---------- แถบซ้าย ----------
    Rectangle {
        id: side; width: 84; height: parent.height; color: pal.bg
        Column { anchors.horizontalCenter: parent.horizontalCenter; y: 16; spacing: 10
            Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 44; height: 44; radius: 14; color: pal.accent
                T { anchors.centerIn: parent; text: "AI"; color: pal.textOnAccent; font.weight: Font.Bold } }
            Item { width: 1; height: 8 }
            Nav { icon: Icons.chat; label: "ผู้ช่วย"; active: root.variant === "home" }
            Nav { icon: Icons.calendar; label: "ปฏิทิน" }
            Nav { icon: Icons.folder; label: "ไฟล์" }
            Nav { icon: Icons.sparkle; label: "Skill"; active: root.variant === "skills" }
            Nav { icon: Icons.activity; label: "เครื่อง" }
            Nav { icon: Icons.sliders; label: "ตั้งค่า" }
        }
        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 16
            width: 44; height: 44; radius: 22; color: pal.surface2
            T { anchors.centerIn: parent; text: "P"; font.weight: Font.DemiBold } }
    }

    // ---------- แถบสถานะ: ไมค์/กล้อง (H3 แสดงเต็มเสมอ) + ส่งออก + "เครื่องปกติ" รวมที่เหลือ ----------
    RowLayout {
        id: top
        x: side.width + 20; y: 14; width: parent.width - side.width - 40; spacing: 8
        T { text: "20:45"; font.pixelSize: 20; font.weight: Font.DemiBold }
        T { text: "อังคาร 20 ต.ค."; color: pal.inkMuted; font.pixelSize: 15 }
        Item { Layout.fillWidth: true }
        Pill { icon: Icons.mic; text: "ไมค์ปิด" }
        Pill { icon: Icons.cameraOff; text: "กล้องไม่ได้ใช้" }
        Pill { icon: Icons.shield; text: "ส่งออกวันนี้ 0 ครั้ง"; fg: pal.ok; bgc: pal.okSoft }
        Pill { icon: Icons.check; text: "เครื่องปกติ"; fg: pal.inkMuted }
    }

    // ---------- หน้าแรก ----------
    Item {
        visible: root.variant === "home"
        x: side.width + 20; y: 64; width: parent.width - side.width - 40; height: parent.height - 64

        Column {
            id: hero; anchors.horizontalCenter: parent.horizontalCenter; y: 18; spacing: 6; width: 760
            T { anchors.horizontalCenter: parent.horizontalCenter; text: "สวัสดีตอนค่ำ, Pakon"; font.pixelSize: 34; font.weight: Font.DemiBold }
            T { anchors.horizontalCenter: parent.horizontalCenter; text: "วันนี้ให้ช่วยอะไรดี"; color: pal.inkMuted; font.pixelSize: 17 }
            Item { width: 1; height: 10 }
            Rectangle {
                width: parent.width; height: 56; radius: 28; color: pal.surface; border.width: 1; border.color: pal.line
                T { anchors.verticalCenter: parent.verticalCenter; x: 24; text: "พิมพ์คำถาม หรือสั่ง เช่น “เปิดยูทูบ” “เตือนประชุมพรุ่งนี้บ่ายสอง”"; color: pal.inkFaint }
                Rectangle { anchors.verticalCenter: parent.verticalCenter; anchors.right: parent.right; anchors.rightMargin: 60
                    width: 44; height: 44; radius: 22; color: pal.surface2
                    Icon { anchors.centerIn: parent; path: Icons.mic; color: pal.ink; width: 20; height: 20 } }
                Rectangle { anchors.verticalCenter: parent.verticalCenter; anchors.right: parent.right; anchors.rightMargin: 8
                    width: 44; height: 44; radius: 22; color: pal.accent
                    Icon { anchors.centerIn: parent; path: Icons.send; color: pal.textOnAccent; width: 20; height: 20 } }
            }
            Row { anchors.horizontalCenter: parent.horizontalCenter; spacing: 8; topPadding: 4
                Rectangle { width: 40; height: 24; radius: 6; color: pal.surface2; border.width: 1; border.color: pal.line
                    T { anchors.centerIn: parent; text: "F9"; font.pixelSize: 13; font.weight: Font.DemiBold } }
                T { text: "กดแล้วพูดได้ทุกหน้า · ไทยหรืออังกฤษก็ได้"; color: pal.inkFaint; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
            }
        }

        // แผงแบบ bento: วันนี้ (ใหญ่) · เปิดเว็บ (ไทล์) · ลองถาม
        RowLayout {
            anchors.top: hero.bottom; anchors.topMargin: 24
            anchors.horizontalCenter: parent.horizontalCenter
            width: 1080; spacing: 16; height: 360
            Rectangle {
                Layout.preferredWidth: 300; Layout.fillHeight: true; radius: 20; color: pal.surface
                Column { x: 20; y: 18; width: parent.width - 40; spacing: 12
                    RowLayout { width: parent.width
                        Icon { path: Icons.calendar; color: pal.accent; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                        T { text: "วันนี้"; font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        T { text: "ดูทั้งหมด ›"; color: pal.accent; font.pixelSize: 14 } }
                    Repeater { model: [["21:00", "ส่งรายงานบทที่ 4", "เตือนแล้ว 1 ครั้ง"], ["พรุ่งนี้ 09:30", "พบอาจารย์ที่ปรึกษา", "ห้อง 302"], ["พรุ่งนี้ 14:00", "ซ้อมนำเสนอ", ""]]
                        delegate: Rectangle { width: parent.width; height: 64; radius: 12; color: pal.surface2
                            Rectangle { x: 0; y: 12; width: 3; height: 40; radius: 2; color: index === 0 ? pal.accent : pal.line }
                            Column { x: 14; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                                T { text: modelData[0] + "  " + modelData[1]; font.pixelSize: 15; font.weight: Font.Medium }
                                T { visible: modelData[2] !== ""; text: modelData[2]; font.pixelSize: 13; color: pal.inkFaint } } } }
                    Rectangle { width: parent.width; height: 44; radius: 22; color: "transparent"; border.width: 1; border.color: pal.line
                        Row { anchors.centerIn: parent; spacing: 6
                            Icon { path: Icons.plus; color: pal.ink; width: 18; height: 18 }
                            T { text: "เพิ่มนัด/เตือน"; font.pixelSize: 15 } } }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; radius: 20; color: pal.surface
                Column { x: 20; y: 18; width: parent.width - 40; spacing: 12
                    RowLayout { width: parent.width
                        Icon { path: Icons.globe; color: pal.accent; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                        T { text: "เปิดเว็บและแอป"; font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        T { text: "แตะ = เปิด · หรือพูด “เปิด…”"; color: pal.inkFaint; font.pixelSize: 13 } }
                    GridLayout { width: parent.width; columns: 4; columnSpacing: 10; rowSpacing: 10
                        AppTile { glyph: Icons.play; label: "YouTube"; hot: true }
                        AppTile { glyph: Icons.mail; label: "Gmail" }
                        AppTile { mono: "31"; label: "ปฏิทิน Google" }
                        AppTile { glyph: Icons.folder; label: "Drive" }
                        AppTile { mono: "N"; label: "Netflix" }
                        AppTile { glyph: Icons.speaker; label: "Spotify" }
                        AppTile { mono: "ข่าว"; label: "Thai PBS" }
                        AppTile { glyph: Icons.plus; label: "ดูทั้งหมด" }
                    }
                }
            }
            Rectangle {
                Layout.preferredWidth: 250; Layout.fillHeight: true; radius: 20; color: pal.surface
                Column { x: 20; y: 18; width: parent.width - 40; spacing: 10
                    RowLayout { width: parent.width
                        Icon { path: Icons.sparkle; color: pal.accent; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                        T { text: "ลองถาม"; font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true } }
                    Repeater { model: ["ตอนนี้กี่โมง", "สรุปข้อความนี้ให้หน่อย", "ร่างอีเมลลาป่วย", "ทำไมเครื่องช้า"]
                        delegate: Rectangle { width: parent.width; height: 52; radius: 12; color: pal.surface2
                            T { anchors.verticalCenter: parent.verticalCenter; x: 14; width: parent.width - 28; text: "“" + modelData + "”"; font.pixelSize: 15; elide: Text.ElideRight } } }
                    T { width: parent.width; wrapMode: Text.Wrap; text: "ทำในเครื่องนี้ทั้งหมด"; color: pal.ok; font.pixelSize: 13 }
                }
            }
        }
    }

    // ---------- หน้า Skill: ตารางไทล์ อ่านง่าย รายละเอียดเมื่อแตะ ----------
    Item {
        visible: root.variant === "skills"
        x: side.width + 20; y: 64; width: parent.width - side.width - 40; height: parent.height - 64
        Column { x: 20; y: 10; width: parent.width - 40; spacing: 16
            RowLayout { width: parent.width
                Column { Layout.fillWidth: true; spacing: 2
                    T { text: "Skill"; font.pixelSize: 30; font.weight: Font.DemiBold }
                    T { text: "สิ่งที่ผู้ช่วยทำได้ · แตะเพื่อดูวิธีใช้และสิทธิ์"; color: pal.inkMuted } }
                Row { spacing: 8
                    Pill { text: "ทั้งหมด 6"; fg: pal.textOnAccent; bgc: pal.accent }
                    Pill { text: "ใช้ได้แล้ว 3" }
                    Pill { text: "ต้องเปิดโมเดล 3" } } }
            GridLayout { width: parent.width; columns: 3; columnSpacing: 14; rowSpacing: 14
                Repeater {
                    model: [[Icons.calendar, "นัดหมายและเตือนความจำ", "“เตือนส่งงานพรุ่งนี้บ่ายสอง” “พรุ่งนี้มีนัดอะไร”", 1],
                            [Icons.terminal, "สั่งงานเครื่อง", "“เปิดยูทูบ” “เพิ่มเสียง” “ปิดเสียง”", 1],
                            [Icons.activity, "ถามเครื่องว่าเป็นอะไร", "“ทำไมเครื่องช้า” “เน็ตหลุดไหม”", 1],
                            [Icons.mail, "ร่างจดหมาย/อีเมล", "ต้องเปิดโมเดลภาษาในเครื่องก่อน", 0],
                            [Icons.file, "สรุปข้อความเป็นข้อ", "ต้องเปิดโมเดลภาษาในเครื่องก่อน", 0],
                            [Icons.globe, "แปลไทย ↔ อังกฤษ", "ต้องเปิดโมเดลภาษาในเครื่องก่อน", 0]]
                    delegate: Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 150; radius: 18; color: pal.surface
                        border.width: index === 0 ? 1 : 0; border.color: pal.accent
                        Column { x: 16; y: 16; width: parent.width - 32; spacing: 8
                            RowLayout { width: parent.width
                                Rectangle { width: 40; height: 40; radius: 12; color: modelData[3] ? pal.accentSoft : pal.surface2
                                    Icon { anchors.centerIn: parent; path: modelData[0]; color: modelData[3] ? pal.accent : pal.inkFaint; width: 20; height: 20 } }
                                Item { Layout.fillWidth: true }
                                Rectangle { width: 10; height: 10; radius: 5; color: modelData[3] ? pal.ok : pal.inkFaint } }
                            T { text: modelData[1]; font.pixelSize: 17; font.weight: Font.DemiBold; width: parent.width; elide: Text.ElideRight }
                            T { text: modelData[2]; font.pixelSize: 14; color: modelData[3] ? pal.inkMuted : pal.inkFaint; width: parent.width; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight } } } }
            }
        }
    }
}
