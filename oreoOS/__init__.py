# ruff: noqa: F401
"""oreoOS — the Python OS layer for the Oreo conference badge.

Apps subclass `oreoOS.App` and import services from this package:

    import oreoOS
    from oreoOS import api, theme, widgets

    class App(oreoOS.App):
        def on_enter(self, os): ...
"""

from . import font
from .api import (
    ADC,
    BLACK,
    BLUE,
    BTN_A,
    BTN_B,
    BTN_C,
    BTN_DOWN,
    BTN_HOME,
    BTN_LEFT,
    BTN_RIGHT,
    BTN_UP,
    BUTTONS,
    CYAN,
    GRAY,
    GREEN,
    IR,
    LED_BL,
    LED_BR,
    LED_TL,
    LED_TR,
    MAGENTA,
    OS,
    RED,
    SCREEN_H,
    SCREEN_W,
    WHITE,
    YELLOW,
    Buttons,
    Display,
    LEDs,
    rgb,
)
from .app import App
from .launcher import boot
from .sprite import Animation, SpriteSheet
