"""Configuration for AutoGen Web Tester."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
VIDEO_SIZE_WIDTH = int(os.getenv("VIDEO_SIZE_WIDTH", "1280"))
VIDEO_SIZE_HEIGHT = int(os.getenv("VIDEO_SIZE_HEIGHT", "720"))
KEEP_LAST_N_VIDEOS = int(os.getenv("KEEP_LAST_N_VIDEOS", "10"))  # Per test

# Artifact Settings
ENABLE_HAR_RECORDING = os.getenv("ENABLE_HAR_RECORDING", "true").lower() == "true"
ENABLE_TRACE_RECORDING = os.getenv("ENABLE_TRACE_RECORDING", "false").lower() == "true"
MAX_ARTIFACT_SIZE_MB = int(os.getenv("MAX_ARTIFACT_SIZE_MB", "500"))  # Fail if exceeds
