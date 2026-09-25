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

    // A deliberately lightweight, deterministic star field. No shader, network
    // fetch or 3-D acceleration is required for the greeter to remain usable.
    Item {
        id: stars
        anchors.fill: parent
        Repeater {
            model: 56
            delegate: Rectangle {
                readonly property real xp: ((index * 73 + 11) % 101) / 101
                readonly property real yp: ((index * 43 + 17) % 97) / 97
                x: stars.width * xp
                y: stars.height * yp
                width: index % 11 === 0 ? 3 : 1.5
                height: width
                radius: width / 2
                color: index % 3 === 0 ? "#b4afff" : "#bdeeff"
                opacity: 0.25
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.9; duration: 1700 + (index % 7) * 300 }
                    NumberAnimation { to: 0.2; duration: 2100 + (index % 5) * 350 }
                }
            }
        }
    }

    RowLayout {
        anchors.centerIn: parent
        opacity: 0
        SequentialAnimation on opacity {
            running: true
            PauseAnimation { duration: 300 }
            NumberAnimation { from: 0; to: 1; duration: 1250; easing.type: Easing.OutCubic }
        }
        spacing: 64

        ColumnLayout {
            Layout.preferredWidth: 560
            spacing: 18
            Item {
                Layout.preferredWidth: 158
                Layout.preferredHeight: 158
                Rectangle {
                    id: pulseRing
                    anchors.centerIn: parent
                    width: 148
                    height: 148
                    color: "transparent"
                    border.color: "#6a9cff"
                    border.width: 2
                    radius: width / 2
                    opacity: 0
                    ParallelAnimation {
                        loops: Animation.Infinite
                        running: true
                        NumberAnimation { target: pulseRing; property: "scale"; from: 0.75; to: 1.5; duration: 2800 }
                        SequentialAnimation {
                            NumberAnimation { target: pulseRing; property: "opacity"; from: 0; to: 0.75; duration: 700 }
                            NumberAnimation { target: pulseRing; property: "opacity"; from: 0.75; to: 0; duration: 2100 }
                        }
                    }
                }
                Image {
                    anchors.fill: parent
                    source: "file:///usr/share/icons/hicolor/scalable/apps/synapse-os.svg"
                    fillMode: Image.PreserveAspectFit
                }
            }
            Text { text: "SYNAPSE OS"; color: "#f6fbff"; font.pixelSize: 54; font.bold: true; letterSpacing: 6 }
            Text { text: "COSMOS // BEAST BOX // CST"; color: "#7fdfff"; font.pixelSize: 22; letterSpacing: 4 }
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
