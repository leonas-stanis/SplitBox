# SplitBox

A hardware-backed, cloud-connected speedrunning / session timer built with Raspberry Pi, FastAPI, MQTT, and AWS. This project provides a dedicated physical control deck with an onboard display, arcade split/reset buttons, and a mini D-Pad for category navigation, seamlessly synced via publish-subscribe channels to a web dashboard hosted on AWS.

---

## System Architecture

```
                                [ AWS Cloud Infrastructure ]
                               +----------------------------+
                               |  Nginx (Reverse Proxy)     |
                               |  TLS Encryption (HTTPS)    |
                               +--------------+-------------+
                                              |
                                              v
+-----------------------+     MQTT / TLS    +-----------------------+
|  Hardware Timer Deck  | <===============> |  FastAPI Backend App  |
|  (Raspberry Pi Node)  |   (Pub/Sub)       |  (Python Web Server)  |
+-----------------------+                   +-----------+-----------+
                                                        |
                                                        v
                                            +-----------------------+
                                            | Encrypted DB Storage  |
                                            | (Runs/Splits/PBs)     |
                                            +-----------------------+
```

### Components Overview
1. **IoT Hardware Node:** Raspberry Pi reading physical button inputs and driving an onboard OLED screen for real-time timer/delta rendering.
2. **Pub/Sub Broker:** Secure MQTT broker using TLS encryption (`port 8883`) and Access Control Lists (ACLs) for isolated publish/subscribe topics.
3. **Web Server & Backend:** FastAPI app running behind an Nginx reverse proxy on AWS with SSL/TLS termination. Serves management APIs and real-time dashboard views.
4. **Database:** Relational database storing user profiles, game categories, target splits, personal bests (PBs), and full run history logs.

---

## Hardware Component Specs & Bill of Materials

| Component | Recommended Specification | Function |
| :--- | :--- | :--- |
| **Single Board Computer** | Raspberry Pi 5 | Hardware controller running local Python pub/sub client and GPIO drivers. |
| **Display** | **Waveshare 2.4" LCD Module (ILI9341 Driver)** (240×320 pixels, I2C interface) | Real-time rendering of active timer, segment name, and PB delta (`+/-`). |
| **Main Action Buttons** | **24mm or 30mm Arcade Push Buttons** with internal microswitches (e.g., Sanwa OBSF-24 / OBSF-30) | High-durability buttons for **Start/Split** and **Reset/Undo**. |
| **Category D-Pad / Nav** | **6x6x5mm Tactile Push Button Switches** (x4) or 5-way tactile switch module | Scrolling through games, categories, and split presets on the display. |
| **Pull-up Resistors** | 10k Ohm Resistors (if internal GPIO pull-ups are disabled) | Logic stabilization for GPIO input pins. |
| **Prototyping Wiring** | Male-to-Female & Female-to-Female DuPont jumper wires | Breadboard and GPIO connection wiring. |

---
