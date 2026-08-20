"""Base class for Oreo OS apps with MicroPython heap & GC management."""

try:
    import gc
except ImportError:
    gc = None


class App:
    """Base class for Oreo OS apps.

    Lifecycle: on_enter -> (update + draw)* -> on_exit
    Subclass and override any of: on_enter, update, draw, on_exit,
    on_button_press, on_button_release.
    """

    name = "unnamed"
    author = "sea-deep"
    SHOW_LOADING = True
    FULLSCREEN = False
    NO_HEADER = False
    CONSUMES_C = False
    HEADER_TITLE = None

    def on_enter(self, os):
        self.os = os
        if gc:
            try:
                gc.collect()
            except Exception:
                pass

    def on_exit(self):
        """Called automatically when switching apps or returning to launcher."""
        if gc:
            try:
                gc.collect()
            except Exception:
                pass

    def update(self, dt):
        """Per-frame state update. dt = seconds since last frame."""

    def draw(self, display):
        """Per-frame rendering. Don't call display.present() — the OS does that."""

    def on_button_press(self, btn):
        pass

    def on_button_release(self, btn):
        pass

    def on_home_press(self):
        return False
