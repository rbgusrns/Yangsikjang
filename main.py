import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QDialog, QMessageBox)
from PyQt5.QtCore import pyqtSlot, Qt, QFile, QTextStream, QTimer
from PyQt5.QtGui import QColor

# --- 모듈 임포트 ---
# (mqtt_worker.py 파일이 같은 폴더에 있어야 합니다)
from mqtt_worker import MqttWorker

# --- 경고창 다이얼로그 클래스 (수위 경고용) ---
class WarningDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("경고")
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint) # 닫기 버튼 없애거나 커스텀 가능
        self.setObjectName("WarningDialog") # 스타일시트 적용용 ID
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignCenter)

        # 경고 메시지 라벨
        msg_label = QLabel(message)
        msg_label.setAlignment(Qt.AlignCenter)
        # 폰트나 색상을 강조하고 싶다면 setStyleSheet 직접 사용 가능
        msg_label.setStyleSheet("font-size: 24px; font-weight: bold; color: red;") 
        layout.addWidget(msg_label)

        # 확인 버튼
        ok_btn = QPushButton("확인")
        ok_btn.setFixedSize(120, 50)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
        
    def exec_(self):
        # 부모 중앙에 위치
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.center() - self.rect().center())
        return super().exec_()

# --- 카드 위젯 클래스들 (기존 유지) ---
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
        
        # 상태 플래그 (중복 경고 방지용)
        self.is_level_warning_shown = False 

        # === MQTT 설정 ===
        self.mqtt_thread = MqttWorker(broker_ip="localhost") 
        self.mqtt_thread.data_received.connect(self.update_sensors)
        self.mqtt_thread.start()

        # === 자동 급여 타이머 설정 (5분) ===
        self.feed_timer = QTimer(self)
        self.feed_timer.setInterval(5 * 60 * 1000) # 5분 (ms 단위)
        self.feed_timer.timeout.connect(self.on_feed_clicked) # 기존 급여 함수 재사용
        self.feed_timer.start()

        self._init_ui()
        self.load_stylesheet("stylesheet.qss")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # 헤더
        header = QLabel("자동 양식장 시스템")
        header.setObjectName("HeaderLabel")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # 센서 모니터링 섹션
        sensor_layout = QHBoxLayout()
        sensor_layout.setSpacing(20)
        
        self.temp_card = SensorCard("수온", "°C")
        self.turbidity_card = SensorCard("탁도", "NTU")
        self.level_card = SensorCard("수위", "%")
        
        sensor_layout.addWidget(self.temp_card)
        sensor_layout.addWidget(self.turbidity_card)
        sensor_layout.addWidget(self.level_card)
        main_layout.addLayout(sensor_layout, stretch=1)

        # 제어 패널 섹션
        control_layout = QHBoxLayout()
        control_layout.setSpacing(20)

        self.motor_card = ControlCard("수류 모터", "OFF", self.on_motor_toggled, is_toggle=True)
        self.heater_card = ControlCard("히터 제어", "OFF", self.on_heater_toggled, is_toggle=True)
        self.feeder_card = ControlCard("먹이 급여", "밥 주기", self.on_feed_clicked, is_toggle=False)

        control_layout.addWidget(self.motor_card)
        control_layout.addWidget(self.heater_card)
        control_layout.addWidget(self.feeder_card)
        main_layout.addLayout(control_layout, stretch=1)

    # --- MQTT 데이터 수신 처리 ---
    @pyqtSlot(dict)
    def update_sensors(self, data):
        """RPi2 -> MQTT -> UI로 들어온 센서 데이터 표시 및 자동 제어"""
        
        # 1. UI 업데이트
        if 'temp' in data: self.temp_card.update_value(data['temp'], "°C")
        if 'turbidity' in data: self.turbidity_card.update_value(data['turbidity'], "NTU")
        if 'level' in data: self.level_card.update_value(data['level'], "%")

        # 2. 자동 제어 로직 실행
        self.check_auto_control(data)

    def check_auto_control(self, data):
        """센서 값에 따른 자동 제어 로직"""
        
        # (1) 탁도 제어: 30 NTU 이상이면 수류 모터 ON, 아니면 OFF
        if 'turbidity' in data:
            turbidity_val = float(data['turbidity'])
            is_motor_on = self.motor_card.btn.isChecked()

            if turbidity_val >= 30:
                if not is_motor_on:
                    self.motor_card.btn.setChecked(True) # 토글 시그널 발생 -> MQTT 전송됨
            else:
                # 30 미만으로 떨어지면 자동으로 끌 것인가? (요구사항에 따라 주석 처리 가능)
                if is_motor_on:
                    self.motor_card.btn.setChecked(False)

        # (2) 수온 제어: 20도 이하이면 히터 ON, 아니면 OFF
        if 'temp' in data:
            temp_val = float(data['temp'])
            is_heater_on = self.heater_card.btn.isChecked()

            if temp_val <= 20:
                if not is_heater_on:
                    self.heater_card.btn.setChecked(True)
            else:
                # 20도 초과 시 자동으로 끌 것인가? (안전상 끄는 로직 추가함)
                if is_heater_on:
                    self.heater_card.btn.setChecked(False)

        # (3) 수위 경고: 수위가 30% 미만(임의 설정)이면 경고창
        if 'level' in data:
            level_val = float(data['level'])
            LOW_LEVEL_THRESHOLD = 30.0 # 경고 기준 (30% 미만)

            if level_val < LOW_LEVEL_THRESHOLD:
                if not self.is_level_warning_shown:
                    self.is_level_warning_shown = True
                    # 경고창 띄우기
                    dialog = WarningDialog("수위가 낮습니다!\n물을 보충해주세요.", self)
                    dialog.exec_()
            else:
                # 수위가 정상으로 돌아오면 플래그 초기화 (다시 떨어지면 또 경고 가능하도록)
                self.is_level_warning_shown = False

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
        # 버튼 텍스트 잠시 변경 (피드백 효과)
        self.feeder_card.btn.setText("동작 중...")
        self.feeder_card.btn.setEnabled(False)
        
        self.mqtt_thread.publish_command("feeder", "ACTIVATE")
        
        # 1초 뒤 버튼 원래대로 복구
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