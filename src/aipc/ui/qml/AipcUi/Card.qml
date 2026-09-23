// การ์ดแยกจากพื้นด้วยสีพื้นต่างระดับ ไม่ใช้เงา เพราะเงาต้องใช้ effect ที่กิน GPU ของ Pi (การ์ด 0002)
import QtQuick

Rectangle {
    property bool highlight: false
    color: Theme.surface
    radius: Theme.radiusLarge
    border.width: highlight ? 2 : 0
    border.color: highlight ? Theme.accent : Theme.line
}
