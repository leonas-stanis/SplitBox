# SplitBox: IoT Speedrunning & Session Timer

A hardware-backed, cloud-connected speedrunning timer built for the DkIT Software Development IoT module (2026-27). This project pairs a Raspberry Pi 5 with a simplified arcade-style dual-button control deck and an SPI display, communicating securely via MQTT over TLS with a FastAPI cloud backend hosted on AWS.

---

## 1. System Architecture & Data Flow

```
                                [ AWS Cloud Infrastructure ]
                               +----------------------------+
                               |  Nginx Reverse Proxy       |
                               |  TLS/HTTPS Termination     |
                               +--------------+-------------+
                                              |
                                              v
+-----------------------+     MQTT / TLS    +-----------------------+
|  Hardware Timer Deck  | <===============> |  FastAPI Backend App  |
|  (Raspberry Pi 5)     |   (Port 8883)     |  (REST API & DB Sync) |
+-----------------------+                   +-----------+-----------+
                                                        |
                                                        v
                                            +-----------------------+
                                            | Encrypted PostgreSQL  |
                                            | (Runs/Splits/PBs)     |
                                            +-----------------------+
```

### Data Flow Pipeline
1. **IoT Edge Trigger:** The Raspberry Pi 5 receives input events via USB gamepad interface (SJ@JX Zero-Delay USB Encoder) driven by physical arcade buttons.
2. **Local Processing:** Button 1 triggers start/split events. Button 2 triggers a timer reset when held continuously for 2.5 seconds.
3. **Pub/Sub Transport:** Events are published over encrypted MQTT (`port 8883`) using TLS certificates and topic ACLs to the cloud broker.
4. **Cloud Processing:** The FastAPI backend consumes MQTT payloads, logs run metrics into the encrypted PostgreSQL database, and serves live telemetry to the web dashboard.

---

## 2. Bill of Materials (Zero-Solder Hardware Setup)

| Component | Specification | Interface & Wiring Method |
| :--- | :--- | :--- |
| **Single Board Controller** | Raspberry Pi 5 | Core hardware node running Python HID reader, SPI screen driver, and MQTT client. |
| **Display Module** | **Waveshare 2.4" LCD TFT Display Module** (240x320, ILI9341 Driver, SPI) | Connected directly to Pi 5 GPIO SPI header pins via Female-to-Female DuPont jumper cables. |
| **Control Interface** | **SJ@JX DIY Arcade Game Button & Joystick Kit** (Zero-Delay USB Encoder Board) | Buttons connect to yellow encoder board via quick-connect 2-pin cables; encoder plugs into Pi 5 USB port. |
| **Action Buttons (x2)** | 28mm Arcade Push Buttons (from SJ@JX kit) | Button 1 (Start/Split) and Button 2 (Reset Hold) wired to USB encoder ports. |
| **Hardware Resistors** | None required | Debouncing and signal stabilization handled by hardware encoder IC. |

---

## 3. Prototype Hardware Pin & Interface Mapping Guide

### Display Interface Mapping (Waveshare 2.4" TFT SPI)

| Screen Pin | Target Pi 5 Pin | Physical Pin # | Function / Signal |
| :--- | :--- | :--- | :--- |
| **VCC** | 3.3V Power | Pin 1 | Power Input (3.3V) |
| **GND** | Ground | Pin 6 | Ground |
| **DIN** | SPI MOSI | Pin 19 | `SPI0_MOSI` (Master Out Slave In) |
| **CLK** | SPI Clock | Pin 23 | `SPI0_SCLK` (Serial Clock) |
| **CS** | SPI Chip Select | Pin 24 | `SPI0_CE0` (Chip Enable 0) |
| **DC** | Data / Command | Pin 22 | `GPIO 25` (Data/Command Control) |
| **RST** | Display Reset | Pin 13 | `GPIO 27` (Hardware Reset) |
| **BL** | Backlight Control | Pin 17 | 3.3V Power / Backlight PWM |

### USB Arcade Controller Interface (SJ@JX Zero-Delay Board)

| Hardware Input | Encoder Interface Port | Pi 5 System Input | Software Role |
| :--- | :--- | :--- | :--- |
| **Arcade Button 1** | Terminal `K1` (2-Pin Harness) | USB HID Event / Gamepad `BTN_THUMB` | **Start / Split Action** |
| **Arcade Button 2** | Terminal `K2` (2-Pin Harness) | USB HID Event / Gamepad `BTN_THUMB2` | **Reset Action** (2.5s continuous hold requirement) |
| **USB Out** | USB Type-A Port | Pi 5 USB 3.0 / 2.0 Host Port | Plug-and-Play USB Gamepad Device (`/dev/input/js0`) |

---

## 4. Security Architecture

- **Data in Transit:** All HTTP traffic will be enforced via TLS 1.3 / HTTPS through Nginx on AWS. IoT-to-server messaging will be strictly encrypted using MQTT over TLS (Port 8883) with mutual certificate verification.
- **Data at Rest:** Database storage will use encrypted volumes, hashed user credentials (`bcrypt`), and parameterized queries to prevent SQL injection.
- **Device & Channel Access:** MQTT brokers enforce strict Access Control Lists (ACLs) per client ID. API endpoints require JWT authentication.
- **Secret Management:** All API keys, database URLs, and MQTT credentials are stored in environment variables (`.env`) and excluded via `.gitignore`. No default configurations or hardcoded secrets will be used.

---
