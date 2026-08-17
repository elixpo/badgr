# 🎵 Spotify for OreoOS

The flagship music streaming controller for OreoOS, communicating directly with the Spotify Web API.

## Features
- **Cloud Authentication Relay**: Because the ESP32-S3 cannot easily handle full OAuth flows and callback URLs, we offload the OAuth token exchange to a Next.js relay (`oreo.elixpo`). The badge pairs with the user's Spotify account securely using a 6-digit PIN and a dynamically generated QR code.
- **MicroPython Web Client (`spotify.py`)**: A raw, non-blocking TLS socket client that implements the standard Spotify Web API v1.
- **Debounced Volume Control**: Volume updates are buffered via a 350ms software debounce to avoid ratelimiting the Spotify API when scrolling rapidly with the D-Pad.
- **Zero-Lag Architecture**: Uses `_thread` to push API polling and album art fetching to the background, ensuring the UI remains buttery smooth on the ESP32-S3.

## OS Integration
The app caches credentials securely inside the `badge_data/apps/spotify/` directory.

Since it uses heavy `_thread` fetching, the app manually hooks into the OreoOS garbage collector on setup, teardown, and transition states to prevent PSRAM fragmentation.
