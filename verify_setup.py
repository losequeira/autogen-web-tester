"""Quick setup verification script."""

import sys

print("🔍 Verifying AutoGen Web Tester setup...\n")

# Check Python version
print(f"✓ Python version: {sys.version.split()[0]}")

# Check required packages
try:
    import autogen_agentchat
    print(f"✓ autogen-agentchat: {autogen_agentchat.__version__}")
except ImportError as e:
    print(f"✗ autogen-agentchat not found: {e}")

try:
    import autogen_ext
    print(f"✓ autogen-ext installed")
except ImportError as e:
    print(f"✗ autogen-ext not found: {e}")

try:
    import playwright
    print(f"✓ playwright installed")
except ImportError as e:
    print(f"✗ playwright not found: {e}")

try:
    from dotenv import load_dotenv
    print(f"✓ python-dotenv installed")
except ImportError as e:
    print(f"✗ python-dotenv not found: {e}")

# Check .env file
import os
if os.path.exists(".env"):
    print("✓ .env file exists")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and api_key != "your_openai_api_key_here":
        print(f"✓ OPENAI_API_KEY is set (length: {len(api_key)})")
    else:
        print("⚠ OPENAI_API_KEY not configured in .env file")
        print("  → Edit .env and add your OpenAI API key")
else:
    print("✗ .env file not found")

print("\n" + "="*60)
if api_key and api_key != "your_openai_api_key_here":
    print("✅ Setup complete! Ready to run test_signup.py")
else:
    print("⚠ Almost ready! Just add your OPENAI_API_KEY to .env file")
print("="*60)
