#!/bin/bash
# Pre-training checklist for Qwen 3 4B fine-tuning

echo "=============================================================================="
echo "Pre-Training Checklist for Qwen 3 4B"
echo "=============================================================================="

# 1. Backup broken adapter
if [ -d "outputs/qwen3_4b_hf" ]; then
    echo ""
    echo "⚠️  Found existing adapter at outputs/qwen3_4b_hf"
    echo "📦 Moving to outputs/qwen3_4b_hf_broken..."
    mv outputs/qwen3_4b_hf outputs/qwen3_4b_hf_broken
    echo "✅ Backup complete"
else
    echo ""
    echo "✅ No existing adapter found (clean slate)"
fi

# 2. Check dataset
echo ""
echo "📊 Checking dataset..."
if [ -f "data/train.jsonl" ]; then
    lines=$(wc -l < data/train.jsonl)
    echo "✅ Found data/train.jsonl ($lines lines)"
    
    # Validate first line
    first_line=$(head -1 data/train.jsonl)
    if echo "$first_line" | python3 -m json.tool > /dev/null 2>&1; then
        echo "✅ JSON format valid"
    else
        echo "❌ JSON format invalid in first line"
        exit 1
    fi
else
    echo "❌ data/train.jsonl not found"
    exit 1
fi

# 3. Check Python packages
echo ""
echo "📦 Checking Python packages..."
python3 -c "import torch; print(f'✅ PyTorch: {torch.__version__}')"
python3 -c "import transformers; print(f'✅ Transformers: {transformers.__version__}')"
python3 -c "import peft; print(f'✅ PEFT: {peft.__version__}')"
python3 -c "import datasets; print(f'✅ Datasets: {datasets.__version__}')"

# 4. Check MPS availability
echo ""
echo "🖥️  Checking device..."
python3 -c "import torch; print(f'✅ MPS available: {torch.backends.mps.is_available()}')"

# 5. Check disk space
echo ""
echo "💾 Checking disk space..."
available=$(df -h . | awk 'NR==2 {print $4}')
echo "✅ Available space: $available"

# 6. Summary
echo ""
echo "=============================================================================="
echo "✅ Pre-training checks complete!"
echo "=============================================================================="
echo ""
echo "🚀 Ready to train! Run:"
echo "   python3 train_hf.py"
echo ""
echo "⏱️  Estimated time: 2-3 hours on M5 Air"
echo ""
echo "👀 Watch for:"
echo "   ✅ loss = 2.3 → 1.9 → 1.5 → 1.1  (healthy)"
echo "   ❌ loss = 0, grad_norm = nan     (diverged - stop immediately)"
echo ""
echo "=============================================================================="
