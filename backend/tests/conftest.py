import os

# Tests mock inference; spawning a large model per TestClient obscures isolation.
os.environ["VOICE_WORKER_ENABLED"] = "false"
