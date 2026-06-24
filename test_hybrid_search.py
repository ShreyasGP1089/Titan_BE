#!/usr/bin/env python3
"""
Test script for True Hybrid Search implementation

Tests:
1. Golf clubs search should return actual clubs, not towels/apparel
2. Score breakdown verification (semantic vs keyword)
3. Task tool validation (Golf Clubs should not return towels)
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.hybrid_search import HybridSearchService
from tools.task_tool import TaskTool
from models.schemas import TaskArguments

print("=" * 80)
print("TRUE HYBRID SEARCH TEST SUITE")
print("=" * 80)
print()

# Initialize services
search_service = HybridSearchService()
task_tool = TaskTool()

# Test 1: Golf clubs search
print("TEST 1: Golf Clubs Search")
print("-" * 80)
print("Query: sport=Golf, keywords=['clubs']")
print()

results = search_service.search(
    sport="Golf",
    keywords=["clubs"],
    top_k=10
)

print(f"Results: {len(results)} products")
print()

for i, product in enumerate(results, 1):
    name = product['name']
    semantic = product.get('semantic_score', 0)
    keyword = product.get('keyword_score', 0)
    final = product.get('final_score', 0)
    price = product.get('price', 0)
    
    print(f"{i}. {name}")
    print(f"   Price: ₹{price}")
    print(f"   Scores - Semantic: {semantic:.3f}, Keyword: {keyword:.3f}, Final: {final:.3f}")
    print()

# Check if top results are actually clubs
print("Validation:")
top_5_names = [p['name'].lower() for p in results[:5]]
club_keywords = ['club', 'iron', 'driver', 'putter', 'wood', 'wedge']

club_count = 0
for name in top_5_names:
    if any(kw in name for kw in club_keywords):
        club_count += 1

print(f"Top 5 products containing club keywords: {club_count}/5")

if club_count >= 3:
    print("✅ PASS: Majority of top results are actual golf clubs")
else:
    print("❌ FAIL: Too many non-club items in top results")

print()
print("=" * 80)

# Test 2: Golf balls search
print("TEST 2: Golf Balls Search")
print("-" * 80)
print("Query: sport=Golf, keywords=['balls']")
print()

results = search_service.search(
    sport="Golf",
    keywords=["balls"],
    top_k=5
)

print(f"Results: {len(results)} products")
print()

for i, product in enumerate(results, 1):
    name = product['name']
    semantic = product.get('semantic_score', 0)
    keyword = product.get('keyword_score', 0)
    final = product.get('final_score', 0)
    
    print(f"{i}. {name}")
    print(f"   Scores - Semantic: {semantic:.3f}, Keyword: {keyword:.3f}, Final: {final:.3f}")

print()
print("=" * 80)

# Test 3: Task Tool validation
print("TEST 3: Task Tool - Golf Equipment")
print("-" * 80)
print("Task: Golf with budget ₹10000")
print()

try:
    task_result = task_tool.execute(TaskArguments(
        activity="Golf",
        budget=10000
    ))
    print(f"Task completed successfully: {len(task_result.items) > 0}")
    print(f"Items: {len(task_result.items)}")
    print()
    
    for item in task_result.items:
        print(f"Item: {item.name} (Mandatory: {item.mandatory})")
        print(f"  Products found: {len(item.products)}")
        
        if item.products:
            top_product = item.products[0]
            print(f"  Top product: {top_product.name}")
            print(f"  Price: ₹{top_product.price}")
        
        print()
    
    # Validate Golf Clubs item
    golf_clubs_item = next((item for item in task_result.items if item.name == "Golf Clubs"), None)
    
    if golf_clubs_item:
        if golf_clubs_item.products:
            top_club = golf_clubs_item.products[0]
            club_name_lower = top_club.name.lower()
            
            is_valid_club = any(kw in club_name_lower for kw in ['club', 'iron', 'driver', 'putter', 'wood', 'wedge'])
            
            if is_valid_club:
                print(f"✅ PASS: Golf Clubs item returned actual club: {top_club.name}")
            else:
                print(f"❌ FAIL: Golf Clubs item returned non-club: {top_club.name}")
        else:
            print("⚠️  WARNING: No products found for Golf Clubs")
    else:
        print("❌ FAIL: Golf Clubs item not found")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)

# Test 4: Keyword scoring logic
print("TEST 4: Keyword Scoring Logic")
print("-" * 80)

test_products = [
    {
        "product_id": "TEST1",
        "name": "Golf Iron Set",
        "category_level_1": "Golf Equipment",
        "category_level_2": "",
        "description": "Professional golf club set"
    },
    {
        "product_id": "TEST2",
        "name": "Golf Towel Tri Fold Red",
        "category_level_1": "Golf Accessories",
        "category_level_2": "",
        "description": "Great for cleaning golf clubs and balls"
    },
    {
        "product_id": "TEST3",
        "name": "Golf Clubs Premium",
        "category_level_1": "Golf Equipment",
        "category_level_2": "",
        "description": "Complete club set"
    }
]

keywords = ["clubs"]

print(f"Keywords: {keywords}")
print()

for product in test_products:
    score = search_service.calculate_keyword_score(product, keywords)
    print(f"{product['name']}")
    print(f"  Keyword Score: {score:.3f}")
    print()

print("Expected: Golf Iron Set and Golf Clubs Premium should score higher than Golf Towel")
print()
print("=" * 80)

print()
print("✅ HYBRID SEARCH TESTS COMPLETE")
print("=" * 80)
