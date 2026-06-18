# ✅ Debug Capabilities Added

**Goal:** Investigate prompt format mismatch between training (ChatML) and inference

---

## What Was Added

### 1. Chat Template Logging ✅
**Where:** `local_model_server.py` - startup

**What it does:**
- Prints tokenizer's chat template on startup
- Shows exactly what format the tokenizer uses
- Helps identify format differences

**Output example:**
```
CHAT TEMPLATE INSPECTION
================================================================================
Chat template found:
{%- for message in messages %}
    {{- '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>\n' }}
{%- endfor %}
{%- if add_generation_prompt %}
    {{- '<|im_start|>assistant\n' }}
{%- endif %}
================================================================================
```

---

### 2. Debug Endpoint ✅
**Endpoint:** `POST /debug-prompt`

**Input:**
```json
{
  "query": "Horse riding boots for kids below 3000"
}
```

**What it does:**
1. Tests `apply_chat_template()` method
2. Tests manual ChatML format (training format)
3. Shows prompts for both methods
4. Shows token IDs for both methods
5. Generates output with both methods
6. Compares results
7. Recommends which format to use

**Output includes:**
- Raw prompts from both methods
- Token IDs from both methods
- Generated outputs from both methods
- Comparison (do prompts match?)
- Recommendation (which to use)

---

### 3. Test Script ✅
**File:** `test_prompt_format.py`

**Usage:**
```bash
python3 test_prompt_format.py
```

**What it tests:**
- Multiple queries
- Both prompt formats
- JSON validity of outputs
- Token counts
- Output quality

---

## How to Use

### Step 1: Start Server
```bash
python3 local_model_server.py
```

**Look for:**
```
CHAT TEMPLATE INSPECTION
================================================================================
Chat template found: ...
```

This shows you what format the tokenizer uses.

---

### Step 2: Run Debug Test
```bash
# New terminal
python3 test_prompt_format.py
```

**You'll see:**
```
PROMPT FORMAT DEBUG TEST
================================================================================
Query: Horse riding boots for kids below 3000

--- Method 1: apply_chat_template ---
Prompt:
<|im_start|>user
Horse riding boots for kids below 3000<|im_end|>
<|im_start|>assistant

Token count: 25
Output:
{"intent": "search", ...}

--- Method 2: Manual ChatML Format ---
Prompt:
<|im_start|>user
Horse riding boots for kids below 3000<|im_end|>
<|im_start|>assistant

Token count: 25
Output:
{"intent": "search", ...}

--- Comparison ---
✓ Prompts MATCH - Both methods produce identical prompts

--- Recommendation ---
✓ FORMATS_MATCH - Both methods produce identical prompts
```

---

### Step 3: Interpret Results

#### Scenario A: Formats Match ✅
```
Recommendation: FORMATS_MATCH - Both methods produce identical prompts
```

**Action:** Keep using current implementation, no changes needed.

---

#### Scenario B: Formats Differ ⚠️
```
Recommendation: USE_CHATML - Training used ChatML format, inference should match
```

**Action:** Switch to ChatML format in `/generate` and `/parse-query` endpoints.

**Example change:**
```python
# BEFORE (apply_chat_template)
messages = [{"role": "user", "content": query}]
prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

# AFTER (ChatML - matches training)
prompt = f"<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n"
```

---

## What the Debug Reveals

### 1. Prompt Format
- ✓ Are prompts identical?
- ✓ Token count differences?
- ✓ Special tokens correct?

### 2. Model Output
- ✓ Which format produces valid JSON?
- ✓ Which format matches training expectations?
- ✓ Output quality differences?

### 3. Token IDs
- ✓ Are inputs tokenized identically?
- ✓ Special token IDs correct?
- ✓ Any extra tokens added?

---

## Quick Reference

### Manual Debug Request
```bash
curl -X POST http://localhost:8001/debug-prompt \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'
```

### Check Server Logs
```bash
# Look for:
# - CHAT TEMPLATE INSPECTION
# - DEBUG PROMPT COMPARISON
```

### Test Multiple Queries
Edit `test_prompt_format.py` and add more queries to `test_queries` list.

---

## Files Created

| File | Purpose |
|------|---------|
| `local_model_server.py` (updated) | Added chat template logging + debug endpoint |
| `test_prompt_format.py` | Test script for debugging |
| `PROMPT_FORMAT_DEBUG.md` | Complete debugging guide |
| `DEBUG_READY.md` | This file - quick summary |

---

## Testing Checklist

- [ ] Start server: `python3 local_model_server.py`
- [ ] Check chat template in logs
- [ ] Run test: `python3 test_prompt_format.py`
- [ ] Review prompt comparison
- [ ] Check which format produces valid JSON
- [ ] Note recommendation
- [ ] Decide: keep current or switch to ChatML

---

## Expected Timeline

1. **5 min:** Start server, check logs
2. **5 min:** Run debug test
3. **5 min:** Analyze results
4. **Decision:** Keep current or switch format

**Total:** ~15 minutes to identify the issue

---

## Important Notes

### Training Format
Your training data uses:
```
<|im_start|>user
{query}<|im_end|>
<|im_start|>assistant
{response}<|im_end|>
```

### Inference Must Match
If inference uses different format, the model may:
- Generate invalid JSON
- Produce unexpected responses
- Not follow fine-tuned patterns

### No Retraining Needed
Just adjust inference format to match training.

---

## Next Steps

1. ✅ Start server
2. ✅ Run debug test
3. ✅ Compare outputs
4. ⏭️ Update endpoints if needed (based on recommendation)
5. ⏭️ Re-test with `test_local_model.py`

---

**Status:** Debug tools ready  
**Action:** Run `python3 test_prompt_format.py` (with server running)  
**Goal:** Identify which prompt format matches training
