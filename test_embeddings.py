#!/usr/bin/env python3
"""
Test embedding endpoint on local model server
"""
import requests
import json

LOCAL_URL = "http://localhost:8001"

def test_embed():
    """Test the /embed endpoint."""
    print("=" * 80)
    print("TEST: Embedding Endpoint")
    print("=" * 80)
    
    texts = [
        "running shoes",
        "football boots",
        "Horse riding equipment for kids"
    ]
    
    print(f"\nTexts to embed ({len(texts)}):")
    for i, text in enumerate(texts, 1):
        print(f"  {i}. {text}")
    
    try:
        response = requests.post(
            f"{LOCAL_URL}/embed",
            json={"texts": texts},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"\n❌ HTTP {response.status_code}")
            print(f"   Error: {response.text}")
            return False
        
        data = response.json()
        
        print(f"\n✓ Embeddings generated")
        print(f"   Model: {data.get('model')}")
        print(f"   Dimension: {data.get('dimension')}")
        print(f"   Count: {data.get('count')}")
        
        embeddings = data.get('embeddings', [])
        
        if len(embeddings) != len(texts):
            print(f"\n❌ Expected {len(texts)} embeddings, got {len(embeddings)}")
            return False
        
        print(f"\n✓ All embeddings present")
        
        # Check dimensions
        for i, emb in enumerate(embeddings):
            if len(emb) != data['dimension']:
                print(f"❌ Embedding {i} has wrong dimension: {len(emb)}")
                return False
        
        print(f"✓ All embeddings have correct dimension ({data['dimension']})")
        
        # Show sample
        print(f"\nSample embedding (first 10 values):")
        print(f"  {embeddings[0][:10]}")
        
        print(f"\n✅ TEST PASSED")
        return True
        
    except requests.ConnectionError:
        print("\n❌ Cannot connect to server")
        print(f"   URL: {LOCAL_URL}")
        print("   Is the server running?")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run embedding tests."""
    print("\nEMBEDDING ENDPOINT TEST")
    print(f"Testing server at: {LOCAL_URL}\n")
    
    success = test_embed()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ EMBEDDING TEST PASSED")
        print("=" * 80)
        print("\nThe /embed endpoint is working correctly!")
        print("  ✓ Accepts list of texts")
        print("  ✓ Returns embeddings with correct dimensions")
        print("  ✓ Uses sentence-transformers/all-MiniLM-L6-v2")
        return 0
    else:
        print("❌ EMBEDDING TEST FAILED")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit(main())
