# Repository Cleanup Audit Report
## Status: BEFORE DELETION - REVIEW REQUIRED

---

## SUMMARY

**Total items to remove/update**: 47 files and directories
**Strategy**: Archive experimental work, standardize on Qwen2.5-3B-Instruct

---

## SECTION 1: MODEL ADAPTERS TO DELETE

### A. Qwen3-4B Adapters (ALL TO DELETE)
```
training/outputs/qwen3_4b_hf/
├── (empty directory - safe to delete)

training/outputs/qwen3_4b_lora/
├── 0000500_adapters.safetensors (27MB)
├── 0001000_adapters.safetensors (27MB)
├── 0001500_adapters.safetensors (27MB)
├── adapter_config.json
├── adapters.safetensors (27MB)
└── training_info.json
Total: ~108MB
```

### B. Old Shopping Agent Adapters (Qwen2.5-Coder-3B)
```
training/outputs/shopping_agent_lora/
├── 0000250_adapters.safetensors (27MB)
├── 0000500_adapters.safetensors (27MB)
├── 0000750_adapters.safetensors (27MB)
├── 0001000_adapters.safetensors (27MB)
├── 0001250_adapters.safetensors (27MB)
├── 0001500_adapters.safetensors (27MB)
├── adapter_config.json
└── adapters.safetensors (27MB)
Total: ~189MB

training/outputs/shopping_agent_lora_hf/
├── adapter_config.json
└── adapter_model.safetensors (27MB)
Total: ~27MB
```

### C. KEEP (Qwen2.5-3B-Instruct)
```
training/outputs/qwen25_3b_instruct_lora_hf/
├── adapter_config.json
└── adapter_model.safetensors (27MB)
✅ THIS IS THE PRODUCTION ADAPTER - DO NOT DELETE
```

**Total adapter space to reclaim**: ~324MB

---

## SECTION 2: PYTHON FILES TO DELETE

### Ollama-Related Files
```
backend/ollama_parser.py (286 lines)
- Ollama Qwen3:4b parser
- Zero-shot approach
- No longer needed

scripts/test_parser.py (exists?)
- Ollama parser evaluation
```

### Test Files
```
backend/test_qwen.py (67 lines)
- Tests Qwen/Qwen3-4B with adapter
- References: ../training/outputs/qwen3_4b_hf
```

### Conversion Scripts
```
training/convert_mlx_to_hf.py (exists)
- MLX → HuggingFace conversion
- References qwen3_4b_lora
- Can be archived
```

---

## SECTION 3: TRAINING SCRIPTS TO UPDATE

### Files Referencing Qwen3-4B
```
training/train_hf.py
Line 2: "Fine-tune Qwen3-4B..."
Line 30: BASE_MODEL_NAME = "Qwen/Qwen3-4B"
Line 31: OUTPUT_DIR = "outputs/qwen3_4b_hf"
Action: UPDATE to Qwen/Qwen2.5-3B-Instruct

training/train_simple.py
Line 19: output_dir = "outputs/qwen3_4b_lora"
Line 18: model_name = "mlx-community/Qwen2.5-3B-Instruct-4bit"
Action: UPDATE output_dir only
```

---

## SECTION 4: BACKEND FILES TO UPDATE

### API Files
```
backend/api_swagger.py
Line 3: "Ollama Qwen3:4b + PostgreSQL..."
Line 26-27: References Ollama Qwen3:4b
Line 29: Imports ollama_parser
Line 127-129: References qwen3_4b_hf
Line 271-274: "AI-powered smart search with Ollama Qwen3:4b"
Line 330, 349: metadata: 'model': 'Ollama Qwen3:4b'
Line 411: "Uses fine-tuned Qwen3-4B..."
Action: REVERT to HuggingFace hf_planner

backend/hf_planner.py
Line 75: BASE_MODEL_NAME = "Qwen/Qwen3-4B"
Line 78: ADAPTER_PATH = "training/outputs/qwen3_4b_hf"
Line 140: "Using fine-tuned Qwen3 adapter..."
Line 445: metadata: 'Qwen3-4B (Hugging Face + PEFT)'
Action: UPDATE to Qwen2.5-3B-Instruct
```

---

## SECTION 5: DOCKER & CONFIG FILES

### Docker Files
```
docker-compose.yml
Line 42: HF_BASE_MODEL_NAME: Qwen/Qwen3-4B
Line 43: HF_ADAPTER_PATH: /app/training/outputs/qwen3_4b_hf
Action: UPDATE to Qwen2.5-3B-Instruct

backend/.env (check if exists)
```

---

## SECTION 6: DOCUMENTATION FILES

### Files Referencing Qwen3 or Ollama
```
MIGRATION_TO_OLLAMA.md (NEW - 248 lines)
- Complete Ollama migration guide
Action: DELETE

OLLAMA_ARCHITECTURE.md (NEW - 327 lines)
- Ollama architecture documentation
Action: DELETE

MODEL_PIPELINE_CLEANUP.md
- References Qwen3-4B
Action: UPDATE or DELETE

SPEED_OPTIMIZATIONS.md
- References Qwen/Qwen3-4B training
Action: UPDATE or ARCHIVE

training/RETRAIN_QWEN3.md (exists?)
- Qwen3 retraining guide
Action: DELETE or UPDATE

training/NAN_FIX_EXPLANATION.md (exists?)
Action: KEEP (generic fixes)

training/FINAL_FIXES_APPLIED.md (exists?)
Action: KEEP or UPDATE
```

---

## SECTION 7: ARCHIVE STRATEGY

### Create Archive Folder
```
mkdir -p training/archived_experiments/qwen3_experiments/
mkdir -p training/archived_experiments/ollama_experiments/
mkdir -p training/archived_experiments/old_adapters/
```

### Move (Don't Delete) Experimental Work
```
# Qwen3 adapters
mv training/outputs/qwen3_4b_hf/ training/archived_experiments/qwen3_experiments/
mv training/outputs/qwen3_4b_lora/ training/archived_experiments/qwen3_experiments/

# Old Qwen2.5-Coder adapters
mv training/outputs/shopping_agent_lora/ training/archived_experiments/old_adapters/
mv training/outputs/shopping_agent_lora_hf/ training/archived_experiments/old_adapters/

# Ollama files
mv backend/ollama_parser.py training/archived_experiments/ollama_experiments/
mv OLLAMA_ARCHITECTURE.md training/archived_experiments/ollama_experiments/
mv MIGRATION_TO_OLLAMA.md training/archived_experiments/ollama_experiments/

# Test files
mv backend/test_qwen.py training/archived_experiments/qwen3_experiments/
```

---

## SECTION 8: FILES TO KEEP & UPDATE

### Training Pipeline
```
✅ training/data/train.jsonl (KEEP - dataset)
✅ training/train_hf.py (UPDATE - change model name)
✅ training/train_simple.py (UPDATE - change output dir)
✅ training/outputs/qwen25_3b_instruct_lora_hf/ (KEEP - production adapter)
```

### Backend
```
✅ backend/hf_planner.py (UPDATE - change model name)
✅ backend/api_swagger.py (UPDATE - revert to hf_planner)
✅ backend/search_pipeline.py (KEEP - no changes)
✅ backend/embedding.py (KEEP - no changes)
✅ backend/db.py (KEEP - no changes)
✅ backend/tools.py (KEEP - no changes)
```

### Deployment
```
✅ Dockerfile (UPDATE if needed)
✅ docker-compose.yml (UPDATE model names)
✅ backend/.env (UPDATE model paths)
✅ backend/requirements_production.txt (KEEP)
```

---

## SECTION 9: FINAL PRODUCTION STATE

### Single Model Pipeline
```
Dataset (train.jsonl)
    ↓
Qwen2.5-3B-Instruct (HuggingFace)
    ↓
LoRA Fine-tuning (train_hf.py)
    ↓
qwen25_3b_instruct_lora_hf/
    ↓
hf_planner.py (inference)
    ↓
Hybrid Search + pgvector
    ↓
Render Deployment
```

### Environment Variables (Final)
```
HF_BASE_MODEL_NAME=Qwen/Qwen2.5-3B-Instruct
HF_ADAPTER_PATH=/app/training/outputs/qwen25_3b_instruct_lora_hf
```

---

## SPACE SAVINGS

- Qwen3 adapters: ~108MB
- Shopping agent adapters: ~216MB
- Documentation: ~2MB
- **Total: ~326MB**

---

## RISK ASSESSMENT

### Low Risk (Safe to Delete/Archive)
- ✅ qwen3_4b_hf/ (empty)
- ✅ qwen3_4b_lora/ (experimental)
- ✅ shopping_agent_lora/ (old model)
- ✅ shopping_agent_lora_hf/ (old model)
- ✅ ollama_parser.py (not in production)
- ✅ test_qwen.py (test file)
- ✅ OLLAMA_ARCHITECTURE.md (documentation)
- ✅ MIGRATION_TO_OLLAMA.md (documentation)

### Medium Risk (Review Before Delete)
- ⚠️  convert_mlx_to_hf.py (may be useful for future conversions)
- ⚠️  SPEED_OPTIMIZATIONS.md (has generic optimization tips)

### High Risk (DO NOT DELETE)
- ❌ qwen25_3b_instruct_lora_hf/ (PRODUCTION ADAPTER)
- ❌ train.jsonl (TRAINING DATA)
- ❌ hf_planner.py (PRODUCTION INFERENCE)
- ❌ api_swagger.py (PRODUCTION API)

---

## RECOMMENDED ACTIONS

### Phase 1: Archive (Reversible)
```bash
mkdir -p training/archived_experiments/{qwen3,ollama,old_adapters}
# Move files to archive (see Section 7)
```

### Phase 2: Update Code
- Update train_hf.py → Qwen2.5-3B-Instruct
- Update hf_planner.py → Qwen2.5-3B-Instruct
- Revert api_swagger.py → hf_planner
- Update docker-compose.yml

### Phase 3: Test
- Run train_hf.py (verify it works)
- Test hf_planner.py (verify inference)
- Test API end-to-end

### Phase 4: Clean Archive (Optional)
- After 1 week of successful production
- Delete archived_experiments/ if not needed

---

## APPROVAL REQUIRED

⚠️  **Before proceeding, confirm:**

1. ✅ Archive experimental adapters (324MB)
2. ✅ Delete Ollama files
3. ✅ Update all code to Qwen2.5-3B-Instruct
4. ✅ Keep qwen25_3b_instruct_lora_hf/ as production adapter

**Reply "PROCEED" to start cleanup**

---

**Generated**: $(date)
**Status**: AWAITING APPROVAL
