#!/usr/bin/env bash
# Install Python-based maider tool

set -euo pipefail

echo "════════════════════════════════════════════════════════"
echo "  Installing Python-based Linode LLM maider"
echo "════════════════════════════════════════════════════════"
echo

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | sed 's/Python //' | cut -d. -f1-2)
REQUIRED_VERSION="3.10"

if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]]; then
    echo "❌ Python 3.10 or later required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✓ Python $PYTHON_VERSION found"

# Create virtual environment
if [[ ! -d venv ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip > /dev/null
pip install -e . > /dev/null

echo
echo "✓ Installation complete!"
echo
echo "════════════════════════════════════════════════════════"
echo "  Quick Start"
echo "════════════════════════════════════════════════════════"
echo
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo
echo "2. Validate your configuration:"
echo "   maider validate"
echo
echo "3. Create a VM:"
echo "   maider up"
echo
echo "4. List VMs:"
echo "   maider list"
echo
echo "5. Destroy a VM:"
echo "   maider down"
echo
echo "════════════════════════════════════════════════════════"
