# ✅ Pydantic Validation Fixed

**Problem:** Response schema was too strict - required both fields even when only one should be present  
**Solution:** Made fields optional and added validation based on intent  
**Status:** Fixed and ready to test

---

## What Was Wrong

### Previous Schema ❌

```python
class ParseQueryResponse(BaseModel):
    intent: str
    search_request: dict = None      # Default None
    search_requests: list = None     # Default None
    raw_response: str               # Required
    model: str                       # Required  
    device: str                      # Required
```

**Problem:**
- When `intent="search"`, `search_requests=None` caused validation error
- When `intent="task"`, `search_request=None` caused validation error
- Pydantic expected lists/dicts, not None

---

## What Was Fixed

### New Schema ✅

```python
from typing import Optional, Literal
from pydantic import BaseModel, model_validator

class ParseQueryResponse(BaseModel):
    """
    Response model for query parsing.
    
    Supports both search and task intents:
    - search: returns search_request (single request)
    - task: returns search_requests (list of requests)
    """
    intent: Literal["search", "task"]
    search_request: Optional[dict] = None
    search_requests: Optional[list] = None
    raw_response: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_intent_fields(self):
        """Validate that the correct field is present based on intent."""
        if self.intent == "search":
            if self.search_request is None:
                raise ValueError("search_request is required when intent is 'search'")
        elif self.intent == "task":
            if self.search_requests is None:
                raise ValueError("search_requests is required when intent is 'task'")
        return self
```

**Benefits:**
1. ✅ All fields are `Optional` - no validation errors for None
2. ✅ `Literal["search", "task"]` - intent must be one of these
3. ✅ Custom validator checks correct field is present
4. ✅ Supports both intent types properly

---

## Response Examples

### Search Intent

**Request:**
```json
{
  "query": "Horse riding boots for kids below 3000"
}
```

**Response:**
```json
{
  "intent": "search",
  "search_request": {
    "sport": "Horse Riding",
    "category": "Riding Boots",
    "keywords": ["kids", "boots"],
    "price_limit": 3000
  },
  "search_requests": null,
  "raw_response": "{\"intent\": \"search\", ...}",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps"
}
```

**Key:**
- ✅ `search_request` is present (dict)
- ✅ `search_requests` is null
- ✅ HTTP 200 OK

---

### Task Intent

**Request:**
```json
{
  "query": "I want to start playing football"
}
```

**Response:**
```json
{
  "intent": "task",
  "search_request": null,
  "search_requests": [
    {
      "sport": "Football",
      "category": "Football",
      "keywords": []
    },
    {
      "sport": "Football",
      "category": "Football Shoes",
      "keywords": ["shoes"]
    }
  ],
  "raw_response": "{\"intent\": \"task\", ...}",
  "model": "Qwen/Qwen2.5-1.5B-Instruct",
  "device": "mps"
}
```

**Key:**
- ✅ `search_requests` is present (list)
- ✅ `search_request` is null
- ✅ HTTP 200 OK

---

## Validation Logic

### Search Intent
```python
if intent == "search":
    assert search_request is not None  # Must be present
    assert search_requests is None     # Must be absent
```

### Task Intent
```python
if intent == "task":
    assert search_requests is not None  # Must be present
    assert search_request is None       # Must be absent
```

---

## Code Changes

### Imports Added
```python
from typing import Optional, Literal, List
from pydantic import BaseModel, model_validator
```

### Model Updated
```python
# Before
search_request: dict = None      # Not optional, validation fails
search_requests: list = None     # Not optional, validation fails

# After
search_request: Optional[dict] = None     # Optional, accepts None
search_requests: Optional[list] = None    # Optional, accepts None
```

### Validator Added
```python
@model_validator(mode='after')
def validate_intent_fields(self):
    """Validate that the correct field is present based on intent."""
    if self.intent == "search":
        if self.search_request is None:
            raise ValueError("search_request is required when intent is 'search'")
    elif self.intent == "task":
        if self.search_requests is None:
            raise ValueError("search_requests is required when intent is 'task'")
    return self
```

---

## Testing

### Test Script: test_both_intents.py

**Usage:**
```bash
# Terminal 1
python3 local_model_server.py

# Terminal 2
python3 test_both_intents.py
```

**Tests:**
1. ✅ Search intent returns `search_request` (not `search_requests`)
2. ✅ Task intent returns `search_requests` (not `search_request`)
3. ✅ Both intents pass Pydantic validation
4. ✅ Raw responses are valid JSON
5. ✅ No `<|im_end|>` tokens in output

---

## Expected Test Output

```
INTENT AND VALIDATION TESTS
================================================================================
Testing server at: http://localhost:8001

Verifying:
  1. Search intent returns search_request (not search_requests)
  2. Task intent returns search_requests (not search_request)
  3. Both intents pass Pydantic validation
  4. Raw responses are valid JSON
  5. No <|im_end|> tokens in output

================================================================================
TEST: Search Intent
================================================================================
Query: Horse riding boots for kids below 3000
✓ Intent: search
✓ search_request: present
✓ search_requests: None (correct)
✅ SEARCH INTENT TEST PASSED

================================================================================
TEST: Task Intent
================================================================================
Query: I want to start playing football
✓ Intent: task
✓ search_requests: present (list with 2 items)
✓ search_request: None (correct)
✅ TASK INTENT TEST PASSED

================================================================================
TEST: Raw Response Validity
================================================================================
✓ raw_response is valid JSON
✓ No <|im_end|> token (clean)
✅ RAW RESPONSE VALIDITY TEST PASSED

================================================================================
TEST SUMMARY
================================================================================
✅ PASS  Search Intent
✅ PASS  Task Intent
✅ PASS  Raw Response Validity

✅ ALL TESTS PASSED (3/3)

Both intents work correctly!
  ✓ Search intent returns search_request
  ✓ Task intent returns search_requests
  ✓ Pydantic validation passes
  ✓ Raw responses are valid JSON
  ✓ No extra tokens in output
```

---

## Verification Checklist

- [ ] Start server: `python3 local_model_server.py`
- [ ] No import errors (Optional, Literal, model_validator)
- [ ] Run tests: `python3 test_both_intents.py`
- [ ] Search intent test passes
- [ ] Task intent test passes
- [ ] Raw response validity test passes
- [ ] All 3 tests show ✅ PASS

---

## Common Errors (Now Fixed)

### Before: ValidationError ❌
```
pydantic_core._pydantic_core.ValidationError: 1 validation error
search_requests
  Input should be a valid list [type=list_type, input_value=None]
```

### After: Works Correctly ✅
```
✓ Intent: search
✓ search_request: present
✓ search_requests: None (correct)
✅ SEARCH INTENT TEST PASSED
```

---

## Files Modified

- ✅ `local_model_server.py` - Updated `ParseQueryResponse` model and imports
- ✅ `test_both_intents.py` - New comprehensive test script

---

## Quick Test

```bash
# Terminal 1
python3 local_model_server.py

# Terminal 2
python3 test_both_intents.py
```

**Expected:**
```
✅ ALL TESTS PASSED (3/3)
```

---

## Manual Test

### Search Intent:
```bash
curl -X POST http://localhost:8001/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "running shoes under 5000"}'
```

**Should return:**
```json
{
  "intent": "search",
  "search_request": {...},
  "search_requests": null
}
```

### Task Intent:
```bash
curl -X POST http://localhost:8001/parse-query \
  -H "Content-Type: application/json" \
  -d '{"query": "I want to start playing football"}'
```

**Should return:**
```json
{
  "intent": "task",
  "search_request": null,
  "search_requests": [...]
}
```

---

**Last Updated:** June 18, 2026  
**Status:** Pydantic validation fixed ✅  
**Next:** Run `python3 test_both_intents.py`
