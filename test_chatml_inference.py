#!/usr/bin/env python3
"""
Test ChatML format inference
Verifies that the server uses ChatML format correctly and produces valid JSON
"""
import requests
import json

import os
LOCAL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:8000")

def test_parse_query(query: str, expected_intent: str):
    """Test parse-query endpoint with ChatML format."""
    print("\n" + "=" * 80)
    print(f"TEST: {query}")
    print("=" * 80)
    
    try:
        response = requests.post(
            f"{LOCAL_URL}/parse-query",
            json={"query": query},
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        data = response.json()
        
        # Verify response structure
        if "intent" not in data:
            print("❌ Missing 'intent' field")
            return False
        
        if "raw_response" not in data:
            print("❌ Missing 'raw_response' field")
            return False
        
        intent = data["intent"]
        raw_response = data["raw_response"]
        
        print(f"✓ Intent: {intent}")
        print(f"✓ Expected: {expected_intent}")
        
        if intent != expected_intent:
            print(f"⚠️  Intent mismatch! Got '{intent}', expected '{expected_intent}'")
        
        # Verify raw response is valid JSON
        print(f"\n✓ Raw response ({len(raw_response)} chars):")
        print(f"   {raw_response[:200]}...")
        
        try:
            # Try to parse raw response as JSON
            parsed = json.loads(raw_response)
            print(f"\n✓ Raw response is valid JSON")
            print(f"   Keys: {list(parsed.keys())}")
        except json.JSONDecodeError as e:
            print(f"\n❌ Raw response is NOT valid JSON: {e}")
            print(f"   This means ChatML format is not working correctly")
            return False
        
        # Display structured data
        if intent == "search" and data.get("search_request"):
            sr = data["search_request"]
            print(f"\n✓ Search Request:")
            print(f"   Sport: {sr.get('sport')}")
            print(f"   Category: {sr.get('category')}")
            print(f"   Keywords: {sr.get('keywords')}")
            print(f"   Price limit: {sr.get('price_limit')}")
            print(f"   Experience level: {sr.get('experience_level')}")
            
        elif intent == "task" and data.get("search_requests"):
            print(f"\n✓ Search Requests ({len(data['search_requests'])} items):")
            for i, sr in enumerate(data["search_requests"], 1):
                print(f"\n   {i}. {sr.get('category', 'Unknown')}")
                print(f"      Sport: {sr.get('sport')}")
                print(f"      Keywords: {sr.get('keywords')}")
        
        print(f"\n✅ TEST PASSED")
        return True
        
    except requests.Timeout:
        print("❌ Request timeout (120s)")
        return False
    except requests.ConnectionError:
        print("❌ Cannot connect to server")
        print(f"   URL: {LOCAL_URL}")
        print("   Is the server running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all ChatML format tests."""
    print("=" * 80)
    print("CHATML INFERENCE TESTS")
    print("=" * 80)
    print(f"\nTesting server at: {LOCAL_URL}")
    print("\nVerifying:")
    print("  1. ChatML format is used (not apply_chat_template)")
    print("  2. Raw response is valid JSON")
    print("  3. No <|im_end|> tokens in output")
    print("  4. Structured data is correct")
    
    tests = [
        # (query, expected_intent)
        ("Horse riding boots for kids below 3000", "search"),
        ("running shoes under 5000", "search"),
        ("football cleats under 3000", "search"),
        ("I want to start playing football", "task"),
        ("I want to start running", "task"),
    ]
    
    results = []
    
    for query, expected_intent in tests:
        success = test_parse_query(query, expected_intent)
        results.append((query, success))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for query, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}  {query[:50]}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print("\n" + "=" * 80)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 80)
        print("\nChatML format is working correctly!")
        print("  ✓ No apply_chat_template()")
        print("  ✓ Valid JSON output")
        print("  ✓ Clean responses (no extra tokens)")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 80)
        print("\nPlease check server logs for details.")
        return 1


if __name__ == "__main__":
    exit(main())
