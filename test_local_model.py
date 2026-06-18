"""
Test script for local model server

Tests the local model server running on Mac.

Usage:
    python3 test_local_model.py
"""
import sys
import requests
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from local_model_client import LocalModelClient

# Configuration
LOCAL_URL = "http://localhost:8001"

def test_health():
    """Test health endpoint."""
    print("\n" + "=" * 80)
    print("TEST 1: Health Check")
    print("=" * 80)
    
    try:
        response = requests.get(f"{LOCAL_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Server is healthy")
            print(f"   Model: {data.get('model')}")
            print(f"   Device: {data.get('device')}")
            print(f"   Adapter loaded: {data.get('adapter_loaded')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.ConnectionError:
        print("❌ Cannot connect to local server")
        print(f"   URL: {LOCAL_URL}")
        print("   Is the server running?")
        print("   Start with: python3 local_model_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_generate_direct():
    """Test generation endpoint directly with requests."""
    print("\n" + "=" * 80)
    print("TEST 2: Direct HTTP Generation")
    print("=" * 80)
    
    try:
        prompt = """You are a JSON parser for shopping queries. You MUST respond with ONLY valid JSON, no other text.

Query: running shoes under 5000

Output format:
{"intent": "search", "search_request": {"sport": "Running", "category": "Running Shoes", "keywords": ["shoes"], "price_limit": 5000}}

Now parse this query:"""
        
        payload = {
            "prompt": prompt,
            "max_new_tokens": 256,
            "temperature": 0.0,
            "do_sample": False
        }
        
        print(f"📤 Sending request...")
        print(f"   Prompt length: {len(prompt)} chars")
        
        response = requests.post(
            f"{LOCAL_URL}/generate",
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Generation successful")
            print(f"   Model: {data.get('model')}")
            print(f"   Device: {data.get('device')}")
            print(f"   Tokens: {data.get('tokens_generated')}")
            print(f"\n   Response:")
            print(f"   {data.get('response')}")
            return True
        else:
            print(f"❌ Generation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.Timeout:
        print("❌ Request timeout (120s)")
        print("   Model might be slow or prompt too long")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_client():
    """Test using LocalModelClient."""
    print("\n" + "=" * 80)
    print("TEST 3: LocalModelClient")
    print("=" * 80)
    
    try:
        client = LocalModelClient(base_url=LOCAL_URL, timeout=120)
        
        # Health check
        print("\n3a. Health check via client:")
        health = client.health_check()
        print(f"✓ {health}")
        
        # Generate
        print("\n3b. Generate via client:")
        prompt = """You are a JSON parser for shopping queries. You MUST respond with ONLY valid JSON, no other text.

Query: football cleats under 3000

Output format:
{"intent": "search", "search_request": {"sport": "Football", "category": "Football Shoes", "keywords": ["cleats"], "price_limit": 3000}}

Now parse this query:"""
        
        response = client.generate(prompt, max_new_tokens=256)
        print("✓ Generation successful")
        print(f"\n   Response:")
        print(f"   {response}")
        
        # Try to parse as JSON
        print("\n3c. Validate JSON:")
        try:
            parsed = json.loads(response)
            print(f"✓ Valid JSON")
            print(f"   Intent: {parsed.get('intent')}")
            print(f"   Sport: {parsed.get('search_request', {}).get('sport')}")
        except json.JSONDecodeError as e:
            print(f"⚠️  Not valid JSON: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_parse_query():
    """Test the new parse-query endpoint."""
    print("\n" + "=" * 80)
    print("TEST 4: Parse Query Endpoint (Returns JSON directly)")
    print("=" * 80)
    
    try:
        payload = {"query": "running shoes under 5000"}
        
        print(f"📤 Sending request...")
        print(f"   Query: {payload['query']}")
        
        response = requests.post(
            f"{LOCAL_URL}/parse-query",
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Parse successful")
            print(f"   Intent: {data.get('intent')}")
            print(f"   Model: {data.get('model')}")
            print(f"   Device: {data.get('device')}")
            
            # Check structure
            if data.get('intent') == 'search' and data.get('search_request'):
                print(f"\n   Search Request:")
                print(f"   {json.dumps(data['search_request'], indent=6)}")
            elif data.get('intent') == 'task' and data.get('search_requests'):
                print(f"\n   Search Requests:")
                print(f"   {json.dumps(data['search_requests'], indent=6)}")
            
            return True
        else:
            print(f"❌ Parse failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.Timeout:
        print("❌ Request timeout (120s)")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_client_parse_query():
    """Test parse_query method in LocalModelClient."""
    print("\n" + "=" * 80)
    print("TEST 5: LocalModelClient.parse_query()")
    print("=" * 80)
    
    try:
        client = LocalModelClient(base_url=LOCAL_URL, timeout=120)
        
        query = "I want to start playing football"
        print(f"\n   Query: {query}")
        
        parsed = client.parse_query(query)
        
        print("✓ Parse successful")
        print(f"   Intent: {parsed.get('intent')}")
        print(f"\n   Full response:")
        print(f"   {json.dumps(parsed, indent=6)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("LOCAL MODEL SERVER TESTS")
    print("=" * 80)
    print(f"\nTesting server at: {LOCAL_URL}")
    print("\nMake sure the server is running:")
    print("   python3 local_model_server.py")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    
    if results[0][1]:  # Only continue if health check passed
        results.append(("Direct HTTP", test_generate_direct()))
        results.append(("Client", test_client()))
        results.append(("Parse Query Endpoint", test_parse_query()))
        results.append(("Client Parse Query", test_client_parse_query()))
    else:
        print("\n⚠️  Skipping generation tests (server not healthy)")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status:8} {name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nLocal model server is working correctly!")
        print("\nNext steps:")
        print("1. Expose with ngrok: ngrok http 8001")
        print("2. Set LOCAL_MODEL_URL in Render")
        print("3. Deploy backend to Render")
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        print("\nPlease fix the issues above before proceeding.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
