import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QDialog)
from PyQt5.QtCore import pyqtSlot, Qt, QFile, QTextStream, QTimer
from PyQt5.QtGui import QColor

# --- 모듈 임포트 ---
from mqtt_worker import MqttWorker

# --- 경고창 클래스 ---
class WarningDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("경고")
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setObjectName("WarningDialog")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        msg_label = QLabel(message)
        msg_label.setAlignment(Qt.AlignCenter)
        msg_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #e74c3c;")
        layout.addWidget(msg_label)

        ok_btn = QPushButton("확인")
        ok_btn.setFixedSize(120, 40)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn, alignment=Qt.AlignCenter)
        
    def exec_(self):
        if self.parent():
            self.move(self.parent().geometry().center() - self.rect().center())
        return super().exec_()

# --- 카드 위젯들 (기존 동일) ---
class SensorCard(QFrame):
    def __init__(self, title, unit, icon_text=""):
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
        
        # === 상태 플래그 ===
        self.is_level_warning_shown = False 
        
        # [중요] 누가 켰는지 추적하는 변수 (True면 자동제어가 킨 것, False면 사용자가 킨 것)
        self.is_motor_auto_on = False
        self.is_heater_auto_on = False

        # === MQTT 설정 ===
        self.mqtt_thread = MqttWorker(broker_ip="localhost") 
        self.mqtt_thread.data_received.connect(self.update_sensors)
        self.mqtt_thread.start()

        # === 자동 급여 타이머 (5분) ===
        self.feed_timer = QTimer(self)
        self.feed_timer.setInterval(5 * 60 * 1000)
        self.feed_timer.timeout.connect(self.on_feed_clicked)
        self.feed_timer.start()

        self._init_ui()
        self.load_stylesheet("stylesheet.qss")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        header = QLabel("자동 양식장 시스템")
        header.setObjectName("HeaderLabel")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # 센서 섹션
        sensor_layout = QHBoxLayout()
        sensor_layout.setSpacing(20)
        self.temp_card = SensorCard("수온", "°C")
        self.turbidity_card = SensorCard("탁도", "NTU")
        self.level_card = SensorCard("수위", "%")
        sensor_layout.addWidget(self.temp_card)
        sensor_layout.addWidget(self.turbidity_card)
        sensor_layout.addWidget(self.level_card)
        main_layout.addLayout(sensor_layout, stretch=1)

        # 제어 섹션
        control_layout = QHBoxLayout()
        control_layout.setSpacing(20)
        self.motor_card = ControlCard("수류 모터", "OFF", self.on_motor_toggled, is_toggle=True)
        self.heater_card = ControlCard("히터 제어", "OFF", self.on_heater_toggled, is_toggle=True)
        self.feeder_card = ControlCard("먹이 급여", "밥 주기", self.on_feed_clicked, is_toggle=False)
        control_layout.addWidget(self.motor_card)
        control_layout.addWidget(self.heater_card)
        control_layout.addWidget(self.feeder_card)
        main_layout.addLayout(control_layout, stretch=1)

    # --- MQTT 데이터 처리 및 자동 제어 ---
    @pyqtSlot(dict)
    def update_sensors(self, data):
        if 'temp' in data: self.temp_card.update_value(data['temp'], "°C")
        if 'turbidity' in data: self.turbidity_card.update_value(data['turbidity'], "NTU")
        if 'level' in data: self.level_card.update_value(data['level'], "%")

        self.check_auto_control(data)

    def check_auto_control(self, data):
        """센서 값에 따른 자동 제어 로직 (사용자 수동 제어 존중)"""
        
        # 1. 탁도 제어 (수류 모터)
        if 'turbidity' in data:
            turbidity = float(data['turbidity'])
            is_motor_on = self.motor_card.btn.isChecked()

            if turbidity >= 30:
                # 탁도가 높으면 무조건 켬 (안전 우선)
                if not is_motor_on:
                    self.set_device_state(self.motor_card.btn, True, "water_motor")
                    self.is_motor_auto_on = True # "시스템이 켰음" 표시
            else:
                # 탁도가 낮아짐 (안전함)
                # [중요] "시스템이 켰을 때만" 시스템이 끈다. 
                # 사용자가 수동으로 켰다면(is_motor_auto_on == False) 끄지 않음.
                if is_motor_on and self.is_motor_auto_on:
                    self.set_device_state(self.motor_card.btn, False, "water_motor")
                    self.is_motor_auto_on = False

        # 2. 수온 제어 (히터)
        if 'temp' in data:
            temp = float(data['temp'])
            is_heater_on = self.heater_card.btn.isChecked()

            if temp <= 20:
                # 추우면 무조건 켬
                if not is_heater_on:
                    self.set_device_state(self.heater_card.btn, True, "heater")
                    self.is_heater_auto_on = True
            else:
                # 따뜻해짐
                # [중요] "시스템이 켰을 때만" 끈다.
                if is_heater_on and self.is_heater_auto_on:
                    self.set_device_state(self.heater_card.btn, False, "heater")
                    self.is_heater_auto_on = False

        # 3. 수위 경고
        if 'level' in data:
            level = float(data['level'])
            if level < 30.0:
                if not self.is_level_warning_shown:
                    self.is_level_warning_shown = True
                    WarningDialog("수위가 낮습니다!\n물을 보충해주세요.", self).exec_()
            else:
                self.is_level_warning_shown = False

    # --- 장치 제어 헬퍼 함수 ---
    def set_device_state(self, btn, turn_on, mqtt_topic):
        """
        코드로 버튼 상태를 강제로 변경할 때 사용.
        blockSignals를 사용하여 on_clicked 이벤트(사용자 액션)와 구분함.
        """
        btn.blockSignals(True) # 시그널 차단 (사용자 클릭으로 오인되지 않게)
        btn.setChecked(turn_on)
        state_text = "ON" if turn_on else "OFF"
        btn.setText(state_text)
        self.mqtt_thread.publish_command(mqtt_topic, state_text)
        btn.blockSignals(False) # 차단 해제

    # --- 사용자 입력 이벤트 핸들러 ---
    def on_motor_toggled(self, checked):
        # 사용자가 버튼을 클릭했을 때만 실행됨 (set_device_state에서는 실행 안 됨)
        # [중요] 사용자가 개입했으므로 "자동 제어 플래그"를 해제하여 시스템이 끄지 못하게 함
        self.is_motor_auto_on = False 
        
        state = "ON" if checked else "OFF"
        self.motor_card.btn.setText(state)
        self.mqtt_thread.publish_command("water_motor", state)

    def on_heater_toggled(self, checked):
        # 사용자가 개입했으므로 자동 제어 플래그 해제
        self.is_heater_auto_on = False
        
        state = "ON" if checked else "OFF"
        self.heater_card.btn.setText(state)
        self.mqtt_thread.publish_command("heater", state)

    def on_feed_clicked(self):
        self.feeder_card.btn.setText("동작 중...")
        self.feeder_card.btn.setEnabled(False)
        self.mqtt_thread.publish_command("feeder", "ACTIVATE")
        QTimer.singleShot(1000, lambda: self.reset_feeder_btn())

    def reset_feeder_btn(self):
        self.feeder_card.btn.setText("밥 주기")
        self.feeder_card.btn.setEnabled(True)

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