import json
import paho.mqtt.client as mqtt
from PyQt5.QtCore import QThread, pyqtSignal

class MqttWorker(QThread):
    # UI로 보낼 시그널 (딕셔너리 형태)
    data_received = pyqtSignal(dict)

    def __init__(self, broker_ip="localhost", port=1883):
        super().__init__()
        self.broker_ip = broker_ip
        self.port = port
        self.client = mqtt.Client()
        
        # 콜백 함수 연결
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # 토픽 정의
        self.TOPIC_SENSORS = "farm/sensors"  # 수신: 센서값
        self.TOPIC_CONTROL = "farm/control"  # 송신: 제어 명령

    def run(self):
        try:
            print(f"MQTT 브로커({self.broker_ip}) 연결 시도...")
            self.client.connect(self.broker_ip, self.port, 60)
            self.client.loop_forever()  # 스레드 내에서 무한 루프
        except Exception as e:
            print(f"MQTT 연결 실패: {e}")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("MQTT 브로커 연결 성공!")
            # 센서 데이터 구독
            client.subscribe(self.TOPIC_SENSORS)
        else:
            print(f"연결 실패 코드: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            # UI 스레드로 데이터 전송
            self.data_received.emit(data)
        except Exception as e:
            print(f"메시지 처리 오류: {e}")

    def publish_command(self, device, state):
        """제어 명령 전송 (UI -> RPi2)"""
        payload = json.dumps({"device": device, "state": state})
        self.client.publish(self.TOPIC_CONTROL, payload)
        print(f"명령 전송: {payload}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()