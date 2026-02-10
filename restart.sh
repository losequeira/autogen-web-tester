#!/bin/bash

echo "🔄 Restarting AutoGen Web Tester..."
echo ""

# Kill any existing instances
echo "1️⃣  Stopping existing server..."
pkill -f "python3 web_ui.py" 2>/dev/null || true
sleep 1

# Start fresh
echo "2️⃣  Starting server..."
python3 web_ui.py
