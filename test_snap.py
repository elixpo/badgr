import os
os.environ["OREOSIM_ACTIVE_APP"] = "home"
import threading
import time

def snap():
    time.sleep(1.5)
    import pygame
    pygame.image.save(pygame.display.get_surface(), "sim_screenshot_hints.png")
    os._exit(0)

threading.Thread(target=snap, daemon=True).start()

# Load the simulator properly
import sys
sys.path.insert(0, os.path.abspath('oreoSim'))
import run
