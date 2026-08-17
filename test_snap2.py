import os
os.environ["OREOSIM_ACTIVE_APP"] = "home"
import threading
import time

def snap():
    time.sleep(2)
    import pygame
    surf = pygame.display.get_surface()
    if surf:
        pygame.image.save(surf, "/home/dipak/.gemini/antigravity/brain/3995cddf-39ed-46e3-a177-ccbf84d77d56/sim_screenshot_hints.png")
    os._exit(0)

threading.Thread(target=snap, daemon=True).start()
import sys
sys.path.insert(0, os.path.abspath('oreoSim'))
import run
