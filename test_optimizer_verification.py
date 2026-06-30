#!/usr/bin/env python3
"""
Verification script to test that the budget optimizer is actually running
and affecting product selection.
"""

import sys
import os
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from tools.task_tool import TaskTool
from models.schemas import TaskArguments

print("=" * 80)
print("BUDGET OPTIMIZER VERIFICATION TEST")
print("=" * 80)
print()
print("This test will verify that:")
print("1. _optimize_selection() is being called")
print("2. All candidate combinations are logged")
print("3. The best combination is selected")
print("4. The selected products are applied to the response")
print("5. Tie-breaker prefers higher cost when scores are equal")
print()
print("Watch the logs above for detailed optimization output.")
print()
print("=" * 80)

# Test Case: Cycling with ₹10,000 budget
print("\nTEST: Cycling Activity with ₹10,000 budget")
print("-" * 80)

task_tool = TaskTool()
task_args = TaskArguments(
    activity="Cycling",
    budget=10000.0,
    query="I want to start cycling"
)

print("\nExecuting task tool...")
response = task_tool.execute(task_args)

print("\n" + "=" * 80)
print("RESPONSE SUMMARY:")
print("=" * 80)
print(f"Activity: {response.activity}")
print(f"Budget: ₹{response.budget:.2f}")
print(f"Total Cost: ₹{response.total_cost:.2f}")
print(f"Budget Remaining: ₹{response.budget_remaining:.2f}")
print(f"Budget Utilization: {(response.total_cost / response.budget * 100):.1f}%")
print(f"Within Budget: {response.within_budget}")
print()

print("SELECTED PRODUCTS:")
print("-" * 80)
for item in response.items:
    mandatory_tag = "(Mandatory)" if item.mandatory else "(Optional)"
    if item.recommended:
        print(f"\n{item.name} {mandatory_tag}:")
        print(f"  Product ID: {item.recommended.product_id}")
        print(f"  Name: {item.recommended.name}")
        print(f"  Price: ₹{item.recommended.price:.2f}")
        print(f"  Budget Allocated: ₹{item.budget_allocated:.2f}")
        if hasattr(item.recommended, 'similarity') and item.recommended.similarity:
            print(f"  Search Score: {item.recommended.similarity:.3f}")
    else:
        print(f"\n{item.name} {mandatory_tag}: NOT SELECTED")

print("\n" + "=" * 80)
print("VERIFICATION CHECKLIST:")
print("=" * 80)
print()
print("Review the logs above to verify:")
print()
print("✓ Look for: '>>> ENTERING _optimize_selection()'")
print("  This confirms the optimizer is being called")
print()
print("✓ Look for: 'CANDIDATES AVAILABLE FOR OPTIMIZATION:'")
print("  This shows all products being considered")
print()
print("✓ Look for: 'Exploring combinations...'")
print("  This shows the search is running")
print()
print("✓ Look for: 'Combination: ... | Cost=₹... | Score=...'")
print("  These are all the combinations being evaluated")
print()
print("✓ Look for: '🏆 BEST COMBINATION FOUND:'")
print("  This shows which combination won")
print()
print("✓ Look for: 'APPLYING OPTIMIZED SELECTION TO ITEMS:'")
print("  This confirms the selected products are being used")
print()
print("✓ Look for: 'Set recommended to...'")
print("  This confirms each item's recommended product is updated")
print()
print("=" * 80)
print("EXPECTED BEHAVIOR:")
print("=" * 80)
print()
print("With ₹10,000 budget for cycling:")
print("- Should NOT select only the cheapest products")
print("- Should use 70-95% of budget")
print("- Should maximize total recommendation score")
print("- Budget remaining should be ₹500-₹3,000 (not ₹8,000+)")
print()
print("If budget remaining is > ₹8,000:")
print("  → Optimizer may not be running")
print("  → Check logs for '>>> ENTERING _optimize_selection()'")
print()
print("=" * 80)
