#!/bin/bash
# Fix local environment for Apple Silicon compatibility
# Removes bitsandbytes and NumPy 2.x, installs compatible versions

set -e  # Exit on error

echo "========================================="
echo "FIX LOCAL ENVIRONMENT FOR APPLE SILICON"
echo "========================================="
echo ""
echo "This script will:"
echo "  1. Remove bitsandbytes (incompatible with Apple Silicon)"
echo "  2. Remove NumPy 2.x (incompatible with transformers)"
echo "  3. Install NumPy 1.x"
echo "  4. Install compatible PyTorch, transformers, PEFT"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "========================================="
echo "Step 1: Uninstalling incompatible packages"
echo "========================================="

# Uninstall bitsandbytes (if installed)
echo "Removing bitsandbytes..."
pip uninstall -y bitsandbytes 2>/dev/null || echo "  (not installed)"

# Uninstall NumPy 2.x
echo "Removing NumPy 2.x..."
pip uninstall -y numpy 2>/dev/null || echo "  (not installed)"

echo "✓ Incompatible packages removed"

echo ""
echo "========================================="
echo "Step 2: Installing NumPy 1.x"
echo "========================================="

pip install "numpy<2.0.0"

echo "✓ NumPy 1.x installed"

echo ""
echo "========================================="
echo "Step 3: Installing compatible dependencies"
echo "========================================="

pip install -r requirements_local_server.txt

echo "✓ All dependencies installed"

echo ""
echo "========================================="
echo "Step 4: Verifying installation"
echo "========================================="

python3 << 'EOF'
import sys

def check_package(name):
    try:
        module = __import__(name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✓ {name:20} {version}")
        return True
    except ImportError as e:
        print(f"✗ {name:20} NOT INSTALLED")
        return False

print("\nPackage versions:")
print("-" * 50)

all_ok = True
all_ok &= check_package('numpy')
all_ok &= check_package('torch')
all_ok &= check_package('transformers')
all_ok &= check_package('peft')
all_ok &= check_package('accelerate')
all_ok &= check_package('fastapi')
all_ok &= check_package('uvicorn')
all_ok &= check_package('safetensors')

print()

# Check NumPy version
import numpy as np
if np.__version__.startswith('2.'):
    print("⚠️  WARNING: NumPy 2.x detected - this may cause issues")
    print(f"   Version: {np.__version__}")
    print("   Recommended: numpy<2.0.0")
    all_ok = False
else:
    print(f"✓ NumPy version OK: {np.__version__}")

print()

# Check PyTorch device support
import torch
print("PyTorch device support:")
print("-" * 50)
print(f"  CUDA available: {torch.cuda.is_available()}")
print(f"  MPS available: {torch.backends.mps.is_available()}")
print(f"  MPS built: {torch.backends.mps.is_built()}")

if torch.cuda.is_available():
    print(f"  ✓ Selected device: CUDA")
elif torch.backends.mps.is_available():
    print(f"  ✓ Selected device: MPS (Apple Silicon)")
else:
    print(f"  ⚠️  Selected device: CPU (no GPU acceleration)")

print()

# Check for bitsandbytes
try:
    import bitsandbytes
    print("⚠️  WARNING: bitsandbytes is still installed")
    print("   This may cause compatibility issues on Apple Silicon")
    print("   Run: pip uninstall -y bitsandbytes")
    all_ok = False
except ImportError:
    print("✓ bitsandbytes not found (good - not needed for MPS)")

print()

if all_ok:
    print("=" * 50)
    print("✅ ENVIRONMENT READY")
    print("=" * 50)
    sys.exit(0)
else:
    print("=" * 50)
    print("❌ ENVIRONMENT HAS ISSUES")
    print("=" * 50)
    print("\nPlease fix the issues above before starting the server.")
    sys.exit(1)

EOF

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "========================================="
    echo "✅ SUCCESS - Environment is ready!"
    echo "========================================="
    echo ""
    echo "You can now start the local model server:"
    echo "  python3 local_model_server.py"
    echo ""
    echo "The server will:"
    echo "  • Load Qwen2.5-1.5B-Instruct"
    echo "  • Load LoRA adapter from training/outputs/qwen25_1_5b_lora_hf/"
    echo "  • Use MPS (Apple Silicon GPU acceleration)"
    echo "  • Listen on port 8001"
    echo ""
else
    echo "========================================="
    echo "❌ FAILED - Please fix issues above"
    echo "========================================="
fi

exit $EXIT_CODE
