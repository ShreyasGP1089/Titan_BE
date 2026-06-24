#!/usr/bin/env python3
import sys
import os
import requests

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from tools.compare_tool import CompareTool
from models.schemas import CompareArguments

# Define expected outputs to verify correctness
TEST_CASES = [
    {
        "query": "Compare Gallon Water Bottle 1.3L and Gallon Water Bottle 2.2L",
        "inputs": ["Gallon Water Bottle 1.3L", "Gallon Water Bottle 2.2L"],
        "expected_ids": ["8800515", "8800516"]
    },
    {
        "query": "Compare Football Size 5 Germany 2026 and Football Size 5 Brazil 2026",
        "inputs": ["Football Size 5 Germany 2026", "Football Size 5 Brazil 2026"],
        "expected_ids": ["8949587", "8949670"]
    },
    {
        "query": "Compare Football Ball Size 5 First Kick and Size 5 Machine-Stitched Football Training Ball",
        "inputs": ["Football Ball Size 5 First Kick", "Size 5 Machine-Stitched Football Training Ball"],
        "expected_ids": ["8968895", "8789910"]
    },
    {
        "query": "Compare Cycle Water Bottle 650ml Black and Hydrapak Tempo Running Water Bottles",
        "inputs": ["Cycle Water Bottle 650ml Black", "Hydrapak Tempo Running Water Bottles"],
        "expected_ids": ["8518737", "1000005516"]
    },
    {
        "query": "Compare G Elite Bottle FLY 550ML ARKEA B&B HOTELS and Go 2-Stage Water Filter Bottle - 650 ml with Activated Carbon Filter, Clear",
        "inputs": ["G Elite Bottle FLY 550ML ARKEA B&B HOTELS", "Go 2-Stage Water Filter Bottle - 650 ml with Activated Carbon Filter, Clear"],
        "expected_ids": ["1000001169", "1000001180"]
    }
]

def run_compare_tool_tests():
    print("=" * 80)
    print("RUNNING COMPARE_TOOL DIRECT TESTS")
    print("=" * 80)
    
    tool = CompareTool()
    passed = 0
    failed = 0
    
    for i, tc in enumerate(TEST_CASES, 1):
        print(f"Test Case {i}: {tc['inputs']}")
        try:
            res = tool.execute(CompareArguments(products=tc["inputs"]))
            resolved_ids = [p.product_id for p in res.products]
            print(f"  Expected IDs: {tc['expected_ids']}")
            print(f"  Resolved IDs: {resolved_ids}")
            
            # Check if resolved matches expected
            if resolved_ids == tc["expected_ids"]:
                print("  ✅ PASS")
                passed += 1
            else:
                print("  ❌ FAIL (Mismatched IDs)")
                failed += 1
        except Exception as e:
            print(f"  ❌ FAIL (Error: {e})")
            failed += 1
        print("-" * 80)
        
    print(f"CompareTool tests finished: {passed} passed, {failed} failed.")
    return failed == 0

def run_api_tests():
    print("=" * 80)
    print("RUNNING HTTP API INTEGRATION TESTS")
    print("=" * 80)
    
    api_url = "http://localhost:5000/api/v1/query"
    headers = {"Api-Key": "test_api_key"} # Use config.py's API key if auth is active
    
    passed = 0
    failed = 0
    
    for i, tc in enumerate(TEST_CASES, 1):
        print(f"API Test Case {i}: Query='{tc['query']}'")
        try:
            # First fetch API key from config if needed
            from config import API_KEY
            headers["Api-Key"] = API_KEY
            
            response = requests.post(api_url, json={"query": tc["query"]}, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"  ❌ FAIL: HTTP Status {response.status_code}")
                print(f"  Response: {response.text}")
                failed += 1
                continue
                
            data = response.json()
            products = data.get("products", [])
            resolved_ids = [p.get("product_id") for p in products]
            
            print(f"  Expected IDs: {tc['expected_ids']}")
            print(f"  Resolved IDs: {resolved_ids}")
            
            if resolved_ids == tc["expected_ids"]:
                print("  ✅ PASS")
                passed += 1
            else:
                print("  ❌ FAIL (Mismatched IDs)")
                failed += 1
        except Exception as e:
            print(f"  ❌ FAIL (Error: {e})")
            failed += 1
        print("-" * 80)
        
    print(f"API tests finished: {passed} passed, {failed} failed.")
    return failed == 0

def run_ambiguous_tests():
    print("=" * 80)
    print("RUNNING AMBIGUOUS / LOW CONFIDENCE RESOLUTION TESTS")
    print("=" * 80)
    
    tool = CompareTool()
    direct_ok = False
    api_ok = False
    
    # Ambiguous test case 1: Non-existent product name
    print("Ambiguous Test Case 1: ['xyzabcproduct', 'Gallon Water Bottle 1.3L']")
    try:
        tool.execute(CompareArguments(products=["xyzabcproduct", "Gallon Water Bottle 1.3L"]))
        print("  ❌ FAIL (Expected ValueError but completed successfully)")
    except ValueError as e:
        print(f"  ✅ PASS (Expected ValueError: {e})")
        direct_ok = True
    except Exception as e:
        print(f"  ❌ FAIL (Unexpected exception: {e})")
        
    print("-" * 80)
    
    # Ambiguous test case 2: API call for ambiguous product
    api_url = "http://localhost:5000/api/v1/query"
    try:
        from config import API_KEY
        headers = {"Api-Key": API_KEY}
        
        print("Ambiguous Test Case 2: Query='Compare xyzabcproduct and Gallon Water Bottle 1.3L'")
        response = requests.post(api_url, json={"query": "Compare xyzabcproduct and Gallon Water Bottle 1.3L"}, headers=headers, timeout=10)
        if response.status_code == 400:
            print(f"  ✅ PASS (Expected 400 Bad Request, response: {response.text})")
            api_ok = True
        else:
            print(f"  ❌ FAIL (Expected 400, got status {response.status_code}, response: {response.text})")
    except Exception as e:
        print(f"  ❌ FAIL (Error: {e})")
        
    print("-" * 80)
    return direct_ok and api_ok

def main():
    direct_ok = run_compare_tool_tests()
    api_ok = run_api_tests()
    ambig_ok = run_ambiguous_tests()
    
    if direct_ok and api_ok and ambig_ok:
        print("ALL TESTS PASSED SUCCESSFULLY! 🎉")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
