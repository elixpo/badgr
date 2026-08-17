"""Pixel-perfect 13x13 Inactive WiFi Status Icon with red slash for OreoOS."""

W = 13
H = 13
M = b"\xf8\x1f"  # Transparent Chroma-Key (Magenta 0xF81F)
G = b"\x7b\xef"  # Dimmed Muted Grey (0x7BEF)
R = b"\xf8\x00"  # High-Contrast Red (0xF800)

DATA = (
    M * 11
    + R * 2
    + M * 2
    + G * 7
    + R * 2
    + G * 1
    + M * 1
    + M * 1
    + G * 2
    + M * 5
    + R * 2
    + G * 1
    + M * 2
    + M * 7
    + R * 2
    + M * 4
    + M * 3
    + G * 3
    + R * 2
    + G * 2
    + M * 3
    + M * 2
    + G * 2
    + M * 1
    + R * 2
    + M * 2
    + G * 2
    + M * 2
    + M * 4
    + R * 2
    + M * 7
    + M * 3
    + R * 2
    + G * 1
    + M * 3
    + G * 1
    + M * 3
    + M * 2
    + R * 2
    + M * 2
    + G * 1
    + M * 1
    + G * 1
    + M * 4
    + M * 1
    + R * 2
    + M * 10
    + R * 2
    + M * 4
    + G * 2
    + M * 5
    + R * 1
    + M * 5
    + G * 2
    + M * 5
    + M * 13
)
