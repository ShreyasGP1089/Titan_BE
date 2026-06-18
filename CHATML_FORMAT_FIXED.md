# ✅ ChatML Format Fixed

**Problem:** `tokenizer.apply_chat_template()` added system prompts and broke JSON parsing  
**Solution:** Use manual ChatML format to match training data exactly  
**Status:** Fixed and ready to test

---

## What Was Wrong

### apply_chat_template() Issues ❌

**Generated this:**
```
<|im_start|>system
You are Qwen, created by Alibaba Cloud...<|im_end|>
<|im_start|>user
Horse riding boots for kids below 3000<|im_end|>
<|im_start|>assistant
{"intent": "search", ...}<|im_end|>
```

**Problems:**
1. ❌ Added unwanted system prompt
2. ❌ Included `<|im_end|>` token in output
3. ❌ `json.loads()` failed on: `{...}<|im_end|>`
4. ❌ Didn't match training format

---

## What Was Fixed

### Manual ChatML Format ✅

**Now generates this:**
```
<|im_start|>user
Horse riding boots for kids below 3000<|im_end|>
<|im_start|>assistant
{"intent": "search", ...}
```

**Benefits:**
1. ✅ No system prompt
2. ✅ Matches training format exactly
3. ✅ Clean JSON output
4. ✅ `json.loads()` succeeds

---

## Code Changes

### /generate Endpoint

**Before:**
```python
# Used raw prompt
inputs = tokenizer(request.prompt, return_tensors="pt")
outputs = model.generate(**inputs)
# Complex extraction with apply_chat_template
```

**After:**
```python
# Use ChatML format
chatml_prompt = f"<|im_start|>user\n{request.prompt}<|im_end|>\n<|im_start|>assistant\n"
inputs = tokenizer(chatml_prompt, return_tensors="pt").to(device)

outputs = model.generate(
    **inputs,
    max_new_tokens=128,
    do_sample=False,
    eos_token_id=tokenizer.eos_token_id,
    pad_token_id=tokenizer.eos_token_id
)

# Decode only generated tokens
generated = outputs[0][inputs["input_ids"].shape[1]:]
response = tokenizer.decode(generated, skip_special_tokens=False)

# Remove stop token
response = response.split("<|im_end|>")[0].strip()
```

---

### /parse-query Endpoint

**Before:**
```python
# No ChatML format
prompt = f"{system_prompt}\n\nQuery: {request.query}"
inputs = tokenizer(prompt, return_tensors="pt")
# Complex extraction
```

**After:**
```python
# ChatML format with instructions
user_message = f"""You are a JSON parser for shopping queries...

Now parse this query:
{request.query}"""

chatml_prompt = f"<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"
inputs = tokenizer(chatml_prompt, return_tensors="pt").to(device)

outputs = model.generate(
    **inputs,
    max_new_tokens=256,
    do_sample=False,
    eos_token_id=tokenizer.eos_token_id,
    pad_token_id=tokenizer.eos_token_id
)

# Decode only generated tokens
generated = outputs[0][inputs["input_ids"].shape[1]:]
response = tokenizer.decode(generated, skip_special_tokens=False)

# Remove stop token and parse
response = response.split("<|im_end|>")[0].strip()
parsed = json.loads(response)
```

---

## Key Improvements

### 1. Exact Training Match ✅
- Training: `<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n`
- Inference: `<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n`
- ✓ Identical format

### 2. Clean JSON Output ✅
- Before: `{"intent": "search"}<|im_end|>` ❌
- After: `{"intent": "search"}` ✅
- ✓ `json.loads()` works

### 3. No System Prompt ✅
- Before: Added "You are Qwen..." ❌
- After: Only user message ✅
- ✓ Matches training data

### 4. Token Handling ✅
- Decode only generated tokens (not prompt)
- Remove `<|im_end|>` cleanly
- No `skip_special_tokens` issues

---

## Testing

### Test Script: test_chatml_inference.py

**Usage:**
```bash
# Terminal 1
python3 local_model_server.py

# Terminal 2
python3 test_chatml_inference.py
```

**Tests:**
1. ✅ ChatML format is used (not apply_chat_template)
2. ✅ Raw response is valid JSON
3. ✅ No `<|im_end|>` tokens in output
4. ✅ Structured data is correct

**Test queries:**
- "Horse riding boots for kids below 3000"
- "running shoes under 5000"
- "I want to start playing football"

---

## Expected Response

### Request:
```bash
curl -X POST http://localhost:8001/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "Horse riding boots for kids below 3000"}'
```

### Response:
```json
{
  "intent": "search",
  "search_request": {
    "sport": "Horse Riding",
    "category": "Riding Boots",
    "keywords": ["kids", "boots"],
    "price_limit": 3000,
    "experience_level": null
  },
  "raw_response": "{\"intent\": \"search\", \"search_request\": {...}}",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps"
}
```

**Key points:**
- ✅ `raw_response` is valid JSON
- ✅ No `<|im_end|>` tokens
- ✅ Structured data is parsed correctly

---

## Verification Checklist

- [ ] Start server: `python3 local_model_server.py`
- [ ] No errors on startup
- [ ] Run tests: `python3 test_chatml_inference.py`
- [ ] All tests pass
- [ ] `raw_response` is valid JSON
- [ ] No `<|im_end|>` in responses
- [ ] Intent detection works
- [ ] Search request parsing works
- [ ] Task parsing works (multiple search requests)

---

## Comparison: Before vs After

| Aspect | Before (apply_chat_template) | After (ChatML) |
|--------|------------------------------|----------------|
| Format | System + User + Assistant | User + Assistant |
| System prompt | ✗ Added "You are Qwen..." | ✓ None |
| Training match | ✗ Different format | ✓ Exact match |
| JSON output | ✗ `{...}<|im_end|>` | ✓ `{...}` |
| json.loads() | ✗ Fails | ✓ Works |
| Token handling | ✗ Complex extraction | ✓ Clean decode |

---

## Files Modified

- ✅ `local_model_server.py` - Updated `/generate` and `/parse-query` endpoints
- ✅ `test_chatml_inference.py` - New comprehensive test script

---

## No Changes Needed

- ✅ `test_local_model.py` - Already tests `/parse-query` correctly
- ✅ `backend/local_model_client.py` - Client code unchanged
- ✅ `backend/hf_planner.py` - Uses client, no changes needed

---

## Quick Test

### Terminal 1:
```bash
python3 local_model_server.py
```

Wait for:
```
✅ Server ready for requests
```

### Terminal 2:
```bash
python3 test_chatml_inference.py
```

Expected:
```
✅ ALL TESTS PASSED (5/5)

ChatML format is working correctly!
  ✓ No apply_chat_template()
  ✓ Valid JSON output
  ✓ Clean responses (no extra tokens)
```

---

## Debug Commands

### Test parse-query manually:
```bash
curl -X POST http://localhost:8001/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'
```

### Check raw response:
```bash
curl -X POST http://localhost:8001/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' | jq '.raw_response'
```

Should output valid JSON string (no `<|im_end|>`).

---

## Success Criteria

✅ Server starts without errors  
✅ All tests pass  
✅ `raw_response` contains valid JSON  
✅ No `<|im_end|>` tokens in responses  
✅ Intent detection works correctly  
✅ Search request parsing works  
✅ Task parsing works (multiple requests)  

---

**Last Updated:** June 18, 2026  
**Status:** ChatML format implemented ✅  
**Next:** Run `python3 test_chatml_inference.py`
