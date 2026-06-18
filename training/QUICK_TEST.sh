#!/bin/bash
# Quick test script for speed verification

echo "=============================================================================="
echo "🚀 Quick Speed Test for Qwen 3 4B Training"
echo "=============================================================================="
echo ""
echo "Starting training..."
echo "This will run for 5 steps to verify speed improvements."
echo ""
echo "⏱️  Watch the step times:"
echo "   ✅ Target: <400 seconds/step"
echo "   ⚠️  Warning: 400-600 seconds/step (slower than expected)"
echo "   ❌ Problem: >600 seconds/step (check device placement)"
echo ""
echo "=============================================================================="
echo ""

# Run training (will auto-stop after checkpoint or you can Ctrl+C after 5 steps)
cd "$(dirname "$0")"
python3 train_hf.py

echo ""
echo "=============================================================================="
echo "If step time is still >600s, check the diagnostic output for:"
echo "   Device: cpu     ← CPU fallback (BAD)"
echo "   Device: mps:0   ← MPS active (GOOD)"
echo "=============================================================================="
