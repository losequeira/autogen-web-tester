"""Configuration for AutoGen Web Tester."""

import os
import secrets
from pathlib import Path
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
VIDEO_SIZE_WIDTH = int(os.getenv("VIDEO_SIZE_WIDTH", "1920"))
VIDEO_SIZE_HEIGHT = int(os.getenv("VIDEO_SIZE_HEIGHT", "1080"))
KEEP_LAST_N_VIDEOS = int(os.getenv("KEEP_LAST_N_VIDEOS", "10"))  # Per test

# Artifact Settings
ENABLE_HAR_RECORDING = os.getenv("ENABLE_HAR_RECORDING", "true").lower() == "true"
ENABLE_TRACE_RECORDING = os.getenv("ENABLE_TRACE_RECORDING", "false").lower() == "true"
MAX_ARTIFACT_SIZE_MB = int(os.getenv("MAX_ARTIFACT_SIZE_MB", "500"))  # Fail if exceeds

# Local auto-login (single-user Mac app — skip login screen)
LOCAL_USERNAME = os.getenv("LOCAL_USERNAME", "")
LOCAL_PASSWORD = os.getenv("LOCAL_PASSWORD", "")

# CDP Screencast (live browser view quality)
USE_CDP_SCREENCAST = os.getenv("USE_CDP_SCREENCAST", "true").lower() == "true"
SCREENCAST_JPEG_QUALITY = int(os.getenv("SCREENCAST_JPEG_QUALITY", "100"))
SCREENCAST_MAX_WIDTH = int(os.getenv("SCREENCAST_MAX_WIDTH", "1920"))
SCREENCAST_MAX_HEIGHT = int(os.getenv("SCREENCAST_MAX_HEIGHT", "1080"))


# Multi-User Configuration
class Config:
    """Flask application configuration."""

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "test-artifacts")

    # Local artifact storage (Mac app — videos/HAR saved to disk)
    ARTIFACTS_DIR: Path = Path.home() / ".autogen" / "artifacts"

    # Flask Secret Key (for CSRF protection)
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_hex(32)
        print("WARNING: SECRET_KEY not set in .env - using temporary random key")

    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Rate Limiting (optional, for production)
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "false").lower() == "true"
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")

