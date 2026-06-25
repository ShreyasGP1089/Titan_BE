#!/usr/bin/env python3
"""
Test script to debug prompt format mismatch
Compares apply_chat_template vs manual ChatML format
"""
import requests
import json

import os
LOCAL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:8000")

def test_debug_prompt(query: str):
    """Test the debug-prompt endpoint."""
    print("=" * 80)
    print("PROMPT FORMAT DEBUG TEST")
    print("=" * 80)
    print(f"\nQuery: {query}\n")
    
    try:
        response = requests.post(
            f"{LOCAL_URL}/debug-prompt",
            json={"query": query},
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print("=" * 80)
            print("RESULTS")
            print("=" * 80)
            
            # Chat template info
            print(f"\n✓ Chat template found: {data['chat_template_found']}")
            
            if data['chat_template_found'] and data['chat_template_prompt']:
                print("\n--- Method 1: apply_chat_template ---")
                print(f"Prompt:\n{data['chat_template_prompt']}")
                print(f"\nToken count: {len(data['chat_template_tokens'])}")
                print(f"First 20 tokens: {data['chat_template_tokens'][:20]}")
                print(f"\nOutput:\n{data['chat_template_output'][:500]}")
            
            # ChatML format
            print("\n--- Method 2: Manual ChatML Format ---")
            print(f"Prompt:\n{data['chatml_prompt']}")
            print(f"\nToken count: {len(data['chatml_tokens'])}")
            print(f"First 20 tokens: {data['chatml_tokens'][:20]}")
            print(f"\nOutput:\n{data['chatml_output'][:500]}")
            
            # Comparison
            print("\n--- Comparison ---")
            comparison = data['comparison']
            if comparison.get('prompts_match') is not None:
                if comparison['prompts_match']:
                    print("✓ Prompts MATCH - Both methods produce identical prompts")
                else:
                    print("✗ Prompts DIFFER - Methods produce different prompts")
            
            print(f"  chat_template token count: {comparison['token_count_chat_template']}")
            print(f"  ChatML token count: {comparison['token_count_chatml']}")
            print(f"  chat_template output length: {comparison['output_length_chat_template']}")
            print(f"  ChatML output length: {comparison['output_length_chatml']}")
            
            # Recommendation
            print("\n--- Recommendation ---")
            print(f"✓ {data['recommendation']}")
            
            print("\n" + "=" * 80)
            
            # Try to parse outputs as JSON
            print("\nJSON PARSING TEST")
            print("=" * 80)
            
            if data['chat_template_output']:
                print("\nMethod 1 (chat_template):")
                try:
                    parsed = json.loads(data['chat_template_output'])
                    print(f"✓ Valid JSON")
                    print(f"  Intent: {parsed.get('intent')}")
                except json.JSONDecodeError as e:
                    print(f"✗ Invalid JSON: {e}")
            
            print("\nMethod 2 (ChatML):")
            try:
                parsed = json.loads(data['chatml_output'])
                print(f"✓ Valid JSON")
                print(f"  Intent: {parsed.get('intent')}")
            except json.JSONDecodeError as e:
                print(f"✗ Invalid JSON: {e}")
            
            print("\n" + "=" * 80)
            return True
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.ConnectionError:
        print("❌ Cannot connect to server")
        print(f"   URL: {LOCAL_URL}")
        print("   Is the server running?")
        print("   Start with: python3 local_model_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run debug tests."""
    test_queries = [
        "Horse riding boots for kids below 3000",
        "running shoes under 5000",
        "I want to start playing football"
    ]
    
    for query in test_queries:
        success = test_debug_prompt(query)
        if not success:
            break
        print("\n" * 2)


if __name__ == "__main__":
    main()
