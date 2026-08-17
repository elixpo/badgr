import os

os.environ["OREOSIM_ACTIVE_APP"] = "home"
import threading
import time


def snap():
    time.sleep(2)
    import pygame

    pygame.image.save(pygame.display.get_surface(), "sim_screenshot_launcher_test.png")
    print("SAVED SCREENSHOT")
    os._exit(0)


threading.Thread(target=snap, daemon=True).start()

with open("oreoSim/run.py") as f:
    exec(f.read(), {"__name__": "__main__"})
