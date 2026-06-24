#!/usr/bin/env python3
"""
Demo: Budget Optimizer in Action
Shows how the budget optimizer works with realistic scenarios
"""
import sys
sys.path.insert(0, '.')

from tools.budget_optimizer import BudgetOptimizer
from models.schemas import TaskItem, Product

print("=" * 80)
print("BUDGET OPTIMIZER DEMO")
print("=" * 80)
print()
print("Scenario: User wants to start hiking")
print("Budget: ₹10,000")
print()

# Create realistic products
shoes = [
    Product(
        product_id="MH100", name="MH100 Hiking Shoe", brand="Quechua",
        price=1999, mrp=2499, sport="Hiking", category_level_1="Footwear",
        category_level_2="Hiking Shoes", description="Entry-level hiking shoe",
        image_url=None, product_url=None, rating=3.8, review_count=245
    ),
    Product(
        product_id="MH500", name="MH500 Mid Hiking Shoe", brand="Quechua",
        price=3999, mrp=4999, sport="Hiking", category_level_1="Footwear",
        category_level_2="Hiking Shoes", description="Waterproof mid-cut shoe",
        image_url=None, product_url=None, rating=4.5, review_count=512
    ),
    Product(
        product_id="MH900", name="MH900 Premium Shoe", brand="Forclaz",
        price=7999, mrp=9999, sport="Hiking", category_level_1="Footwear",
        category_level_2="Hiking Shoes", description="Premium trekking shoe",
        image_url=None, product_url=None, rating=4.8, review_count=328
    ),
]

backpacks = [
    Product(
        product_id="NH100", name="NH100 20L Backpack", brand="Quechua",
        price=1299, mrp=1699, sport="Hiking", category_level_1="Bags",
        category_level_2="Backpacks", description="Day hiking backpack",
        image_url=None, product_url=None, rating=4.0, review_count=189
    ),
    Product(
        product_id="NH500", name="NH500 30L Backpack", brand="Quechua",
        price=2999, mrp=3999, sport="Hiking", category_level_1="Bags",
        category_level_2="Backpacks", description="Weekend trekking pack",
        image_url=None, product_url=None, rating=4.6, review_count=421
    ),
]

bottles = [
    Product(
        product_id="WB100", name="500ml Water Bottle", brand="Decathlon",
        price=199, mrp=299, sport="Hiking", category_level_1="Accessories",
        category_level_2="Bottles", description="Basic water bottle",
        image_url=None, product_url=None, rating=4.2, review_count=1024
    ),
    Product(
        product_id="WB500", name="Insulated 750ml Bottle", brand="Quechua",
        price=999, mrp=1299, sport="Hiking", category_level_1="Accessories",
        category_level_2="Bottles", description="Keeps drinks cold 12h",
        image_url=None, product_url=None, rating=4.7, review_count=567
    ),
]

poles = [
    Product(
        product_id="TP100", name="Basic Trekking Pole", brand="Quechua",
        price=799, mrp=999, sport="Hiking", category_level_1="Equipment",
        category_level_2="Poles", description="Aluminum poles, adjustable",
        image_url=None, product_url=None, rating=4.1, review_count=234
    ),
]

jacket = [
    Product(
        product_id="RJ100", name="Rain Jacket", brand="Quechua",
        price=1499, mrp=1999, sport="Hiking", category_level_1="Clothing",
        category_level_2="Jackets", description="Waterproof rain jacket",
        image_url=None, product_url=None, rating=4.4, review_count=345
    ),
]

# Create task items
items = [
    TaskItem(name="Hiking Shoes", mandatory=True, products=shoes),
    TaskItem(name="Backpack", mandatory=True, products=backpacks),
    TaskItem(name="Water Bottle", mandatory=False, products=bottles),
    TaskItem(name="Trekking Poles", mandatory=False, products=poles),
    TaskItem(name="Rain Jacket", mandatory=False, products=jacket),
]

print("Available Products:")
print()
print("MANDATORY:")
print("  Hiking Shoes:")
for s in shoes:
    print(f"    - {s.name}: ₹{s.price} (★{s.rating}/5)")
print("  Backpack:")
for b in backpacks:
    print(f"    - {b.name}: ₹{b.price} (★{b.rating}/5)")
print()
print("OPTIONAL:")
print("  Water Bottle:")
for w in bottles:
    print(f"    - {w.name}: ₹{w.price} (★{w.rating}/5)")
print("  Trekking Poles:")
for p in poles:
    print(f"    - {p.name}: ₹{p.price} (★{p.rating}/5)")
print("  Rain Jacket:")
for j in jacket:
    print(f"    - {j.name}: ₹{j.price} (★{j.rating}/5)")
print()
print("=" * 80)
print("RUNNING BUDGET OPTIMIZER...")
print("=" * 80)
print()

# Run optimizer
optimizer = BudgetOptimizer()
result = optimizer.optimize(items, 10000)

# Display result
if result['success']:
    print("✅ SUCCESS!")
    print()
    print(f"Budget: ₹10,000")
    print(f"Total Cost: ₹{result['total_cost']}")
    print(f"Remaining: ₹{10000 - result['total_cost']}")
    print(f"Budget Utilization: {(result['total_cost'] / 10000 * 100):.1f}%")
    print()
    print("Selected Kit:")
    print()
    
    for item in result['items']:
        if item.products:
            product = item.products[0]
            score = optimizer._product_scores.get(product.product_id, 0)
            tag = "MANDATORY" if item.mandatory else "OPTIONAL "
            print(f"  [{tag}] {item.name}")
            print(f"    → {product.name}")
            print(f"       Price: ₹{product.price}")
            print(f"       Rating: ★{product.rating}/5")
            print(f"       Score: {score:.3f}")
            if not item.mandatory:
                utility = score / product.price if product.price > 0 else 0
                print(f"       Utility: {utility:.4f} (value for money)")
            print()
        else:
            print(f"  [OPTIONAL ] {item.name}")
            print(f"    → Not selected (budget constraint)")
            print()
    
    print("=" * 80)
    print("INSIGHTS:")
    print("=" * 80)
    print()
    print("✓ Algorithm selected mid-range mandatory items (good quality)")
    print("✓ Added high-utility optional items within budget")
    print("✓ Balanced quality vs budget utilization")
    print(f"✓ Processed in O(n log n) time complexity")
    print()
    
else:
    print("❌ FAILED")
    print(f"Message: {result['message']}")
    print()

print("=" * 80)
print("DEMO COMPLETE")
print("=" * 80)
