#!/usr/bin/env python3
"""
Test script to reproduce and diagnose the duplicate /parse-query issue.

This script will:
1. Send a single task query: "I want to start cycling"
2. Monitor the logs for duplicate /parse-query calls
3. Help identify the source of repeated executions
"""
import requests
import time
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
API_KEY = os.getenv("API_KEY", "decathlon_smart_search_2024_secure_key_abc123xyz")

def test_task_query():
    """Test a task query that searches for multiple items (helmet, gloves, bottle)."""
    
    query = "I want to start cycling"
    
    print("=" * 80)
    print("DUPLICATE /parse-query TEST")
    print("=" * 80)
    print(f"Query: {query}")
    print("\nExpected behavior:")
    print("  1. Single /parse-query call")
    print("  2. TaskTool searches for: helmet, gloves, bottle")
    print("  3. Each search calls /embed (for semantic search)")
    print("  4. Each search may call /validate-products")
    print("  5. REQUEST COMPLETE")
    print("\n❌ WRONG behavior (current bug):")
    print("  1. /parse-query")
    print("  2. Searches complete")
    print("  3. /parse-query AGAIN (duplicate!)")
    print("  4. Repeat...")
    print()
    print("Watch the backend logs closely for [REQUEST <id>] markers.")
    print("If you see two different REQUEST IDs, it means TWO separate HTTP requests.")
    print("=" * 80)
    print()
    
    input("Press Enter to send the request...")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Api-Key": API_KEY
        }
        
        payload = {"query": query}
        
        print(f"\n🚀 Sending POST request to {BACKEND_URL}/api/v1/query")
        print(f"   Payload: {payload}")
        print()
        
        start_time = time.time()
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query",
            json=payload,
            headers=headers,
            timeout=120
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Response received in {elapsed:.2f}s")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Result:")
            print(f"   Activity: {data.get('activity')}")
            print(f"   Items: {len(data.get('items', []))}")
            
            for item in data.get('items', []):
                print(f"     - {item['name']}: {len(item.get('products', []))} products")
        else:
            print(f"\n❌ Error response:")
            print(response.text)
            
    except requests.exceptions.Timeout:
        print("\n⏱️  Request timed out after 120 seconds")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("CHECK THE BACKEND LOGS ABOVE")
    print("=" * 80)
    print("\nLook for:")
    print("  [REQUEST abc123] NEW REQUEST    <- First request")
    print("  [REQUEST abc123] Calling /parse-query")
    print("  [REQUEST abc123] TaskTool completed")
    print("  [REQUEST abc123] ✅ REQUEST COMPLETE")
    print()
    print("If you see:")
    print("  [REQUEST xyz456] NEW REQUEST    <- Second request with DIFFERENT ID")
    print("Then a NEW HTTP request arrived (not a backend loop).")
    print()
    print("If you see:")
    print("  [REQUEST abc123] Calling /parse-query  <- SECOND call with SAME ID")
    print("Then the backend is calling /parse-query twice (backend bug).")
    print("=" * 80)


if __name__ == "__main__":
    test_task_query()
