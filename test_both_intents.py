#!/usr/bin/env python3
"""
Test both search and task intents
Verifies that Pydantic validation works for both response types
"""
import requests
import json

LOCAL_URL = "http://localhost:8001"

def test_search_intent():
    """Test search intent (single search_request)."""
    print("\n" + "=" * 80)
    print("TEST: Search Intent")
    print("=" * 80)
    
    query = "Horse riding boots for kids below 3000"
    print(f"Query: {query}")
    
    try:
        response = requests.post(
            f"{LOCAL_URL}/parse-query",
            json={"query": query},
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            print(f"   Error: {response.text}")
            return False
        
        data = response.json()
        
        # Verify structure
        assert data["intent"] == "search", f"Expected intent='search', got '{data['intent']}'"
        assert data["search_request"] is not None, "search_request should not be None"
        assert data["search_requests"] is None, "search_requests should be None for search intent"
        
        print(f"✓ Intent: {data['intent']}")
        print(f"✓ search_request: present")
        print(f"✓ search_requests: None (correct)")
        
        sr = data["search_request"]
        print(f"\nSearch Request:")
        print(f"  Sport: {sr.get('sport')}")
        print(f"  Category: {sr.get('category')}")
        print(f"  Keywords: {sr.get('keywords')}")
        print(f"  Price limit: {sr.get('price_limit')}")
        
        print(f"\n✅ SEARCH INTENT TEST PASSED")
        return True
        
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_task_intent():
    """Test task intent (multiple search_requests)."""
    print("\n" + "=" * 80)
    print("TEST: Task Intent")
    print("=" * 80)
    
    query = "I want to start playing football"
    print(f"Query: {query}")
    
    try:
        response = requests.post(
            f"{LOCAL_URL}/parse-query",
            json={"query": query},
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            print(f"   Error: {response.text}")
            return False
        
        data = response.json()
        
        # Verify structure
        assert data["intent"] == "task", f"Expected intent='task', got '{data['intent']}'"
        assert data["search_requests"] is not None, "search_requests should not be None"
        assert data["search_request"] is None, "search_request should be None for task intent"
        assert isinstance(data["search_requests"], list), "search_requests should be a list"
        assert len(data["search_requests"]) > 0, "search_requests should not be empty"
        
        print(f"✓ Intent: {data['intent']}")
        print(f"✓ search_requests: present (list with {len(data['search_requests'])} items)")
        print(f"✓ search_request: None (correct)")
        
        print(f"\nSearch Requests:")
        for i, sr in enumerate(data["search_requests"], 1):
            print(f"\n  {i}. {sr.get('category', 'Unknown')}")
            print(f"     Sport: {sr.get('sport')}")
            print(f"     Keywords: {sr.get('keywords')}")
        
        print(f"\n✅ TASK INTENT TEST PASSED")
        return True
        
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_raw_response_validity():
    """Test that raw_response is valid JSON."""
    print("\n" + "=" * 80)
    print("TEST: Raw Response Validity")
    print("=" * 80)
    
    tests = [
        ("running shoes under 5000", "search"),
        ("I want to start running", "task"),
    ]
    
    all_passed = True
    
    for query, expected_intent in tests:
        print(f"\nQuery: {query}")
        
        try:
            response = requests.post(
                f"{LOCAL_URL}/parse-query",
                json={"query": query},
                timeout=120
            )
            
            if response.status_code != 200:
                print(f"  ❌ HTTP {response.status_code}")
                all_passed = False
                continue
            
            data = response.json()
            raw = data.get("raw_response")
            
            if not raw:
                print(f"  ❌ No raw_response field")
                all_passed = False
                continue
            
            # Try to parse raw response
            try:
                parsed = json.loads(raw)
                print(f"  ✓ raw_response is valid JSON")
                print(f"    Intent: {parsed.get('intent')}")
                
                # Check for <|im_end|> token
                if "<|im_end|>" in raw:
                    print(f"  ❌ raw_response contains <|im_end|> token!")
                    all_passed = False
                else:
                    print(f"  ✓ No <|im_end|> token (clean)")
                
            except json.JSONDecodeError as e:
                print(f"  ❌ raw_response is NOT valid JSON: {e}")
                print(f"     Content: {raw[:100]}...")
                all_passed = False
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            all_passed = False
    
    if all_passed:
        print(f"\n✅ RAW RESPONSE VALIDITY TEST PASSED")
    else:
        print(f"\n❌ RAW RESPONSE VALIDITY TEST FAILED")
    
    return all_passed


def main():
    """Run all tests."""
    print("=" * 80)
    print("INTENT AND VALIDATION TESTS")
    print("=" * 80)
    print(f"\nTesting server at: {LOCAL_URL}")
    print("\nVerifying:")
    print("  1. Search intent returns search_request (not search_requests)")
    print("  2. Task intent returns search_requests (not search_request)")
    print("  3. Both intents pass Pydantic validation")
    print("  4. Raw responses are valid JSON")
    print("  5. No <|im_end|> tokens in output")
    
    results = []
    
    # Run tests
    results.append(("Search Intent", test_search_intent()))
    results.append(("Task Intent", test_task_intent()))
    results.append(("Raw Response Validity", test_raw_response_validity()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print("\n" + "=" * 80)
    if passed_count == total_count:
        print(f"✅ ALL TESTS PASSED ({passed_count}/{total_count})")
        print("=" * 80)
        print("\nBoth intents work correctly!")
        print("  ✓ Search intent returns search_request")
        print("  ✓ Task intent returns search_requests")
        print("  ✓ Pydantic validation passes")
        print("  ✓ Raw responses are valid JSON")
        print("  ✓ No extra tokens in output")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed_count}/{total_count} passed)")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit(main())
