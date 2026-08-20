# 💻 oreoSim: The Desktop Simulator

Building and testing embedded applications directly on the ESP32-S3 can be slow and tedious. To solve this, OreoOS ships with a state-of-the-art desktop simulator called **oreoSim** (`oreoSim/run.py`).

`oreoSim` allows you to run, test, and debug your OreoOS apps entirely on your laptop without needing physical hardware.

## How it works

The simulator uses Pygame to render the 320x240 LCD display and intercepts all native MicroPython and ESP32-specific hardware calls.

- **Hardware Mocks**: Files like `native_esp32.py` and `native_hardware.py` fully mock modules like `machine` (Pin, ADC, PWM, I2C, SPI) and `esp32.RMT`. If your app toggles a hardware pin, the mock catches it and prevents a crash on desktop.
- **Wireless Networking**: WiFi and Bluetooth are mocked. `native_wifi.py` intercepts `network.WLAN` and seamlessly translates it into desktop `socket` and `urllib` requests, so your apps can fetch real data from the internet while running in the simulator.

## Running the Simulator

Ensure you have installed the desktop requirements:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r oreoSim/requirements.txt
```

Launch it with:
```bash
python oreoSim/run.py
```

## Features & Quirks

### 🔄 AST-Validated Hot Reloading
When you modify a Python file inside `apps/` or `oreoOS/`, the simulator instantly hot-reloads the changes into the running display.
- **AST Pre-Validation**: The hot-reloader checks your code for syntax errors (using Python's `ast.parse`) *before* applying the reload. If you accidentally save code with a missing bracket, the simulator will ignore it, log an error, and continue running the old frame, ensuring it never crashes.
- **Active State Retention**: The simulator preserves your currently open app (`OREOSIM_ACTIVE_APP`). You don't have to navigate back through the home screen after every save!

> [!WARNING]
> **Hot-Reloading Caveat**: The hot-reloader replaces the Abstract Syntax Tree (AST) of the class in real-time, but **it does not re-trigger `on_enter()`** for an app that is currently active. If you add a new instance variable (like `self._new_var`) inside `on_enter()`, the running app will throw an `AttributeError` on the next frame because `on_enter()` wasn't re-run. Always handle missing attributes gracefully (e.g., `getattr(self, "_new_var", default)`) to ensure smooth hot-reloads!

### 🎮 Controls

Use your keyboard to simulate the physical tactile buttons on the badge.

| Badge Button | Primary Key | Secondary Key | Function |
|--------------|-------------|---------------|----------|
| **UP** | <kbd>Up Arrow</kbd> | <kbd>W</kbd> | Navigate up |
| **DOWN** | <kbd>Down Arrow</kbd> | <kbd>S</kbd> | Navigate down |
| **LEFT** | <kbd>Left Arrow</kbd> | <kbd>A</kbd> | Navigate left |
| **RIGHT** | <kbd>Right Arrow</kbd> | <kbd>D</kbd> | Navigate right |
| **A** | <kbd>Z</kbd> | <kbd>J</kbd> | Primary action / Select |
| **B** | <kbd>X</kbd> | <kbd>K</kbd> | Secondary action / Cancel |
| **C** | <kbd>C</kbd> | <kbd>L</kbd> | Notification panel / Options |
| **HOME** | <kbd>Esc</kbd> | <kbd>H</kbd> | Return to launcher |

### 🔍 Display Scaling
The physical screen is 320x240, which is tiny on modern 4K desktop monitors.
- Press **<kbd>F11</kbd>** while the simulator is running to toggle between 1x, 2x, and 3x crisp integer pixel scaling!
