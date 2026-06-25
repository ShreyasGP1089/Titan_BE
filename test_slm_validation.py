#!/usr/bin/env python3
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.hybrid_search import HybridSearchService

# Test queries definition
# Format: (query_name, sport, keywords, is_broad, required_terms, excluded_terms)
TEST_QUERIES = [
    # Specific queries
    ("show me water bottles", "Cycling", ["water", "bottle"], False, ["bottle"], ["holder", "cage"]),
    ("show me footballs", "Football", ["football"], False, ["football", "ball"], ["jersey", "goal", "shorts", "socks", "cones", "marker"]),
    ("show me helmets", "Cycling", ["helmet"], False, ["helmet"], ["cover", "mount"]),
    ("show me backpacks", "Hiking", ["backpack"], False, ["backpack", "bag"], ["cover", "raincover"]),
    ("show me tents", "Camping", ["tent"], False, ["tent"], ["peg", "pole", "groundsheet"]),
    ("show me gloves", "Climbing", ["gloves"], False, ["glove", "gloves"], ["liner", "clip"]),
    ("show me hiking shoes", "Hiking", ["shoes", "hiking"], False, ["shoe", "shoes", "footwear"], ["socks", "bag"]),
    ("show me cycling helmets", "Cycling", ["helmet", "cycling"], False, ["helmet"], ["cover"]),
    
    # Broad queries (SLM validation should be bypassed)
    ("show me football gear", "Football", ["football", "gear"], True, [], []),
    ("show me camping equipment", "Camping", ["camping", "equipment"], True, [], []),
    ("show me hiking products", "Hiking", ["hiking", "products"], True, [], [])
]

def main():
    search_service = HybridSearchService()
    
    print("=" * 80)
    print("SLM PRODUCT VALIDATION AND RE-RANKING TEST SUITE")
    print("=" * 80)
    print()
    
    passed_tests = 0
    failed_tests = 0
    
    for i, (query, sport, keywords, is_broad, required, excluded) in enumerate(TEST_QUERIES, 1):
        print(f"TEST {i}: Query='{query}' | Sport='{sport}' | Keywords={keywords} | IsBroad={is_broad}")
        print("-" * 80)
        
        # We retrieve up to 10 products
        results = search_service.search(
            sport=sport,
            keywords=keywords,
            top_k=10
        )
        
        print(f"Returned {len(results)} products.")
        
        if is_broad:
            # For broad queries, verify that we returned general products without filtering them all out
            if len(results) > 0:
                print(f"✅ PASS: Broad query successfully returned products without strict filtering.")
                for p in results[:3]:
                    print(f"  - '{p['name']}' (Score: {p.get('final_score')})")
                passed_tests += 1
            else:
                print(f"❌ FAIL: Broad query returned empty result set.")
                failed_tests += 1
        else:
            # Check for excluded words in name (e.g. holder/cage when bottle is requested)
            import re
            invalid_products = []
            for p in results:
                name = p['name'].lower()
                desc = (p.get('description') or '').lower()
                
                # Check for excluded words in name (e.g. holder/cage when bottle is requested) with word boundaries
                has_exclusion = any(re.search(r'\b' + re.escape(ex) + r'\b', name) for ex in excluded)
                if has_exclusion:
                    # Check if SLM marked it as RELATED (which is acceptable if placed at the end, but let's check validation_decision)
                    decision = p.get("validation_decision", "RELEVANT")
                    if decision == "RELEVANT":
                        invalid_products.append(p)
            
            if invalid_products:
                print(f"❌ FAIL: Returned unrelated/accessory products classified as RELEVANT:")
                for p in invalid_products:
                    print(f"  - '{p['name']}' [Decision: {p.get('validation_decision')} | Reason: {p.get('validation_reason')}]")
                failed_tests += 1
            else:
                print("✅ PASS: All returned products match precision rules.")
                if results:
                    print("Top results:")
                    for j, p in enumerate(results[:5], 1):
                        decision = p.get('validation_decision', 'N/A')
                        score = p.get('final_score')
                        confidence = p.get('validation_confidence', 'N/A')
                        reason = p.get('validation_reason', 'N/A')
                        print(f"  {j}. '{p['name']}'")
                        print(f"     Decision: {decision} | Score: {score} | Confidence: {confidence}")
                        print(f"     Reason: {reason}")
                passed_tests += 1
                
        print()
        print("=" * 80)
        print()
        
    print(f"TEST SUMMARY: {passed_tests} PASSED, {failed_tests} FAILED")
    if failed_tests > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
