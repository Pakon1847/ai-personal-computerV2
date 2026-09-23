// การ์ดพื้นขาวขอบบาง · ใช้เส้นขอบแทนเงา เพราะเงาต้องใช้ effect ที่กิน GPU ของ Pi
import QtQuick

Rectangle {
    property bool highlight: false
    color: Theme.surface
    radius: Theme.radiusLarge
    border.width: highlight ? 2 : 1
    border.color: highlight ? Theme.accent : Theme.line
}
