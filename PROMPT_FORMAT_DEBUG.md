# Prompt Format Debugging

**Issue:** Training data uses ChatML format, but inference might use `apply_chat_template()` which could differ.

**Goal:** Investigate which prompt format matches training and produces better results.

---

## Background

### Training Format (ChatML)
```
<|im_start|>user
Horse riding boots for kids below 3000<|im_end|>
<|im_start|>assistant
{"intent": "search", "search_request": {...}}<|im_end|>
```

### Inference Format (Unknown)
Currently uses `tokenizer.apply_chat_template()` which may or may not match ChatML.

---

## Investigation Steps

### 1. Check Chat Template
When server starts, it now prints:
```
CHAT TEMPLATE INSPECTION
================================================================================
Chat template found:
{template content}
================================================================================
```

### 2. Use Debug Endpoint
```bash
# Start server
python3 local_model_server.py

# In another terminal, test
python3 test_prompt_format.py
```

**Or manually:**
```bash
curl -X POST http://localhost:8001/debug-prompt \
  -H "Content-Type: application/json" \
  -d '{"query": "Horse riding boots for kids below 3000"}'
```

### 3. Compare Outputs

The debug endpoint compares:

**Method 1: apply_chat_template**
- Uses `tokenizer.apply_chat_template(messages, add_generation_prompt=True)`
- May or may not match training format

**Method 2: Manual ChatML**
- Uses exact training format: `<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n`
- Guaranteed to match training data

---

## Debug Endpoint

### POST /debug-prompt

**Request:**
```json
{
  "query": "Horse riding boots for kids below 3000"
}
```

**Response:**
```json
{
  "query": "Horse riding boots for kids below 3000",
  "chat_template_found": true,
  "chat_template_prompt": "...",
  "chat_template_tokens": [1, 2, 3, ...],
  "chat_template_output": "{...}",
  "chatml_prompt": "<|im_start|>user\n...",
  "chatml_tokens": [1, 2, 3, ...],
  "chatml_output": "{...}",
  "comparison": {
    "prompts_match": false,
    "output_length_chat_template": 150,
    "output_length_chatml": 145,
    "token_count_chat_template": 25,
    "token_count_chatml": 24
  },
  "recommendation": "USE_CHATML - Training used ChatML format"
}
```

---

## What the Debug Shows

### Prompt Comparison
- **Raw prompts:** Shows exact text sent to model
- **Token IDs:** Shows how text is tokenized
- **Token count:** Verifies prompt length

### Output Comparison
- **Generated text:** Shows model response
- **Token IDs:** Shows generated tokens
- **Length:** Compares output sizes

### Recommendation
- `FORMATS_MATCH`: Both methods produce identical prompts ✓
- `USE_CHATML`: Prompts differ, use ChatML to match training ⚠️
- `USE_CHAT_TEMPLATE`: chat_template is correct ✓

---

## Expected Results

### If Formats Match
```
Recommendation: FORMATS_MATCH - Both methods produce identical prompts
```
✓ Continue using either method

### If Formats Differ
```
Recommendation: USE_CHATML - Training used ChatML format, inference should match
```
⚠️ Switch to ChatML format for better results

---

## Implementation

### Current Code (uses apply_chat_template)
```python
messages = [{"role": "user", "content": query}]
prompt = tokenizer.apply_chat_template(
    messages, 
    tokenize=False, 
    add_generation_prompt=True
)
inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(**inputs)
```

### ChatML Format (matches training)
```python
prompt = f"<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n"
inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(
    **inputs,
    max_new_tokens=128,
    eos_token_id=tokenizer.eos_token_id,
    pad_token_id=tokenizer.eos_token_id
)
# Extract only generated tokens
generated = outputs[0][inputs.input_ids.shape[1]:]
response = tokenizer.decode(generated, skip_special_tokens=False)
# Clean up
response = response.split("<|im_end|>")[0].strip()
```

---

## Testing Workflow

1. **Start server:**
   ```bash
   python3 local_model_server.py
   ```

2. **Check chat template in logs:**
   Look for "CHAT TEMPLATE INSPECTION" section

3. **Run debug test:**
   ```bash
   python3 test_prompt_format.py
   ```

4. **Compare outputs:**
   - Which format produces valid JSON?
   - Which format matches training expectations?
   - Do prompts match exactly?

5. **Decision:**
   - If prompts match → use either method
   - If prompts differ → switch to ChatML format
   - Update `/generate` and `/parse-query` endpoints accordingly

---

## Next Steps

### After Investigation

**If ChatML works better:**
1. Update `/generate` endpoint to use ChatML format
2. Update `/parse-query` endpoint to use ChatML format
3. Remove `apply_chat_template()` calls
4. Test with `test_local_model.py`

**If formats match:**
1. Continue using current implementation
2. Document that chat_template matches training

---

## Files Modified

- ✅ `local_model_server.py` - Added chat template printing and `/debug-prompt` endpoint
- ✅ `test_prompt_format.py` - Test script for debugging

---

## Quick Test

```bash
# Terminal 1
python3 local_model_server.py

# Terminal 2  
python3 test_prompt_format.py
```

Look for:
- ✓ Valid JSON from which method?
- ✓ Prompts match or differ?
- ✓ Recommendation?

---

**Last Updated:** June 18, 2026  
**Status:** Investigation tool ready  
**Next:** Run tests and compare outputs
