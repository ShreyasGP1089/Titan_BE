#!/usr/bin/env python3
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from tools.task_tool import TaskTool, is_kids_product
from models.schemas import TaskArguments


def test_golf_adult_beginner():
    print("TEST 1: Golf for Adult Beginner ('I want to start playing golf')")
    print("-" * 60)
    tool = TaskTool()
    args = TaskArguments(
        activity="Golf",
        query="I want to start playing golf",
        budget=None
    )
    res = tool.execute(args)
    
    print(f"Activity: {res.activity}")
    print(f"Query: {res.query}")
    
    failed = False
    for item in res.items:
        rec = item.recommended
        if not rec:
            print(f"❌ '{item.name}': No recommended product found!")
            failed = True
            continue
            
        is_kids = is_kids_product(rec)
        print(f"Item: '{item.name}'")
        print(f"  Recommended: '{rec.name}' [id={rec.product_id}] (Price: ₹{rec.price}, Profile Score: {rec.profile_score})")
        print(f"  Is Kids Product? {is_kids}")
        
        if is_kids:
            print(f"  ❌ FAIL: Recommended a kids' product for an adult beginner query!")
            failed = True
            
    if not failed:
        print("✅ PASS: Correctly recommended adult products for adult beginner query!")
    print()
    return not failed


def test_hiking_kids():
    print("TEST 2: Hiking for Kids ('my kid wants to start hiking')")
    print("-" * 60)
    tool = TaskTool()
    args = TaskArguments(
        activity="Hiking",
        query="my kid wants to start hiking",
        budget=None
    )
    res = tool.execute(args)
    
    print(f"Activity: {res.activity}")
    print(f"Query: {res.query}")
    
    failed = False
    # Check if kids shoes are recommended
    shoes_item = next((item for item in res.items if "Shoes" in item.name or "Footwear" in item.name or "Boots" in item.name), None)
    if not shoes_item:
        print("⚠️ No shoes item found in Hiking activity definitions.")
    else:
        rec = shoes_item.recommended
        if not rec:
            print("❌ No recommended product found for Hiking Shoes!")
            failed = True
        else:
            is_kids = is_kids_product(rec)
            print(f"Shoes Recommended: '{rec.name}' [id={rec.product_id}] (Price: ₹{rec.price}, Profile Score: {rec.profile_score})")
            print(f"  Is Kids Product? {is_kids}")
            if not is_kids:
                print("  ❌ FAIL: Recommended an adult product when a kids' product was requested!")
                failed = True
                
    if not failed:
        print("✅ PASS: Correctly recommended kids products for kids hiking query!")
    print()
    return not failed


def test_camping_adult():
    print("TEST 3: Camping for Adult ('I want to get into camping')")
    print("-" * 60)
    tool = TaskTool()
    args = TaskArguments(
        activity="Camping",
        query="I want to get into camping",
        budget=None
    )
    res = tool.execute(args)
    
    print(f"Activity: {res.activity}")
    print(f"Query: {res.query}")
    
    failed = False
    for item in res.items:
        rec = item.recommended
        if not rec:
            continue
        is_kids = is_kids_product(rec)
        print(f"Item: '{item.name}'")
        print(f"  Recommended: '{rec.name}' [id={rec.product_id}] (Price: ₹{rec.price}, Profile Score: {rec.profile_score})")
        
        if is_kids:
            print(f"  ❌ FAIL: Recommended a kids' product for camping query!")
            failed = True
            
    if not failed:
        print("✅ PASS: Correctly recommended adult products for camping query!")
    print()
    return not failed


def main():
    print("=" * 80)
    print("RUNNING TASK RECOMMENDATION (PHASE 1) TESTS")
    print("=" * 80)
    print()
    
    all_passed = True
    all_passed &= test_golf_adult_beginner()
    all_passed &= test_hiking_kids()
    all_passed &= test_camping_adult()
    
    print("=" * 80)
    if all_passed:
        print("ALL TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
