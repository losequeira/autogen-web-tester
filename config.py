"""Configuration for AutoGen Web Tester."""

import os
import sys
import secrets
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables — resolve .env path for both dev and frozen (PyInstaller) modes
if getattr(sys, 'frozen', False):
    _base_dir = Path(sys._MEIPASS)
else:
    _base_dir = Path(__file__).parent

load_dotenv(_base_dir / '.env')

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in .env file")

# Website Configuration
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://sunny.com")

# Browser Settings
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"
TIMEOUT = int(os.getenv("TIMEOUT", "60000"))  # 60 seconds default

# Model Configuration
MODEL_NAME = "gpt-4o"  # Use gpt-4o-mini for cheaper testing

# Video Recording Settings
ENABLE_VIDEO_RECORDING = os.getenv("ENABLE_VIDEO_RECORDING", "true").lower() == "true"
VIDEO_SIZE_WIDTH = int(os.getenv("VIDEO_SIZE_WIDTH", "1920"))
VIDEO_SIZE_HEIGHT = int(os.getenv("VIDEO_SIZE_HEIGHT", "1080"))
KEEP_LAST_N_VIDEOS = int(os.getenv("KEEP_LAST_N_VIDEOS", "10"))  # Per test

# Artifact Settings
ENABLE_HAR_RECORDING = os.getenv("ENABLE_HAR_RECORDING", "true").lower() == "true"
ENABLE_TRACE_RECORDING = os.getenv("ENABLE_TRACE_RECORDING", "true").lower() == "true"
MAX_ARTIFACT_SIZE_MB = int(os.getenv("MAX_ARTIFACT_SIZE_MB", "500"))  # Fail if exceeds

# Recorder: minimum pause (ms) between actions to record as an explicit wait step
RECORDER_WAIT_THRESHOLD_MS = int(os.getenv("RECORDER_WAIT_THRESHOLD_MS", "1000"))

# CDP Screencast (live browser view quality)
USE_CDP_SCREENCAST = os.getenv("USE_CDP_SCREENCAST", "true").lower() == "true"
SCREENCAST_JPEG_QUALITY = int(os.getenv("SCREENCAST_JPEG_QUALITY", "100"))
SCREENCAST_MAX_WIDTH = int(os.getenv("SCREENCAST_MAX_WIDTH", "1920"))
SCREENCAST_MAX_HEIGHT = int(os.getenv("SCREENCAST_MAX_HEIGHT", "1080"))


class Config:
    """Flask application configuration."""

    # Local workspace tree (Saved Tests / AI Steps)
    AUTOGEN_WORKSPACES_DIR: Path = Path.home() / ".autogen" / "workspaces"

    # Flask Secret Key
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_hex(32)

