<div align="center">

# Yansikjang
### Smart aquaculture management system with a touch UI and dual-Raspberry Pi control

A compact embedded project that monitors tank conditions in real time and combines manual control with rule-based automation for small-scale aquaculture environments.

<img src="./assets/readme/hero-demo.png" alt="Smart aquaculture demo setup with touchscreen UI and tank hardware" width="88%" />

<br />

<img src="https://img.shields.io/badge/Field-Embedded%20Systems-0A66C2?style=for-the-badge" alt="Embedded Systems badge" />
<img src="https://img.shields.io/badge/UI-PyQt5-2563eb?style=for-the-badge" alt="PyQt5 badge" />
<img src="https://img.shields.io/badge/Protocol-MQTT-0f766e?style=for-the-badge" alt="MQTT badge" />
<img src="https://img.shields.io/badge/Platform-Raspberry%20Pi-b45309?style=for-the-badge" alt="Raspberry Pi badge" />

</div>

---

## Overview

`Yansikjang` is a small smart-farm style aquaculture project built around two Raspberry Pi roles. One device runs a full-screen PyQt5 dashboard for monitoring and touch input, while the other reads sensors and drives the actuators connected to the tank.

The project focuses on practical embedded integration rather than cloud infrastructure. It brings together a touchscreen UI, MQTT messaging, analog and digital sensors, GPIO-based actuator control, and UI-side rule evaluation in one local system.

---

## Key Features

- Real-time monitoring for temperature, turbidity score, and water level
- Touch-friendly PyQt5 dashboard with a kiosk-style full-screen layout
- Manual device control for the water motor, heater, and feeder
- Rule-based automation for turbidity, temperature, and low-level alerts
- Split architecture that separates UI work from sensor and actuator control
- MQTT-based communication using `farm/sensors` and `farm/control`

---

## Gallery

<table>
  <tr>
    <td width="50%">
      <img src="./assets/readme/ui-dashboard.png" alt="Touchscreen dashboard UI" width="100%" />
    </td>
    <td width="50%">
      <img src="./assets/readme/hardware-overview.png" alt="Tank and circuit hardware overview" width="100%" />
    </td>
  </tr>
</table>

<p align="center">
  <sub>The README uses presentation-derived images to show the touchscreen UI, the tank prototype, and the hardware setup together.</sub>
</p>

---

## System Architecture

<p align="center">
  <img src="./assets/readme/system-architecture.png" alt="Dual Raspberry Pi system architecture" width="82%" />
</p>

The repository is organized around two runtime roles:

- **UI Raspberry Pi**: runs the PyQt5 dashboard in `main.py`, visualizes incoming sensor values, evaluates the automation thresholds, and sends MQTT control commands from either the touchscreen or the rule checks.
- **Sensor / Control Raspberry Pi**: runs `rp2_client.py`, reads the sensors, drives the motor and heater outputs, handles feeder activation, and publishes telemetry back to the UI.

Communication between the two sides follows a simple MQTT publish/subscribe pattern:

- `farm/sensors` for sensor telemetry from the control side to the UI
- `farm/control` for command messages from the UI to the control side

---

## Hardware and Software Snapshot

| Category | Details |
|---|---|
| UI stack | `PyQt5`, `QTimer`, custom `stylesheet.qss` |
| MQTT client | `paho-mqtt` |
| Temperature sensor | `DS18B20` over 1-Wire |
| Analog sensors | Turbidity + water level through `PCF8591` ADC (`0x48`) |
| Actuator pins | Water motor `GPIO17`, feeder `GPIO22`, heater `GPIO27` |
| Runtime model | Local dual-device MQTT system |

The current repository styling in `stylesheet.qss` defines a dark navy dashboard with cyan highlights, card-style sensor panels, and clearly separated control buttons.

---

## Automation Logic

<p align="center">
  <img src="./assets/readme/automation-logic.png" alt="Automation thresholds and responses" width="88%" />
</p>

The current automation behavior is evaluated in `main.py` after telemetry arrives from the sensor/control side:

- If the turbidity score is `>= 30`, the water motor is turned on.
- If temperature is `<= 20C`, the heater is turned on.
- If water level is `< 45%`, the UI shows a warning dialog.

The dashboard also starts a repeating feeder timer every five minutes through `QTimer`, while still exposing a separate manual feed button in the UI.

The control flow in `main.py` also keeps track of whether a device was enabled automatically, so the system only turns a device back off if the system turned it on in the first place. That keeps manual intervention from being immediately overridden.

---

## Repository Structure

```text
yansikjang/
|- assets/
|  `- readme/
|     |- automation-logic.png
|     |- hardware-overview.png
|     |- hero-demo.png
|     |- system-architecture.png
|     `- ui-dashboard.png
|- main.py
|- mqtt_worker.py
|- rp2_client.py
|- stylesheet.qss
`- README.md
```

### File Roles

- `main.py` - PyQt5 dashboard, sensor rendering, manual controls, automation checks, and the repeating feeder timer
- `mqtt_worker.py` - MQTT thread for sensor subscriptions and control command publishing
- `rp2_client.py` - GPIO setup, sensor reads, actuator driving, and periodic telemetry publishing
- `stylesheet.qss` - dashboard look and feel, including cards, buttons, and popup styling

---

## Configuration Notes

This repository already shows the main runtime assumptions, but it is still a project archive rather than a polished deployment package.

- The UI side currently creates `MqttWorker(broker_ip="localhost")` in `main.py`.
- The control side currently targets `BROKER_IP = "192.168.0.202"` in `rp2_client.py`.
- In practice, the current code suggests the MQTT broker is expected to live on the UI host, so the broker address should be aligned before running the project across separate devices.

The code also labels turbidity as `NTU` in the UI, while `rp2_client.py` currently converts the raw ADC value into an inverted score-like value. The README keeps that distinction conservative and treats the UI label as a display choice rather than a calibrated scientific measurement.

---

## Project Context

This project was created as an embedded systems final project and works well as a portfolio piece because it shows the full path from hardware wiring to user-facing control software. It demonstrates how a small local system can combine sensing, messaging, automation, and interface design without depending on a larger cloud stack.

---

## Author

- Park Gyuhyeon
- Electrical and Electronic Engineering, Dankook University
- Interests: Embedded Systems, MCU-based control, robotics, and hardware-software integration
