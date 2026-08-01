import os

SERVER_PORT = int(os.environ.get("PORT", 8780))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL_DIR = os.path.join(BASE_DIR, "for_testing_original")
SERVER_DIR = os.path.join(BASE_DIR, "for_testing_server")
LOG_FILE = os.path.join(BASE_DIR, "maintainer.log")

os.makedirs(ORIGINAL_DIR, exist_ok=True)
os.makedirs(SERVER_DIR, exist_ok=True)

# Mutable globals — always read as config.X
DEV_MODE = False
