"""Standalone server launcher for the preview tool."""
import os
import sys

PROJECT_DIR = "/Users/carloscalegari/Desktop/claude-projects/tmc-cultural-calendar"
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

from app import app  # noqa: E402

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
