#!/usr/bin/env python3
"""
Test script for "Find waterproof backpack" query instrumentation.

This script sends the query and monitors the complete retrieval pipeline
to identify where valid backpacks are lost.
"""
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
API_KEY = os.getenv("API_KEY", "decathlon_smart_search_2024_secure_key_abc123xyz")

def test_waterproof_backpack():
    """Test the waterproof backpack query and track the pipeline."""
    
    query = "Find waterproof backpack"
    
    print("=" * 80)
    print("INSTRUMENTED RETRIEVAL PIPELINE TEST")
    print("=" * 80)
    print(f"Query: {query}")
    print()
    print("Expected pipeline stages:")
    print("  1. Parser: Extract intent, keywords, filters")
    print("  2. SQL Retrieval: Progressive relaxation stages")
    print("     - Stage 1: All keywords (AND) + filters")
    print("     - Stage 1b: All keywords (AND) + drop category")
    print("     - Stage 2a: Core keywords (AND)")
    print("     - Stage 2c: All keywords (OR)")
    print("     - Stage 3: No keywords (structured only)")
    print("  3. Semantic Ranking: Score candidates with embeddings")
    print("  4. LLM Validation: Filter by RELEVANT/RELATED/NOT_RELEVANT")
    print("  5. Final Results")
    print()
    print("=" * 80)
    print()
    
    input("Press Enter to send the request and watch logs...")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Api-Key": API_KEY
        }
        
        payload = {"query": query}
        
        print(f"\n🚀 Sending POST to {BACKEND_URL}/api/v1/query")
        print()
        
        response = requests.post(
            f"{BACKEND_URL}/api/v1/query",
            json=payload,
            headers=headers,
            timeout=120
        )
        
        print(f"✅ Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Final Result:")
            print(f"   Total products: {data.get('total', 0)}")
            
            products = data.get('products', [])
            if products:
                print(f"\n   Products returned:")
                for idx, prod in enumerate(products, 1):
                    print(f"      {idx}. {prod.get('name')} | ₹{prod.get('price')}")
            else:
                print(f"\n   ⚠️  NO PRODUCTS RETURNED")
        else:
            print(f"\n❌ Error:")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("CHECK THE BACKEND LOGS ABOVE")
    print("=" * 80)
    print("\nLook for these markers:")
    print("  🚀 RETRIEVAL PIPELINE START")
    print("  🔍 SQL STAGE: <stage_name>")
    print("     - SQL query and params")
    print("     - Candidate count and IDs")
    print("  🧠 SEMANTIC SEARCH STAGE")
    print("     - Top semantic scores")
    print("  ⚡ HYBRID RANKING STAGE")
    print("     - Combined scores")
    print("  🤖 LLM VALIDATION STAGE")
    print("     - Validation decisions per product")
    print("  🎯 FINAL SEARCH RESULTS")
    print()
    print("Identify at which stage valid backpacks disappear!")
    print("=" * 80)


if __name__ == "__main__":
    test_waterproof_backpack()
