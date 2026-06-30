#!/usr/bin/env python3
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.hybrid_search import HybridSearchService

def get_variations(word: str) -> list:
    w = word.lower()
    vars = [w]
    if w.endswith('s') and len(w) > 3:
        vars.append(w[:-1])
        if w.endswith('es') and len(w) > 4:
            vars.append(w[:-2])
    else:
        vars.append(w + 's')
        vars.append(w + 'es')
    return list(set(vars))

# Define test cases
# Format: (query_str, sport, keywords, list_of_required_terms, price_limit)
TEST_CASES = [
    ("show me gloves", "Climbing", ["gloves"], ["glove", "gloves"], None),
    ("show me water bottles", "Cycling", ["water", "bottle"], ["bottle", "bottles"], None),
    ("show me backpacks", "Hiking", ["backpack"], ["backpack", "backpacks", "bag", "bags"], None),
    ("show me footballs", "Football", ["football"], ["football", "footballs", "ball", "balls"], None),
    ("show me tents", "Camping", ["tent"], ["tent", "tents"], None),
    ("show me helmets", "Cycling", ["helmet"], ["helmet", "helmets"], None),
    ("climbing harnesses", "Climbing", ["harness"], ["harness", "harnesses"], None),
    ("waterproof hiking shoes", "Hiking", ["shoes", "waterproof"], ["shoe", "shoes", "footwear", "boot", "boots"], None),
    ("men running shoes under 3000", "Running", ["shoes", "men"], ["shoe", "shoes", "footwear"], 3000.0),
    ("kids hiking shoes under 4000", "Hiking", ["shoes", "kids"], ["shoe", "shoes", "footwear"], 4000.0),
    ("camping chair", "Camping", ["chair"], ["chair", "chairs", "seat", "seats"], None),
    ("waterproof backpack", "Hiking", ["waterproof", "backpack"], ["backpack", "backpacks", "bag", "bags"], None),
    ("water repellent backpack", "Hiking", ["water", "repellent", "backpack"], ["backpack", "backpacks", "bag", "bags"], None),
    ("golf club", "Golf", ["golf", "club"], ["club", "clubs", "putter", "driver", "iron", "wedge", "hybrid", "wood"], None),
    ("football", "Football", ["football"], ["football", "footballs", "ball", "balls"], None),
    ("yoga mat", "Yoga", ["yoga", "mat"], ["mat", "mats"], None),
    ("camping tent", "Camping", ["camping", "tent"], ["tent", "tents"], None),
    ("football backpack", "Football", ["football", "backpack"], ["backpack", "backpacks", "bag", "bags"], None),
]

def main():
    search_service = HybridSearchService()
    
    print("=" * 80)
    print()
    
    failed_tests = 0
    passed_tests = 0
    
    for i, (query, sport, keywords, required_terms, price_limit) in enumerate(TEST_CASES, 1):
        print(f"TEST {i}: Query='{query}', Sport='{sport}', Keywords={keywords}, PriceLimit={price_limit}")
        print("-" * 80)
        
        results = search_service.search(
            sport=sport,
            keywords=keywords,
            price_limit=price_limit,
            top_k=5
        )
        
        print(f"Returned {len(results)} products.")
        
        # Verify precision: all returned products must contain at least one of the required terms in name/description
        invalid_products = []
        for product in results:
            name = product['name'].lower()
            desc = (product.get('description') or '').lower()
            
            # Check if any variation of required terms matches
            match = False
            for term in required_terms:
                variations = get_variations(term)
                if any(var in name or var in desc for var in variations):
                    match = True
                    break
            
            if not match:
                invalid_products.append(product)
                
        if invalid_products:
            print(f"❌ FAIL: Returned {len(invalid_products)} unrelated products:")
            for p in invalid_products:
                print(f"  - '{p['name']}' [id={p['product_id']}]")
                print(f"    Desc: {p.get('description')}")
            failed_tests += 1
        else:
            print("✅ PASS: All returned products match the expected product type (or list is empty).")
            if results:
                for p in results[:3]:
                    print(f"  - '{p['name']}' (Score: {p.get('final_score')})")
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
