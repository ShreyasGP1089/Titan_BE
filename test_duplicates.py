#!/usr/bin/env python3
"""
Test script to identify and fix duplicate recommendations
"""
import sys
import requests
import json
from pathlib import Path

# Test queries
TEST_QUERIES = [
    "running shoes under 5000",
    "football boots",
    "I want to start running",
    "I want to start playing football"
]

# Add backend to path to load config
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "backend"))
try:
    from config import API_KEY
except ImportError:
    API_KEY = "decathlon_smart_search_2024_secure_key_abc123xyz"

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

def test_smart_search(query: str):
    """Test unified query endpoint and check for duplicate products or items."""
    print("\n" + "=" * 80)
    print(f"TEST: {query}")
    print("=" * 80)
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query",
            json={"query": query},
            headers={"Api-Key": API_KEY},
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            print(f"   Error: {response.text}")
            return False
        
        data = response.json()
        resp_type = data.get("type")
        print(f"\n✓ Response Type: {resp_type}")
        
        if resp_type == "search":
            products = data.get("products", [])
            print(f"📦 Products returned: {len(products)}")
            
            # Check for duplicate product IDs
            seen_ids = set()
            duplicates = []
            for p in products:
                pid = p.get("product_id")
                if pid in seen_ids:
                    duplicates.append(pid)
                seen_ids.add(pid)
                
            if duplicates:
                print(f"   ❌ DUPLICATE PRODUCTS FOUND: {duplicates}")
                return False
            else:
                print(f"   ✓ No duplicate products found")
                
        elif resp_type == "task":
            items = data.get("items", [])
            print(f"📋 Task Items returned: {len(items)}")
            
            # Check for duplicate item categories/names
            seen_items = set()
            item_duplicates = []
            for item in items:
                name = item.get("name")
                if name in seen_items:
                    item_duplicates.append(name)
                seen_items.add(name)
                
            # Check for duplicate product IDs in recommended products
            seen_pids = set()
            prod_duplicates = []
            for item in items:
                rec = item.get("recommended")
                if rec:
                    pid = rec.get("product_id")
                    if pid in seen_pids:
                        prod_duplicates.append((item.get("name"), pid))
                    seen_pids.add(pid)
                    
            failed = False
            if item_duplicates:
                print(f"   ❌ DUPLICATE TASK ITEMS FOUND: {item_duplicates}")
                failed = True
            else:
                print(f"   ✓ No duplicate task items found")
                
            if prod_duplicates:
                print(f"   ❌ DUPLICATE RECOMMENDED PRODUCTS FOUND ACROSS ITEMS: {prod_duplicates}")
                failed = True
            else:
                print(f"   ✓ No duplicate products recommended across items")
                
            if failed:
                return False
                
        else:
            print(f"⚠️ Unknown response type: {resp_type}")
            
        print(f"\n✅ TEST PASSED (no duplicates)")
        return True
        
    except requests.ConnectionError:
        print("\n❌ Cannot connect to backend")
        print(f"   URL: {BACKEND_URL}")
        print("   Is the backend running?")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("DUPLICATE RECOMMENDATIONS TEST")
    print("=" * 80)
    print(f"\nTesting backend at: {BACKEND_URL}")
    print(f"API Key: {API_KEY}")
    
    results = []
    
    for query in TEST_QUERIES:
        success = test_smart_search(query)
        results.append((query, success))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for query, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {query}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print("\n" + "=" * 80)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 80)
        print("\nNo duplicates found!")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 80)
        print("\nDuplicates detected - check logs above")
        return 1


if __name__ == "__main__":
    exit(main())
