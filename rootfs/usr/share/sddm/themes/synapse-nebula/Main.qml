import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    width: 1920
    height: 1080
    color: "#030611"

    Image {
        anchors.fill: parent
        source: "file:///usr/share/wallpapers/SynapseOS/contents/images/3840x2160.svg"
        fillMode: Image.PreserveAspectCrop
    }

    Rectangle {
        anchors.fill: parent
        color: "#2a061018"
    }

    RowLayout {
        anchors.centerIn: parent
        spacing: 64

        ColumnLayout {
            Layout.preferredWidth: 560
            spacing: 18
            Image {
                source: "file:///usr/share/icons/hicolor/scalable/apps/synapse-os.svg"
                Layout.preferredWidth: 150
                Layout.preferredHeight: 150
                fillMode: Image.PreserveAspectFit
            }
            Text { text: "SYNAPSE OS"; color: "#f6fbff"; font.pixelSize: 54; font.bold: true; letterSpacing: 6 }
            Text { text: "NEBULA // CST"; color: "#7fdfff"; font.pixelSize: 22; letterSpacing: 4 }
            Text { text: "Welcome home."; color: "#b7c9e7"; font.pixelSize: 20 }
        }

        Rectangle {
            Layout.preferredWidth: 520
            Layout.preferredHeight: 430
            radius: 24
            color: "#d90b1224"
            border.color: "#4d6fa9"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 38
                spacing: 18
                Text { text: "Sign in"; color: "white"; font.pixelSize: 30; font.bold: true }

                ComboBox {
                    id: userBox
                    Layout.fillWidth: true
                    model: userModel
                    textRole: "name"
                }

                TextField {
                    id: password
                    Layout.fillWidth: true
                    placeholderText: "Password"
                    echoMode: TextInput.Password
                    focus: true
                    onAccepted: loginButton.clicked()
                }

                Button {
                    id: loginButton
                    Layout.fillWidth: true
                    text: "Enter Synapse"
                    onClicked: sddm.login(userBox.currentText, password.text, sessionBox.currentIndex)
                }

                ComboBox {
                    id: sessionBox
                    Layout.fillWidth: true
                    model: sessionModel
                    textRole: "name"
                }

                RowLayout {
                    Layout.fillWidth: true
                    Button { text: "Sleep"; onClicked: sddm.suspend() }
                    Button { text: "Restart"; onClicked: sddm.reboot() }
                    Button { text: "Power"; onClicked: sddm.powerOff() }
                }

                Text {
                    Layout.fillWidth: true
                    text: "Cosmic outside. Familiar inside."
                    color: "#8ca3c8"
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: 15
                }
            }
        }
    }
}
