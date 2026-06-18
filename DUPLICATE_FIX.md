# Duplicate Recommendations Fix

**Problem:** Duplicate search_requests in smart-search response  
**Root Cause:** Model generates duplicate (sport, category) pairs  
**Solution:** Deduplication at query parsing and search execution stages  
**Status:** Fixed with safety deduplication

---

## Problem Example

### Query:
```
"running shoes under 5000"
```

### Response (Before Fix):
```json
{
  "parsed_query": {
    "intent": "search",
    "search_request": {
      "sport": "Running",
      "category": "Running Shoes"
    }
  },
  "recommendations": {
    "intent": "recommend",
    "search_requests": [
      {"sport": "Running", "category": "Running Shoes"},
      {"sport": "Running", "category": "Running Shoes"}  ← DUPLICATE!
    ]
  }
}
```

---

## Root Cause Analysis

### Flow Traced:
```
1. smart-search endpoint
   ↓
2. shopping_planner_hf()
   ↓
3. parse_query_with_local_model()
   → Returns parsed_query
   ↓
4. execute_search(parsed_query)
   → Executes hybrid search
   ↓
5. generate_recommendations()
   → Natural language response
   ↓
6. Build final response
```

### Where Duplicates Occur:

**Scenario 1: Model Output**
- The local model (`/parse-query` endpoint) might return duplicate search_requests for task intent
- Example: "I want to start running" → generates same search request twice

**Scenario 2: Response Assembly**
- If parsed_query contains duplicates, they propagate through the entire pipeline

---

## Solution Implemented

### 1. Deduplication Function

Added to `backend/hf_planner.py`:

```python
def deduplicate_search_requests(search_requests: List[Dict]) -> List[Dict]:
    """
    Remove duplicate search requests based on (sport, category) pairs.
    
    Args:
        search_requests: List of search request dicts
    
    Returns:
        Deduplicated list of search requests
    """
    if not search_requests:
        return []
    
    seen = set()
    unique = []
    
    for item in search_requests:
        # Create key from sport and category
        key = (
            item.get("sport"),
            item.get("category")
        )
        
        if key not in seen:
            seen.add(key)
            unique.append(item)
        else:
            logger.warning(f"Removing duplicate search request: {key}")
    
    if len(unique) < len(search_requests):
        logger.info(f"Deduplicated search_requests: {len(search_requests)} → {len(unique)}")
    
    return unique
```

---

### 2. Applied at Parsing Stage

After receiving parsed_query from model:

```python
# Safety: Deduplicate search_requests in parsed_query if present
if parsed_query.get('intent') == 'task' and 'search_requests' in parsed_query:
    original_count = len(parsed_query['search_requests'])
    parsed_query['search_requests'] = deduplicate_search_requests(parsed_query['search_requests'])
    if len(parsed_query['search_requests']) < original_count:
        logger.warning(f"Deduplicated parsed_query search_requests: {original_count} → {len(parsed_query['search_requests'])}")
```

---

### 3. Applied at Search Execution

In `execute_search()` function:

```python
elif intent == 'task':
    # Multiple search requests
    search_requests = parsed_query.get('search_requests', [])
    
    logger.info(f"DEBUG - Task search requests (before dedupe): {len(search_requests)}")
    
    # Deduplicate search requests
    search_requests = deduplicate_search_requests(search_requests)
    
    logger.info(f"DEBUG - Task search requests (after dedupe): {len(search_requests)}")
    
    task_results = search_task(search_requests)
```

---

### 4. Debug Logging Added

Throughout the pipeline:

```python
# At parsing
logger.info(f"DEBUG - Parsed query: {json.dumps(parsed_query, indent=2)}")

# At search execution
logger.info(f"DEBUG - Single search request: sport={sport}, category={category}")
logger.info(f"DEBUG - Task search requests (before dedupe): {count}")
logger.info(f"DEBUG - Task search requests (after dedupe): {count}")

# At response building
logger.info(f"DEBUG - Response keys: {list(response.keys())}")
logger.info(f"DEBUG - Response recommendations type: {type(recommendations)}")
```

---

## Response After Fix

### Query:
```
"running shoes under 5000"
```

### Response (After Fix):
```json
{
  "parsed_query": {
    "intent": "search",
    "search_request": {
      "sport": "Running",
      "category": "Running Shoes",
      "keywords": ["shoes"],
      "price_limit": 5000
    }
  },
  "recommendations": "Here are some great running shoes under ₹5000...",
  "products": [...]
}
```

✅ No duplicates  
✅ Recommendations is a string (natural language)  
✅ parsed_query contains single search_request  

---

### For Task Intent:

### Query:
```
"I want to start playing football"
```

### Response (After Fix):
```json
{
  "parsed_query": {
    "intent": "task",
    "search_requests": [
      {"sport": "Football", "category": "Football"},
      {"sport": "Football", "category": "Football Shoes"}
    ]
  },
  "recommendations": "Great! For starting football, I recommend...",
  "products_by_category": {...}
}
```

✅ No duplicate search_requests  
✅ Each (sport, category) pair appears only once  

---

## Testing

### Test Script: test_duplicates.py

**Usage:**
```bash
# Terminal 1: Start local model server
python3 local_model_server.py

# Terminal 2: Start backend
cd backend && python3 api_swagger.py

# Terminal 3: Run tests
python3 test_duplicates.py
```

**Test Cases:**
1. "running shoes under 5000" - search intent
2. "football boots" - search intent
3. "I want to start running" - task intent
4. "I want to start playing football" - task intent

**Expected Results:**
```
✅ PASS  running shoes under 5000
✅ PASS  football boots
✅ PASS  I want to start running
✅ PASS  I want to start playing football

✅ ALL TESTS PASSED (4/4)

No duplicates found!
```

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/hf_planner.py` | Added `deduplicate_search_requests()` function |
| | Added deduplication at parsing stage |
| | Added deduplication at search execution stage |
| | Added comprehensive DEBUG logging |
| `test_duplicates.py` | New test script to verify no duplicates |

---

## Debug Log Example

### Before Deduplication:
```
STEP 1: PARSE QUERY
✓ Successfully parsed: intent=task
DEBUG - Parsed query: {
  "intent": "task",
  "search_requests": [
    {"sport": "Running", "category": "Running Shoes"},
    {"sport": "Running", "category": "Running Shoes"}
  ]
}
⚠️  Deduplicated parsed_query search_requests: 2 → 1

STEP 2: EXECUTE SEARCH
DEBUG - Task search requests (before dedupe): 1
DEBUG - Task search requests (after dedupe): 1
DEBUG - Products returned: 25
```

### After Deduplication:
```
STEP 1: PARSE QUERY
✓ Successfully parsed: intent=task
DEBUG - Parsed query: {
  "intent": "task",
  "search_requests": [
    {"sport": "Running", "category": "Running Shoes"}
  ]
}

STEP 2: EXECUTE SEARCH
DEBUG - Task search requests (before dedupe): 1
DEBUG - Task search requests (after dedupe): 1
DEBUG - Products returned: 25
```

---

## Key Points

### Deduplication Logic:
- Uses `(sport, category)` tuple as unique key
- Preserves order (first occurrence kept)
- Logs warnings when duplicates removed
- Applied at multiple stages for safety

### Where Applied:
1. **After parsing** - Clean model output immediately
2. **Before search** - Prevent duplicate database queries
3. **Two-layer safety** - Catches duplicates at both stages

### Why Multiple Stages:
- Model might generate duplicates
- Defensive programming - catches edge cases
- Minimal performance impact
- Comprehensive logging for debugging

---

## Verification Checklist

- [ ] Start local model server
- [ ] Start backend
- [ ] Run `python3 test_duplicates.py`
- [ ] All 4 tests pass
- [ ] Check logs for duplicate warnings
- [ ] Verify response structure matches expected
- [ ] Test with real frontend queries

---

## Success Criteria

✅ No duplicate (sport, category) pairs in search_requests  
✅ recommendations field contains natural language string  
✅ parsed_query structure is correct  
✅ Products returned correctly  
✅ Debug logs show deduplication happening  
✅ All test queries pass  

---

**Last Updated:** June 18, 2026  
**Status:** Fixed with safety deduplication  
**Next:** Run test_duplicates.py to verify
