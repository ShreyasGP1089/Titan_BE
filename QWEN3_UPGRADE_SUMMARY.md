# Qwen 3 4B Upgrade - Ready to Train

## Summary

**Everything is configured** to switch from Qwen 2.5 Coder 3B to Qwen 3 4B with updated training data.

## What Was Updated

### 1. Training Script (`training/train.py`)
- ✅ Model: `unsloth/Qwen3-4B` (was Qwen2.5-Coder-3B-Instruct)
- ✅ Output: `outputs/qwen3_4b_lora/` (new directory)
- ✅ Keeps old adapter untouched

### 2. Backend API (`backend/hf_planner.py`)
- ✅ Base model: `Qwen/Qwen3-4B`
- ✅ Adapter path: `training/outputs/qwen3_4b_lora_hf/`
- ✅ Metadata: Shows "Qwen 3 4B" in responses

### 3. Training Data (`training/data/train.jsonl`)
- ✅ 52 examples total
- ✅ Added 4 new examples for running/football multi-category queries
- ✅ Examples teach model to return multiple products for "I want to start X"

## New Training Examples Added

1. **"I want to start running"**
   → Returns: shoes + shorts + t-shirt + watch

2. **"I want to start running what should I buy"**
   → Returns: shoes + shorts + t-shirt

3. **"I want to start playing football"**
   → Returns: ball + shoes + shin guards + jersey

4. **"I want to start playing football what should I buy"**
   → Returns: ball + shoes + shin guards

## To Start Training

```bash
cd training
python train.py
```

**Time**: 30-60 minutes on Mac with MPS GPU
**Size**: Downloads ~4GB model (first time only), trains ~16MB adapter

## After Training

1. **Copy adapter** (if needed):
   ```bash
   cp -r outputs/qwen3_4b_lora outputs/qwen3_4b_lora_hf
   ```

2. **Test**:
   ```bash
   cd ../backend
   python hf_planner.py
   ```

3. **Start API**:
   ```bash
   python api_swagger.py
   ```

## No File Deletion Needed

**Before training**:
```
training/outputs/
├── shopping_agent_lora/          # Old MLX adapter (Qwen 2.5)
└── shopping_agent_lora_hf/       # Old HF adapter (Qwen 2.5)
```

**After training**:
```
training/outputs/
├── shopping_agent_lora/          # Old MLX adapter (Qwen 2.5) ✓ Kept
├── shopping_agent_lora_hf/       # Old HF adapter (Qwen 2.5) ✓ Kept
├── qwen3_4b_lora/                # New adapter (Qwen 3 4B) ✓ New
└── qwen3_4b_lora_hf/             # New HF adapter (Qwen 3 4B) ✓ New
```

Both models coexist. You can switch between them by changing 2 lines in `backend/hf_planner.py`.

## Why Qwen 3 4B?

- **Deep thinking capability**: Better reasoning for intent detection
- **Multi-step planning**: Understands "start X sport" needs multiple product categories
- **Context awareness**: Differentiates beginner vs advanced queries
- **Better JSON parsing**: More reliable structured output

## Expected Behavior Change

**Query**: "I want to start running"

**Old behavior** (Qwen 2.5 Coder 3B):
- Intent: `search`
- Returns: Only running shoes

**New behavior** (Qwen 3 4B):
- Intent: `task`
- Returns: Shoes + shorts + t-shirt + watch (complete starter kit)

## Rollback Plan

If Qwen 3 4B doesn't work as expected, rollback is instant:

```python
# In backend/hf_planner.py (lines 31-32)
BASE_MODEL_NAME = "Qwen/Qwen2.5-Coder-3B-Instruct"  # Change back
ADAPTER_PATH = "training/outputs/shopping_agent_lora_hf"  # Change back
```

Restart API - done! Old adapter is still there.

## Next Steps

1. ✅ Configuration complete
2. ⏳ **Run training** → `cd training && python train.py`
3. ⏳ Test new model → `cd ../backend && python hf_planner.py`
4. ⏳ Deploy API → `python api_swagger.py`
5. ⏳ Test query: "I want to start running"

---

**Ready to train!** Just run `python train.py` in the `training/` directory.
