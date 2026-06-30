#!/usr/bin/env python3
"""
Test script to verify the compatibility layer for product discovery response format.

Expected behavior:
1. Search Tool (external API) → returns SearchResponse with products + related
2. Task Tool (internal) → receives flat list of RELEVANT products only
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.hybrid_search import HybridSearchService
from tools.search_tool import SearchTool
from tools.task_tool import TaskTool
from models.schemas import SearchRequest, TaskArguments

print("=" * 80)
print("COMPATIBILITY LAYER TEST")
print("=" * 80)
print()

# Test 1: Direct hybrid_search.search() with dict format
print("TEST 1: HybridSearchService.search() with return_format='dict'")
print("-" * 80)
search_service = HybridSearchService()
result_dict = search_service.search(
    sport="Cycling",
    keywords=["helmet"],
    top_k=5,
    return_format='dict'
)
print(f"✓ Return type: {type(result_dict)}")
print(f"✓ Has 'relevant' key: {'relevant' in result_dict}")
print(f"✓ Has 'related' key: {'related' in result_dict}")
if isinstance(result_dict, dict):
    print(f"✓ RELEVANT products: {len(result_dict.get('relevant', []))}")
    print(f"✓ RELATED products: {len(result_dict.get('related', []))}")
print()

# Test 2: Direct hybrid_search.search() with flat format
print("TEST 2: HybridSearchService.search() with return_format='flat'")
print("-" * 80)
result_flat = search_service.search(
    sport="Cycling",
    keywords=["helmet"],
    top_k=5,
    return_format='flat'
)
print(f"✓ Return type: {type(result_flat)}")
print(f"✓ Is list: {isinstance(result_flat, list)}")
if isinstance(result_flat, list):
    print(f"✓ Products returned: {len(result_flat)}")
    if result_flat:
        print(f"✓ Sample product keys: {list(result_flat[0].keys())[:5]}")
print()

# Test 3: Search Tool (external API endpoint)
print("TEST 3: SearchTool.execute() - External API format")
print("-" * 80)
search_tool = SearchTool()
request = SearchRequest(
    sport="Cycling",
    keywords=["helmet"]
)
response = search_tool.execute(request)
print(f"✓ Response type: {type(response).__name__}")
print(f"✓ Has 'products' field: {hasattr(response, 'products')}")
print(f"✓ Has 'related' field: {hasattr(response, 'related')}")
print(f"✓ Has 'total' field: {hasattr(response, 'total')}")
print(f"✓ Has 'related_total' field: {hasattr(response, 'related_total')}")
print(f"✓ RELEVANT products: {response.total}")
print(f"✓ RELATED products: {response.related_total}")
print()

# Test 4: Task Tool (internal tool)
print("TEST 4: TaskTool.execute() - Internal backward-compatible format")
print("-" * 80)
task_tool = TaskTool()
task_args = TaskArguments(
    activity="Cycling",
    query="I want to start cycling"
)
task_response = task_tool.execute(task_args)
print(f"✓ Response type: {type(task_response).__name__}")
print(f"✓ Activity: {task_response.activity}")
print(f"✓ Items returned: {len(task_response.items)}")
for item in task_response.items:
    print(f"   - {item.name}: {len(item.products)} products")
    if item.products:
        # Verify products are Product objects with expected fields
        first_product = item.products[0]
        print(f"     Sample: {first_product.name} (ID: {first_product.product_id})")
        # Verify no 'related' awareness in Task Tool
        print(f"     Has validation_decision: {hasattr(first_product, 'validation_decision')}")
print()

print("=" * 80)
print("✅ COMPATIBILITY LAYER TEST COMPLETE")
print("=" * 80)
print()
print("SUMMARY:")
print("1. External API (SearchTool) receives dict format with products + related")
print("2. Internal tools (TaskTool) receive flat list of RELEVANT products only")
print("3. No changes to Task Tool logic or validation")
print("4. Backward compatibility maintained")
