#!/bin/bash
# Setup script for Qwen3-4B-Instruct MLX training on Apple Silicon

echo "========================================="
echo "Qwen3-4B-Instruct MLX Setup"
echo "========================================="

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ Error: MLX is only supported on macOS (Apple Silicon)"
    exit 1
fi

# Check for Apple Silicon
arch=$(uname -m)
if [[ "$arch" != "arm64" ]]; then
    echo "⚠️  Warning: You're on $arch. MLX requires Apple Silicon (M1/M2/M3/M4)"
    echo "   MLX will not work properly on Intel Macs"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✓ Running on macOS Apple Silicon"

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
required_version="3.9"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "✓ Python $python_version (>= 3.9 required)"
else
    echo "❌ Python >= 3.9 required, found $python_version"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv_mlx" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv_mlx
    echo "✓ Virtual environment created: venv_mlx"
else
    echo "✓ Virtual environment exists: venv_mlx"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv_mlx/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install MLX requirements
echo ""
echo "Installing MLX and dependencies..."
echo "This may take a few minutes..."
pip install -r requirements_mlx.txt

# Verify installation
echo ""
echo "========================================="
echo "Verifying installation..."
echo "========================================="

python3 << 'EOF'
import sys

def check_import(module_name, display_name=None):
    display_name = display_name or module_name
    try:
        mod = __import__(module_name)
        version = getattr(mod, '__version__', 'unknown')
        print(f"✓ {display_name}: {version}")
        return True
    except ImportError as e:
        print(f"❌ {display_name}: Not installed")
        return False

print("")
all_ok = True
all_ok &= check_import("mlx", "MLX")
all_ok &= check_import("mlx_lm", "MLX-LM")
all_ok &= check_import("transformers", "Transformers")
all_ok &= check_import("datasets", "Datasets")
all_ok &= check_import("numpy", "NumPy")
all_ok &= check_import("pandas", "Pandas")

if all_ok:
    print("")
    print("✅ All dependencies installed successfully!")
else:
    print("")
    print("❌ Some dependencies failed to install")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Installation verification failed"
    exit 1
fi

# Test MLX
echo ""
echo "========================================="
echo "Testing MLX..."
echo "========================================="

python3 << 'EOF'
import mlx.core as mx

print("")
print("MLX Device Information:")
print(f"  Device: Apple Silicon (Metal)")
print(f"  Backend: MLX")

# Simple test
a = mx.array([1, 2, 3])
b = mx.array([4, 5, 6])
c = a + b
print(f"  Test computation: {a.tolist()} + {b.tolist()} = {c.tolist()}")
print("")
print("✓ MLX is working correctly!")
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ MLX test failed"
    exit 1
fi

# Download model (optional, will happen on first use anyway)
echo ""
echo "========================================="
echo "Model Download"
echo "========================================="
echo ""
echo "The Qwen3-4B-Instruct-4bit model (~2.5 GB) will be downloaded"
echo "automatically when you start training."
echo ""
read -p "Download now? This will take 5-10 minutes. (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Downloading model..."
    python3 << 'EOF'
from mlx_lm import load
import logging

logging.basicConfig(level=logging.INFO)

print("")
print("Downloading mlx-community/Qwen3-4B-Instruct-2507-4bit...")
print("This may take 5-10 minutes depending on your internet speed...")
print("")

try:
    model, tokenizer = load("mlx-community/Qwen3-4B-Instruct-2507-4bit")
    print("")
    print("✓ Model downloaded successfully!")
    print(f"  Location: ~/.cache/huggingface/hub/")
    print("")
except Exception as e:
    print(f"❌ Download failed: {e}")
    exit(1)
EOF
else
    echo "Skipping download. Model will be downloaded on first training run."
fi

# Summary
echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Activate the environment:"
echo "   source venv_mlx/bin/activate"
echo ""
echo "2. Start training:"
echo "   python3 train_mlx.py --mode train"
echo ""
echo "3. Test the model:"
echo "   python3 train_mlx.py --mode test --test-query 'football boots under 3000'"
echo ""
echo "Training configuration:"
echo "  Model: Qwen3-4B-Instruct (4-bit quantized)"
echo "  Framework: MLX (Apple Silicon optimized)"
echo "  Dataset: data/train.jsonl"
echo "  Output: outputs/qwen3_4b_lora_mlx/"
echo "  Memory: ~4-6 GB (fits on 8 GB Mac)"
echo ""
echo "========================================="
