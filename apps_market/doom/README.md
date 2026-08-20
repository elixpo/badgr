# 👾 DOOM for OreoOS

This is a native port of the authentic `doomgeneric` engine for OreoOS. It includes the original `doom1.wad` shareware episode (E1M1 Hangar) and runs at a 1:1 pixel framebuffer mapping on the ESP32-S3.

## Features
- **1:1 Pixel Mapping**: Renders natively onto the LCD without tearing or loading gap artifacts.
- **MicroPython Hardware Interfacing**: The underlying C engine communicates efficiently with MicroPython to read gamepad inputs and push framebuffer lines.
- **Full Key Mapping**:
  - `UP`/`DOWN`: Move Forward/Backward
  - `LEFT`/`RIGHT`: Turn Left/Right
  - `A`: Fire Weapon
  | `B`: Use / Open Door
  | `C`: Cycle Weapon

## OS Integration
This app declares `FULLSCREEN = True` and `NO_HEADER = True` to give DOOM full control over the 320x240 LCD real estate.

It is distributed via the **App Market** (`apps_market/`) and installed natively to `badge_data/apps/doom` to ensure it doesn't consume flash space for users who opt out.
