import time
import json
import smbus            # I2C 통신용 (PCF8591)
import RPi.GPIO as GPIO # GPIO 제어용
import paho.mqtt.client as mqtt

# ==========================================
# 1. 설정 및 상수 정의
# ==========================================

# [네트워크 설정] RPi 1(UI)의 IP 주소를 입력하세요.
BROKER_IP = "192.168.0.202" 
PORT = 1883

# [MQTT 토픽]
TOPIC_SENSORS = "farm/sensors"  # 보내는 곳
TOPIC_CONTROL = "farm/control"  # 받는 곳

# [GPIO 핀 설정 (BCM 모드 기준)]
PIN_MOTOR = 17   # 수류 모터
PIN_FEEDER = 22  # 밥 모터
PIN_HEATER = 27  # 히터

# [센서 설정]
# PCF8591 (ADC) 설정
I2C_ADDR = 0x48
bus = smbus.SMBus(1) # RPi 2, 3, 4는 보통 버스 1번 사용

# DS18B20 (온도) 설정 - 제공해주신 파일 경로 반영
TEMP_SENSOR_PATH = "/sys/bus/w1/devices/28-73be00876586/temperature"

# ==========================================
# 2. 하드웨어 제어 함수들 (C언어 로직 변환)
# ==========================================

def setup_gpio():
    """GPIO 핀 초기화"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # 핀들을 출력 모드로 설정하고 초기 상태는 OFF(Low)로 둠
    GPIO.setup(PIN_MOTOR, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PIN_FEEDER, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PIN_HEATER, GPIO.OUT, initial=GPIO.LOW)

def read_temp_ds18b20():
    """temp.c 파일의 로직을 파이썬으로 구현"""
    try:
        with open(TEMP_SENSOR_PATH, 'r') as f:
            data = f.read()
            if data:
                # 파일 내용(문자열)을 숫자로 변환 후 1000으로 나눔
                temp_c = int(data) / 1000.0
                return round(temp_c, 1)
    except Exception as e:
        print(f"온도 센서 읽기 오류: {e}")
        return 0.0

def read_adc_pcf8591(channel):
    """pcf8591_read.c 파일의 로직 구현 (Dummy Read 포함)"""
    try:
        # 1. 제어 바이트 전송 (채널 선택)
        bus.write_byte(I2C_ADDR, channel)
        
        # 2. 더미 읽기 (Dummy Read) - C코드와 동일하게 이전 값 버림
        bus.read_byte(I2C_ADDR)
        
        # 3. 실제 데이터 읽기
        value = bus.read_byte(I2C_ADDR)
        return value
    except Exception as e:
        print(f"ADC({channel}) 읽기 오류: {e}")
        return 0

def control_feeder():
    """밥 주기 동작: 모터를 잠깐 켰다가 끔"""
    print(">>> 🍚 물고기 밥 주는 중... (3초간 가동)")
    GPIO.output(PIN_FEEDER, GPIO.HIGH)
    time.sleep(1.4) # 3초 동안 밥 모터 가동 (시간 조절 가능)
    GPIO.output(PIN_FEEDER, GPIO.LOW)
    print(">>> 🍚 밥 주기 완료")

# ==========================================
# 3. MQTT 통신 및 메인 로직
# ==========================================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ MQTT 브로커 연결 성공! (IP: {BROKER_IP})")
        client.subscribe(TOPIC_CONTROL) # 제어 명령 대기
    else:
        print(f"❌ 연결 실패, 코드: {rc}")

def on_message(client, userdata, msg):
    """UI에서 온 제어 명령 처리"""
    try:
        payload = msg.payload.decode()
        cmd = json.loads(payload)
        
        device = cmd.get("device")
        state = cmd.get("state") # "ON" or "OFF" (or "ACTIVATE")
        
        print(f"📥 [명령 수신] {device} -> {state}")
        
        if device == "water_motor":
            if state == "ON":
                GPIO.output(PIN_MOTOR, GPIO.HIGH)
            else:
                GPIO.output(PIN_MOTOR, GPIO.LOW)
                
        elif device == "heater":
            if state == "ON":
                GPIO.output(PIN_HEATER, GPIO.HIGH)
            else:
                GPIO.output(PIN_HEATER, GPIO.LOW)
                
        elif device == "feeder":
            # 밥 주기는 단발성 동작
            control_feeder()
            
    except Exception as e:
        print(f"명령 처리 중 에러: {e}")

if __name__ == "__main__":
    setup_gpio()
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"📡 RPi 2 클라이언트 시작 (Broker: {BROKER_IP})")
        client.connect(BROKER_IP, PORT, 60)
        client.loop_start() # 별도 스레드에서 수신 대기
        
        while True:
            # 1. 센서 값 읽기
            temp = read_temp_ds18b20()
            turbidity = read_adc_pcf8591(0) # AIN0: 탁도
            level_raw = read_adc_pcf8591(1) # AIN1: 수위
            
            # 수위 값 퍼센트 변환 (센서 특성에 맞게 보정 필요)
            # 예: 0~255 값을 0~100%로 단순 변환
            level_percent = int((level_raw / 255.0) * 100)
            
            # 2. 데이터 패키징
            sensor_data = {
                "temp": temp,
                "turbidity": turbidity, # 필요 시 NTU 단위 변환 로직 추가
                "level": level_percent
            }
            
            # 3. 전송
            client.publish(TOPIC_SENSORS, json.dumps(sensor_data))
            # print(f"📤 데이터 전송: {sensor_data}")
            
            time.sleep(2) # 2초 간격 업데이트

    except KeyboardInterrupt:
        print("\n종료합니다...")
    finally:
        GPIO.cleanup()
        client.loop_stop()
        client.disconnect()