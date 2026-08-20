"""Pixel-perfect 13x13 Active WiFi Status Icon for OreoOS."""

W = 13
H = 13
M = b"\xf8\x1f"  # Transparent Chroma-Key (Magenta 0xF81F)
O = b"\xff\xff"  # Bright White (0xFFFF)

DATA = (
    M * 13
    + M * 2
    + O * 9
    + M * 2
    + M * 1
    + O * 2
    + M * 7
    + O * 2
    + M * 1
    + M * 13
    + M * 3
    + O * 7
    + M * 3
    + M * 2
    + O * 2
    + M * 5
    + O * 2
    + M * 2
    + M * 13
    + M * 4
    + O * 5
    + M * 4
    + M * 4
    + O * 1
    + M * 3
    + O * 1
    + M * 4
    + M * 13
    + M * 5
    + O * 3
    + M * 5
    + M * 5
    + O * 3
    + M * 5
    + M * 13
)
