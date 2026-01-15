#!/bin/bash
# XorthonL API Server Startup Script

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export DISPLAY=:99
export XORTHONL_API_HOST=0.0.0.0
export XORTHONL_API_PORT=12000

# Start Xvfb for headless browser support
echo "🖥️  Starting virtual display..."
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
sleep 2

# Start Redis if not running
echo "🔴 Starting Redis server..."
redis-server --daemonize yes

# Wait for Redis to start
sleep 2

# Start the API server
echo "🚀 Starting XorthonL API server..."
echo "📍 Server will be available at: http://localhost:12000"
echo "📖 API documentation at: http://localhost:12000/docs"
echo "🛑 Press Ctrl+C to stop the server"
echo ""

python -m uvicorn api.main:app --host 0.0.0.0 --port 12000 --reload
