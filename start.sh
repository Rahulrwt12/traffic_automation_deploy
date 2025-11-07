#!/bin/bash
# ============================================================================
# Traffic Automation - Production Startup Script
# ============================================================================
# This script handles the complete startup process for production deployment

set -e  # Exit on error

echo "============================================================================"
echo "🚀 Traffic Automation - Starting Application"
echo "============================================================================"
echo ""

# ============================================================================
# 1. Environment Check
# ============================================================================
echo "📋 Step 1: Checking environment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo ""
    echo "Please create .env file from .env.example:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edit with your actual credentials"
    echo ""
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  WARNING: Virtual environment not found. Creating..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# ============================================================================
# 2. Dependencies Check
# ============================================================================
echo ""
echo "📦 Step 2: Checking dependencies..."

# Check if requirements are installed
if ! python -c "import streamlit" 2>/dev/null; then
    echo "⚠️  Dependencies not installed. Installing..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

# ============================================================================
# 3. Playwright Browsers Check
# ============================================================================
echo ""
echo "🌐 Step 3: Checking Playwright browsers..."

# Check if Chromium is installed
if [ ! -d "$HOME/.cache/ms-playwright/chromium-"* ] && [ ! -d "/ms-playwright/chromium-"* ]; then
    echo "⚠️  Chromium browser not found. Installing..."
    playwright install chromium
    playwright install-deps chromium
    echo "✅ Chromium browser installed"
else
    echo "✅ Chromium browser already installed"
fi

# ============================================================================
# 4. Environment Variables Check
# ============================================================================
echo ""
echo "🔐 Step 4: Validating environment variables..."

# Load .env and check critical variables
export $(cat .env | grep -v '^#' | xargs)

if [ -z "$PROXY_API_KEY" ]; then
    echo "⚠️  WARNING: PROXY_API_KEY not set in .env"
    echo "   The bot will not be able to fetch proxies!"
fi

if [ -z "$BROWSER_AUTH_USERNAME" ] || [ -z "$BROWSER_AUTH_PASSWORD" ]; then
    echo "ℹ️  INFO: Browser authentication not configured"
    echo "   This is OK if you're not using QA environment"
fi

echo "✅ Environment variables loaded"

# ============================================================================
# 5. Configuration Check
# ============================================================================
echo ""
echo "⚙️  Step 5: Checking configuration..."

if [ ! -f "config.json" ]; then
    echo "❌ ERROR: config.json not found!"
    exit 1
fi

echo "✅ Configuration file found"

# ============================================================================
# 6. Create Required Directories
# ============================================================================
echo ""
echo "📁 Step 6: Creating required directories..."

mkdir -p uploads
mkdir -p logs
mkdir -p backups

echo "✅ Directories created"

# ============================================================================
# 7. Port Configuration
# ============================================================================
echo ""
echo "🔌 Step 7: Configuring port..."

# Use PORT from .env or default to 8501
PORT=${PORT:-8501}
echo "✅ Application will run on port: $PORT"

# ============================================================================
# 8. Final Checks
# ============================================================================
echo ""
echo "✔️  Step 8: Final checks..."

# Check available memory
AVAILABLE_MEMORY=$(free -m | awk 'NR==2{printf "%.0f", $7}')
echo "   Available memory: ${AVAILABLE_MEMORY}MB"

if [ $AVAILABLE_MEMORY -lt 4000 ]; then
    echo "⚠️  WARNING: Low available memory (< 4GB)"
    echo "   Consider reducing max_concurrent_proxies in config.json"
fi

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "   Python version: $PYTHON_VERSION"

echo ""
echo "============================================================================"
echo "✅ All checks passed! Starting application..."
echo "============================================================================"
echo ""

# ============================================================================
# 9. Start Application
# ============================================================================
echo "🚀 Starting Streamlit application..."
echo ""
echo "📊 Dashboard will be available at:"
echo "   Local:  http://localhost:$PORT"
echo "   Network: http://$(hostname -I | awk '{print $1}'):$PORT"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""
echo "============================================================================"
echo ""

# Start Streamlit with production settings
exec streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.runOnSave=false \
    --browser.serverAddress=0.0.0.0 \
    --browser.gatherUsageStats=false

