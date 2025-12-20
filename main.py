import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame)
from PyQt5.QtCore import pyqtSlot, Qt, QFile, QTextStream
from PyQt5.QtGui import QColor

# --- 모듈 임포트 ---
from mqtt_worker import MqttWorker

# --- 카드 위젯 클래스들 (이전과 동일) ---
class SensorCard(QFrame):
    def __init__(self, title, unit, icon_text="📊"):
        super().__init__()
        self.setProperty("class", "sensor_card")
        layout = QVBoxLayout(self)
        self.title_label = QLabel(f"{icon_text} {title}")
        self.title_label.setProperty("class", "card_title")
        self.value_label = QLabel(f"- {unit}")
        self.value_label.setProperty("class", "sensor_value")
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        
    def update_value(self, value, unit):
        self.value_label.setText(f"{value} {unit}")

class ControlCard(QFrame):
    def __init__(self, title, btn_text, callback, is_toggle=True):
        super().__init__()
        self.setProperty("class", "control_card")
        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "card_title")
        self.btn = QPushButton(btn_text)
        self.btn.setCheckable(is_toggle)
        self.btn.setProperty("class", "control_btn")
        if is_toggle:
            self.btn.toggled.connect(callback)
        else:
            self.btn.clicked.connect(callback)
        layout.addWidget(self.title_label)
        layout.addWidget(self.btn)

# --- 메인 앱 클래스 ---
class AquaFarmApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("스마트 양식장 관리 시스템")
        self.resize(1024, 600)
        
        # === MQTT 설정 ===
        # 브로커가 이 라즈베리파이(localhost)에 있다면 'localhost'
        # 다른 곳에 있다면 해당 IP 입력
        self.mqtt_thread = MqttWorker(broker_ip="localhost") 
        self.mqtt_thread.data_received.connect(self.update_sensors)
        self.mqtt_thread.start()

        self._init_ui()
        self.load_stylesheet("stylesheet.qss")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # 헤더
        header = QLabel("🐟 Aquaculture Management System")
        header.setObjectName("HeaderLabel")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # 센서 모니터링 섹션
        sensor_layout = QHBoxLayout()
        sensor_layout.setSpacing(20)
        
        self.temp_card = SensorCard("수온", "°C", "🌡️")
        self.turbidity_card = SensorCard("탁도", "NTU", "💧")
        self.level_card = SensorCard("수위", "%", "📏")
        
        sensor_layout.addWidget(self.temp_card)
        sensor_layout.addWidget(self.turbidity_card)
        sensor_layout.addWidget(self.level_card)
        main_layout.addLayout(sensor_layout, stretch=1)

        # 제어 패널 섹션
        control_layout = QHBoxLayout()
        control_layout.setSpacing(20)

        self.motor_card = ControlCard("수류 모터", "OFF", self.on_motor_toggled, is_toggle=True)
        self.heater_card = ControlCard("히터 제어", "OFF", self.on_heater_toggled, is_toggle=True)
        self.feeder_card = ControlCard("먹이 급여", "밥 주기 🍚", self.on_feed_clicked, is_toggle=False)

        control_layout.addWidget(self.motor_card)
        control_layout.addWidget(self.heater_card)
        control_layout.addWidget(self.feeder_card)
        main_layout.addLayout(control_layout, stretch=1)

    # --- MQTT 데이터 수신 처리 ---
    @pyqtSlot(dict)
    def update_sensors(self, data):
        """RPi2 -> MQTT -> UI로 들어온 센서 데이터 표시"""
        if 'temp' in data: self.temp_card.update_value(data['temp'], "°C")
        if 'turbidity' in data: self.turbidity_card.update_value(data['turbidity'], "NTU")
        if 'level' in data: self.level_card.update_value(data['level'], "%")

    # --- 제어 명령 전송 ---
    def on_motor_toggled(self, checked):
        state = "ON" if checked else "OFF"
        self.motor_card.btn.setText(state)
        self.mqtt_thread.publish_command("water_motor", state)

    def on_heater_toggled(self, checked):
        state = "ON" if checked else "OFF"
        self.heater_card.btn.setText(state)
        self.mqtt_thread.publish_command("heater", state)

    def on_feed_clicked(self):
        self.mqtt_thread.publish_command("feeder", "ACTIVATE")

    def load_stylesheet(self, filename):
        qss_file = QFile(filename)
        if qss_file.open(QFile.ReadOnly | QFile.Text):
            self.setStyleSheet(QTextStream(qss_file).readAll())
            qss_file.close()

    def closeEvent(self, event):
        self.mqtt_thread.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AquaFarmApp()
    window.showFullScreen()
    sys.exit(app.exec_())