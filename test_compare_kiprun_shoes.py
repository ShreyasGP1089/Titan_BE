#!/usr/bin/env python3
"""
Test script to verify comparison resolution for Kiprun running shoes.

This script tests that:
1. Each product mention is parsed separately
2. Each mention is resolved independently via Product Discovery
3. The correct running shoes are returned (not unrelated products)
"""

import sys
import os
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from tools.compare_tool import CompareTool
from models.schemas import CompareArguments

print("=" * 80)
print("COMPARISON RESOLUTION TEST: Kiprun Running Shoes")
print("=" * 80)
print()

# Test Case: Compare two Kiprun running shoes
print("TEST: Compare Kiprun KD900X LD+ and Kiprun KD500 2")
print("-" * 80)
print()

compare_tool = CompareTool()

# Simulate the parsed product mentions from the query
# "Compare Kiprun KD900X LD+ and Kiprun KD500 2"
product_mentions = [
    "Kiprun KD900X LD+",
    "Kiprun KD500 2"
]

print("Input product mentions:")
for idx, mention in enumerate(product_mentions, 1):
    print(f"  {idx}. \"{mention}\"")
print()

print("Executing comparison resolution...")
print("(Watch logs above for detailed resolution process)")
print()

try:
    compare_args = CompareArguments(products=product_mentions)
    result = compare_tool.execute(compare_args)
    
    print("=" * 80)
    print("COMPARISON RESOLUTION SUCCESSFUL")
    print("=" * 80)
    print()
    
    print(f"Resolved {len(result.products)} products:")
    print()
    
    for idx, product in enumerate(result.products, 1):
        print(f"Product {idx}:")
        print(f"  Name: {product.name}")
        print(f"  Product ID: {product.product_id}")
        print(f"  Brand: {product.brand}")
        print(f"  Price: ₹{product.price:.2f}")
        print(f"  Category: {product.category_level_1} / {product.category_level_2}")
        if product.rating:
            print(f"  Rating: {product.rating} ({product.review_count} reviews)")
        print()
    
    print("=" * 80)
    print("VERIFICATION CHECKLIST:")
    print("=" * 80)
    print()
    
    # Verify products are running shoes, not unrelated items
    product_names = [p.name.lower() for p in result.products]
    product_categories = [f"{p.category_level_1}/{p.category_level_2}".lower() for p in result.products]
    
    print("✓ Check 1: Both products resolved")
    if len(result.products) == 2:
        print("  PASS: 2 products returned")
    else:
        print(f"  FAIL: Expected 2 products, got {len(result.products)}")
    print()
    
    print("✓ Check 2: Products are running shoes (not T-shirts/visors/etc)")
    unrelated_items = []
    for idx, name in enumerate(product_names, 1):
        if any(bad in name for bad in ['t-shirt', 'tshirt', 'visor', 'cap', 'shorts', 'socks']):
            unrelated_items.append(f"Product {idx}: {result.products[idx-1].name}")
    
    if not unrelated_items:
        print("  PASS: All products appear to be shoes")
    else:
        print(f"  FAIL: Found unrelated items:")
        for item in unrelated_items:
            print(f"    - {item}")
    print()
    
    print("✓ Check 3: Products are Kiprun brand")
    non_kiprun = []
    for idx, product in enumerate(result.products, 1):
        if product.brand and 'kiprun' not in product.brand.lower():
            non_kiprun.append(f"Product {idx}: {product.brand}")
    
    if not non_kiprun:
        print("  PASS: All products are Kiprun brand")
    else:
        print(f"  WARN: Some products may not be Kiprun:")
        for item in non_kiprun:
            print(f"    - {item}")
    print()
    
    print("✓ Check 4: Products are in Running/Footwear categories")
    wrong_category = []
    for idx, category in enumerate(product_categories, 1):
        if 'running' not in category and 'footwear' not in category and 'shoe' not in category:
            wrong_category.append(f"Product {idx}: {result.products[idx-1].category_level_1}/{result.products[idx-1].category_level_2}")
    
    if not wrong_category:
        print("  PASS: All products in appropriate categories")
    else:
        print(f"  FAIL: Some products in wrong categories:")
        for item in wrong_category:
            print(f"    - {item}")
    print()
    
    print("=" * 80)
    print("EXPECTED BEHAVIOR:")
    print("=" * 80)
    print()
    print("The logs above should show:")
    print("  1. 'Parsed product mentions: 1. \"Kiprun KD900X LD+\" 2. \"Kiprun KD500 2\"'")
    print("  2. Separate resolution for each product:")
    print("     - 'RESOLVING PRODUCT 1: \"Kiprun KD900X LD+\"'")
    print("     - 'RESOLVING PRODUCT 2: \"Kiprun KD500 2\"'")
    print("  3. Product Discovery called for each with full product name")
    print("  4. Top RELEVANT product selected from each search")
    print("  5. Both resolved products should be running shoes")
    print()
    print("INCORRECT BEHAVIOR (if still broken):")
    print("  - Resolving only by brand 'Kiprun'")
    print("  - Returning T-shirts, visors, or other non-shoe products")
    print("  - Merging both product names into one search")
    print()
    
except Exception as e:
    print("=" * 80)
    print("COMPARISON RESOLUTION FAILED")
    print("=" * 80)
    print()
    print(f"Error: {str(e)}")
    print()
    print("This may indicate:")
    print("  - Products not found in database")
    print("  - Product Discovery returned no results")
    print("  - Resolution logic error")
    print()

print("=" * 80)
