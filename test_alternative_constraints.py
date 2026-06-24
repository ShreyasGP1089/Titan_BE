#!/usr/bin/env python3
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from tools.alternatives_tool import AlternativesTool
from models.schemas import AlternativesArguments

def run_test_case(name, query, product_ref, assertion_fn, allow_empty=False):
    print("=" * 80)
    print(f"TEST: {name}")
    print(f"Query: '{query}'")
    print(f"Product Ref: {product_ref}")
    print("-" * 80)
    
    tool = AlternativesTool()
    args = AlternativesArguments(
        product=product_ref,
        query=query
    )
    
    try:
        res = tool.execute(args)
        source = res.source_product
        print(f"Source Product: '{source.name}' [brand={source.brand}, price=₹{source.price}, rating={source.rating}]")
        print(f"Returned {res.total} alternatives:")
        
        passed = True
        for p in res.products:
            match_status = "PASS"
            if not assertion_fn(source, p):
                match_status = "FAIL ❌"
                passed = False
            print(f"  - '{p.name}' [brand={p.brand}, price=₹{p.price}, rating={p.rating}] -> {match_status}")
            
        if passed and res.total > 0:
            print("✅ TEST PASSED!")
            return True
        elif res.total == 0 and allow_empty:
            print("✅ TEST PASSED (0 results is valid — constraint correctly filtered all candidates)")
            return True
        elif res.total == 0:
            print("❌ TEST FAILED (No alternatives returned)")
            return False
        else:
            print("❌ TEST FAILED (Assertion failed for some products)")
            return False
    except Exception as e:
        print(f"❌ TEST FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_substitute_only():
    # Only footballs returned (no apparel, cones, etc.)
    def assertion(source, p):
        name = p.name.lower()
        is_sub = "ball" in name or "football" in name or (p.category_level_1 or "").lower() == "balls"
        is_acc = any(kw in name for kw in ["cone", "jersey", "short", "sock", "tights", "pants", "glove", "bag"])
        return is_sub and not is_acc
        
    return run_test_case(
        "Substitute Only (No accessories/apparel)",
        "Show alternatives to Football Size 5 Germany 2026",
        "Football Size 5 Germany 2026",
        assertion
    )

def test_higher_rating():
    def assertion(source, p):
        if source.rating is None:
            return True
        return p.rating is not None and p.rating > source.rating
        
    return run_test_case(
        "Higher Rating",
        "Show alternatives to Football Size 5 Germany 2026 with a higher rating",
        "Football Size 5 Germany 2026",
        assertion
    )

def test_lower_price():
    def assertion(source, p):
        return p.price < source.price
        
    return run_test_case(
        "Lower Price (Cheaper)",
        "Show cheaper alternatives to Size 5 FIFA Basic Football Club Hybrid - Red Black",
        "Size 5 FIFA Basic Football Club Hybrid - Red Black",
        assertion
    )

def test_premium_ranking():
    def assertion(source, p):
        return "ball" in p.name.lower() or (p.category_level_1 or "").lower() == "balls"
        
    return run_test_case(
        "Premium Alternatives Boost",
        "Show premium alternatives to Football Size 5 Germany 2026",
        "Football Size 5 Germany 2026",
        assertion
    )

def test_budget_limit():
    def assertion(source, p):
        return p.price <= 1000.0
        
    return run_test_case(
        "Budget Limit",
        "Show alternatives to Cycle Water Bottle 650ml Black under ₹1000",
        "Cycle Water Bottle 650ml Black",
        assertion
    )

def test_different_brand():
    # All footballs in the DB are brand KIPSTA, so 0 results is the correct outcome.
    # The test verifies that: IF any results are returned, none are the same brand.
    def assertion(source, p):
        return (p.brand or "").strip().lower() != (source.brand or "").strip().lower()
        
    return run_test_case(
        "Different Brand",
        "Show alternatives to Football Size 5 Germany 2026 from another brand",
        "Football Size 5 Germany 2026 from another brand",
        assertion,
        allow_empty=True  # All footballs are KIPSTA — 0 results is correct
    )

def test_source_product_resolution():
    print("=" * 80)
    print("TEST: Source Product Resolution (Robust to Suffix Constraints)")
    print("=" * 80)
    
    queries = [
        ("Football Size 5 Germany 2026", "Football Size 5 Germany 2026"),
        ("Football Size 5 Germany 2026 with higher rating", "Football Size 5 Germany 2026 with higher rating"),
        ("Football Size 5 Germany 2026 from another brand", "Football Size 5 Germany 2026 from another brand"),
        ("Football Size 5 Germany 2026 from same brand", "Football Size 5 Germany 2026 from same brand"),
        ("Football Size 5 Germany 2026 under ₹1000", "Football Size 5 Germany 2026 under ₹1000")
    ]
    
    tool = AlternativesTool()
    passed = True
    for query, p_ref in queries:
        try:
            args = AlternativesArguments(
                product=p_ref,
                query=query
            )
            # Call resolve product directly
            source = tool._resolve_product(p_ref)
            pid = source.get("product_id")
            name = source.get("name")
            if pid == "8949587":
                print(f"  - '{p_ref}' -> RESOLVED TO expected ID 8949587 ('{name}'): PASS")
            else:
                print(f"  - '{p_ref}' -> RESOLVED TO WRONG ID {pid} ('{name}'): FAIL ❌")
                passed = False
        except Exception as e:
            print(f"  - '{p_ref}' -> FAILED with exception: {e}: FAIL ❌")
            passed = False
            
    if passed:
        print("✅ TEST PASSED!")
    else:
        print("❌ TEST FAILED!")
    return passed

def main():
    print("=" * 80)
    print("RUNNING ALTERNATIVES V2 CONSTRAINT VERIFICATION")
    print("=" * 80)
    
    passed = True
    passed &= test_source_product_resolution()
    passed &= test_substitute_only()
    passed &= test_higher_rating()
    passed &= test_lower_price()
    passed &= test_premium_ranking()
    passed &= test_budget_limit()
    passed &= test_different_brand()
    
    print("=" * 80)
    if passed:
        print("ALL V2 ALTERNATIVE CONSTRAINT TESTS PASSED!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
