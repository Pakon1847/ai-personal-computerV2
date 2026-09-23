// สถานะการนำทางของหน้าจอ: ตอนนี้อยู่หน้าไหน
// เก็บเป็น singleton ที่เดียว หน้าจอทุกหน้าเปลี่ยนค่าที่นี่ แล้ว Main.qml สลับหน้าให้เอง
pragma Singleton
import QtQuick

QtObject {
    property string screen: "login"      // login | signup | shell
    property string page: "workspace"    // หน้าย่อยใน shell: workspace | files | skills | privacy | health | settings
    property bool devMode: false         // โหมดพัฒนา: เดินหน้าจอได้ครบโดยยังไม่มี backend จริง (มีแถบเตือนเสมอ)

    function go(name) { screen = name }
    function open(name) { screen = "shell"; page = name }
}
