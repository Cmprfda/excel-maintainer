import os

SERVER_PORT = int(os.environ.get("PORT", 8780))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_JSON = os.path.join(BASE_DIR, "files.json")
GRAPH_CONFIG_JSON = os.path.join(BASE_DIR, "graph_config.json")
GRAPH_TOKEN_JSON = os.path.join(BASE_DIR, "graph_token.json")
LOG_FILE = os.path.join(BASE_DIR, "maintainer.log")

# Mutable globals — always read as config.X
DEV_MODE = False
