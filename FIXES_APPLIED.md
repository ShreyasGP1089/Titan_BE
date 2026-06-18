# Fixes Applied to Split Architecture

## Issues Fixed

### ✅ Issue 1: LoRA Adapter Loading Made Required

**Problem:** LoRA adapter loading was optional, could fall back to base model

**Fix:** Made LoRA loading required with error if not found

**Before:**
```python
if adapter_path.exists():
    try:
        model = PeftModel.from_pretrained(model, adapter_path)
    except:
        logger.warning("Continuing with base model")
else:
    logger.warning("Using base model only")
```

**After:**
```python
if not adapter_path.exists():
    raise FileNotFoundError(f"LoRA adapter not found at {ADAPTER_PATH}")

model = PeftModel.from_pretrained(model, adapter_path)
logger.info("✓ LoRA adapter loaded successfully!")
```

**Impact:** Server will FAIL to start if adapter is missing, preventing base model usage

---

### ✅ Issue 2: Added Direct JSON Parsing Endpoint

**Problem:** `/generate` endpoint returned JSON as string, requiring double parsing

**Old Flow:**
```
Client → POST /generate
    ← {"response": "{\"intent\": \"search\", ...}"}  ← String!
Client → json.loads(response["response"])  ← Parse again
```

**New Flow:**
```
Client → POST /parse-query  
    ← {"intent": "search", "search_request": {...}}  ← Already parsed!
```

**Added to `local_model_server.py`:**
```python
@app.post("/parse-query", response_model=ParseQueryResponse)
async def parse_query(request: ParseQueryRequest):
    # Generate response
    response = model.generate(...)
    
    # Parse JSON internally
    parsed = json.loads(response)
    
    # Return structured response
    return ParseQueryResponse(
        intent=parsed["intent"],
        search_request=parsed.get("search_request"),
        search_requests=parsed.get("search_requests"),
        raw_response=response,
        model=BASE_MODEL,
        device=device
    )
```

**Added to `local_model_client.py`:**
```python
def parse_query(self, query: str) -> Dict:
    """Parse query and get structured JSON directly."""
    response = requests.post(
        f"{self.base_url}/parse-query",
        json={"query": query},
        timeout=self.timeout
    )
    
    result = response.json()
    
    # Return already-parsed structure
    return {
        "intent": result["intent"],
        "search_request": result.get("search_request"),
        "search_requests": result.get("search_requests")
    }
```

**Updated `hf_planner.py`:**
```python
def parse_query_with_local_model(user_query: str):
    client = get_client()
    
    # Call /parse-query endpoint - returns parsed JSON!
    parsed_query = client.parse_query(user_query)
    
    # No json.loads() needed!
    return parsed_query
```

---

## Summary of Changes

### `local_model_server.py`
1. ✅ Made LoRA adapter loading REQUIRED (fail if missing)
2. ✅ Added `/parse-query` endpoint
3. ✅ Added `ParseQueryRequest` and `ParseQueryResponse` models
4. ✅ Server does JSON parsing internally

### `backend/local_model_client.py`
1. ✅ Added `parse_query(query)` method
2. ✅ Returns structured dict, not string
3. ✅ No client-side JSON parsing needed

### `backend/hf_planner.py`
1. ✅ Updated `parse_query_with_local_model()` to use new endpoint
2. ✅ Removed JSON parsing logic (handled by server)
3. ✅ Removed `repair_json()` calls (not needed)

### `test_local_model.py`
1. ✅ Added `test_parse_query()` - tests new endpoint
2. ✅ Added `test_client_parse_query()` - tests client method
3. ✅ Now 5 tests total (was 3)

---

## Verification

### Test the Server

```bash
# 1. Start server
python3 local_model_server.py

# Expected output:
# ✓ LoRA adapter loaded successfully!
# ✅ Server ready for requests
```

**If adapter missing:**
```
❌ LoRA adapter not found at training/outputs/qwen25_1_5b_lora_hf
   Train the adapter first: python3 training/train_hf.py
```

### Test the Endpoints

```bash
# 2. Run tests
python3 test_local_model.py

# Expected:
# ✓ PASS Health Check
# ✓ PASS Direct HTTP
# ✓ PASS Client
# ✓ PASS Parse Query Endpoint  ← NEW
# ✓ PASS Client Parse Query     ← NEW
# ✅ ALL TESTS PASSED
```

### Test Parsing

```bash
# 3. Test parse-query endpoint directly
curl -X POST http://localhost:8001/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'

# Response (already parsed JSON):
{
  "intent": "search",
  "search_request": {
    "sport": "Running",
    "category": "Running Shoes",
    "keywords": ["shoes"],
    "price_limit": 5000
  },
  "raw_response": "{...}",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps"
}
```

---

## Benefits

### ✅ Guaranteed Fine-Tuned Model
- Server will fail fast if adapter missing
- No silent fallback to base model
- Better quality responses guaranteed

### ✅ Cleaner API Contract
- Frontend gets structured JSON, not strings
- No double parsing needed
- Less error-prone
- Faster (no string→JSON conversion on client)

### ✅ Better Error Handling
- JSON parsing errors caught on server
- Client gets clean error messages
- No need for `repair_json()` hacks

### ✅ Easier Debugging
- Server logs show parse success/failure
- Client just receives structured data
- Clear separation of concerns

---

## Migration Notes

### Old Code (Still Works)
```python
# Old generate endpoint still exists
response = client.generate(prompt)
parsed = json.loads(response)
```

### New Code (Recommended)
```python
# New parse_query method
parsed = client.parse_query(user_query)
# Already a dict!
```

### Backend Changes
- `hf_planner.py` already updated to use new method
- `api_swagger.py` unchanged (calls hf_planner)
- No frontend changes needed

---

## Checklist

### Before Starting Server
- [ ] LoRA adapter exists: `training/outputs/qwen25_1_5b_lora_hf/`
- [ ] Dependencies installed: `pip install -r requirements_local_server.txt`

### Server Startup
- [ ] Server starts without errors
- [ ] Logs show "LoRA adapter loaded successfully!"
- [ ] Health check returns 200

### Testing
- [ ] `python3 test_local_model.py` passes all 5 tests
- [ ] Parse query endpoint works
- [ ] Client parse_query method works

### Integration
- [ ] Backend can call parse_query
- [ ] No JSON parsing errors
- [ ] Responses match expected format

---

**Status: FIXES COMPLETE** ✅

The local model server now:
1. **Requires** LoRA adapter (no silent fallback)
2. **Returns** structured JSON (no double parsing)
3. **Works** with existing backend code

Ready to test! Run `python3 local_model_server.py` 🚀
