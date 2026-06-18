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

BACKEND_URL = "http://localhost:5000"
API_KEY = "test_api_key_123"

def test_smart_search(query: str):
    """Test smart search and check for duplicates."""
    print("\n" + "=" * 80)
    print(f"TEST: {query}")
    print("=" * 80)
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/shopping/smart-search",
            json={"query": query},
            headers={"X-API-Key": API_KEY},
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            print(f"   Error: {response.text}")
            return False
        
        data = response.json()
        
        # Display response structure
        print(f"\n✓ Status: {data.get('status')}")
        print(f"✓ Intent: {data.get('intent')}")
        
        # Check parsed_query
        parsed_query = data.get('parsed_query', {})
        print(f"\n📋 Parsed Query:")
        print(f"   Intent: {parsed_query.get('intent')}")
        
        if 'search_request' in parsed_query:
            sr = parsed_query['search_request']
            print(f"   search_request:")
            print(f"     Sport: {sr.get('sport')}")
            print(f"     Category: {sr.get('category')}")
        
        if 'search_requests' in parsed_query:
            srs = parsed_query['search_requests']
            print(f"   search_requests ({len(srs)} items):")
            for i, sr in enumerate(srs, 1):
                print(f"     {i}. Sport: {sr.get('sport')}, Category: {sr.get('category')}")
        
        # Check recommendations
        recommendations = data.get('recommendations')
        print(f"\n💡 Recommendations:")
        print(f"   Type: {type(recommendations)}")
        
        if isinstance(recommendations, str):
            print(f"   Content: {recommendations[:200]}...")
        elif isinstance(recommendations, dict):
            print(f"   Structure: {json.dumps(recommendations, indent=6)}")
            
            # Check for duplicates in recommendations
            if 'search_requests' in recommendations:
                srs = recommendations['search_requests']
                print(f"\n   ⚠️  WARNING: recommendations has search_requests!")
                print(f"   Count: {len(srs)}")
                
                # Check for duplicates
                seen = set()
                duplicates = []
                for sr in srs:
                    key = (sr.get('sport'), sr.get('category'))
                    if key in seen:
                        duplicates.append(key)
                    seen.add(key)
                
                if duplicates:
                    print(f"   ❌ DUPLICATES FOUND: {duplicates}")
                    return False
                else:
                    print(f"   ✓ No duplicates in recommendations")
        
        # Check products
        products = data.get('products', [])
        print(f"\n📦 Products: {len(products)} items")
        
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
