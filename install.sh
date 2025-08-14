#!/bin/bash
# Installation script for Marketplace Monitor

set -e

echo "🚀 Installing Marketplace Monitor..."

# Check if Python 3.8+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)" 2>/dev/null; then
    echo "❌ Python 3.8+ is required. You have Python $python_version"
    exit 1
fi

echo "✅ Python $python_version found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install package in development mode
echo "📥 Installing Marketplace Monitor..."
pip install -e .

echo ""
echo "✅ Installation completed!"
echo ""
echo "📝 Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Initialize configuration: marketplace-monitor init"
echo "3. Edit config.yaml with your sites and notification settings"
echo "4. Set environment variables (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)"
echo "5. Test setup: marketplace-monitor test-notifications"
echo "6. Start monitoring: marketplace-monitor start"
echo ""
echo "📚 For more information, see README.md"
