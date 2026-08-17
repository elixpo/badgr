import os
import sys

# Set up mock _os for oreoSim context if needed, but we are running in CPython anyway.
sys.path.insert(0, os.getcwd())
from oreoOS import launcher

launcher.bootstrap_badge_apps()
print("Bootstrapped. Apps found in badge_data/apps:")
print(os.listdir("badge_data/apps"))
