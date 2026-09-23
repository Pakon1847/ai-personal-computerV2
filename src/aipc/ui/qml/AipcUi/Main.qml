// หน้าต่างหลัก · สลับหน้า login / signup / shell ตาม AppState.screen
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import AipcUi

ApplicationWindow {
    id: win
    width: 1280
    height: 720
    minimumWidth: 1280   // ขนาดจอเล็กสุดที่ออกแบบไว้
    minimumHeight: 720
    visible: true
    visibility: startFullscreen ? Window.FullScreen : Window.Windowed
    title: "AI PC"
    color: Theme.bg
    font.family: Theme.family

    // ผูกธีมกับค่าที่ผู้ใช้ตั้ง (อยู่ใน Python) · เปลี่ยนในหน้าตั้งค่าแล้วทั้งจอเปลี่ยนทันที
    Binding { target: Theme; property: "dark"; value: uiSettings.theme === "dark" }
    Binding { target: Theme; property: "fontScale"; value: uiSettings.fontScale }

    Component.onCompleted: {
        AppState.devMode = devMode
        AppState.page = startPage
        AppState.screen = startScreen
    }

    // ทางออกของหน้าต่างพัฒนา · หน้าต่างเต็มจอที่ออกไม่ได้ = ขังผู้ใช้ไว้ในเครื่อง
    // ในเซสชันจริง (การ์ด 0004) ปิดไว้: หน้าจอนี้คือทั้งเซสชัน ปิดแล้วเหลือจอว่าง · ทางออกคือปุ่ม "ออก"
    readonly property bool quitKeyEnabled: !session.active
    Shortcut {
        enabled: win.quitKeyEnabled
        sequence: "Ctrl+Alt+Q"
        context: Qt.ApplicationShortcut
        onActivated: Qt.quit()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        DevBanner { Layout.fillWidth: true }
        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: AppState.screen === "signup" ? signupPage
                           : AppState.screen === "shell" ? shellPage : loginPage
        }
    }

    Component { id: loginPage; LoginScreen {} }
    Component { id: signupPage; SignupFlow {} }
    Component { id: shellPage; ShellScreen {} }
}
