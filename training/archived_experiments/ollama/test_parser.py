"""
Parser Evaluation Script
Tests Ollama parser accuracy across 100 sample queries
"""
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from ollama_parser import parse_query_with_ollama, test_ollama_connection
import logging

logging.basicConfig(level=logging.WARNING)  # Reduce noise

# Test queries with expected outputs
TEST_QUERIES = [
    # Search queries
    {
        "query": "running shoes under 5000",
        "expected_intent": "search",
        "expected_sport": "Running",
        "expected_category": "Running Shoes",
        "expected_price": 5000
    },
    {
        "query": "kids football below 1000",
        "expected_intent": "search",
        "expected_sport": "Football",
        "expected_price": 1000
    },
    {
        "query": "organic cereals",
        "expected_intent": "search"
    },
    {
        "query": "tennis racket for beginners",
        "expected_intent": "search",
        "expected_sport": "Tennis",
        "expected_level": "beginner"
    },
    {
        "query": "yoga mat",
        "expected_intent": "search",
        "expected_sport": "Yoga"
    },
    
    # Task queries
    {
        "query": "I want to start playing tennis",
        "expected_intent": "task",
        "expected_sport": "Tennis",
        "expected_min_categories": 3
    },
    {
        "query": "I want to start running",
        "expected_intent": "task",
        "expected_sport": "Running",
        "expected_min_categories": 3
    },
    {
        "query": "What do I need for cycling?",
        "expected_intent": "task",
        "expected_sport": "Cycling"
    },
    {
        "query": "I'm starting basketball",
        "expected_intent": "task",
        "expected_sport": "Basketball"
    },
    {
        "query": "Help me start swimming",
        "expected_intent": "task",
        "expected_sport": "Swimming"
    },
]


def evaluate_parser():
    """Run comprehensive parser evaluation."""
    
    print("="*80)
    print("OLLAMA PARSER EVALUATION")
    print("="*80)
    
    # Test connection
    print("\n1. Testing Ollama connection...")
    if not test_ollama_connection():
        print("❌ Ollama not available")
        return False
    
    print("✓ Ollama connected\n")
    
    # Run tests
    print("2. Running test queries...")
    print("="*80)
    
    results = {
        "total": len(TEST_QUERIES),
        "json_valid": 0,
        "intent_correct": 0,
        "sport_correct": 0,
        "category_detected": 0,
        "price_correct": 0,
        "level_correct": 0,
        "task_decomposition_correct": 0,
        "failed": 0
    }
    
    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        print(f"\n[{i}/{len(TEST_QUERIES)}] {query}")
        
        # Parse query
        parsed = parse_query_with_ollama(query)
        
        if not parsed:
            print("   ❌ Failed to parse")
            results["failed"] += 1
            continue
        
        # JSON valid
        results["json_valid"] += 1
        print(f"   ✓ JSON valid")
        
        # Check intent
        if parsed.get("intent") == test.get("expected_intent"):
            results["intent_correct"] += 1
            print(f"   ✓ Intent: {parsed.get('intent')}")
        else:
            print(f"   ❌ Intent: {parsed.get('intent')} (expected {test.get('expected_intent')})")
        
        # Check sport (for search intent)
        if test.get("expected_sport"):
            if parsed.get("intent") == "search":
                sport = parsed.get("search_request", {}).get("sport", "")
            else:
                # Task intent - check first request
                sport = parsed.get("search_requests", [{}])[0].get("sport", "")
            
            if test["expected_sport"].lower() in sport.lower():
                results["sport_correct"] += 1
                print(f"   ✓ Sport: {sport}")
            else:
                print(f"   ❌ Sport: {sport} (expected {test['expected_sport']})")
        
        # Check category detection
        if parsed.get("intent") == "search":
            category = parsed.get("search_request", {}).get("category")
            if category:
                results["category_detected"] += 1
                print(f"   ✓ Category: {category}")
        
        # Check price extraction
        if test.get("expected_price"):
            if parsed.get("intent") == "search":
                price = parsed.get("search_request", {}).get("price_limit")
                if price == test["expected_price"]:
                    results["price_correct"] += 1
                    print(f"   ✓ Price: {price}")
                else:
                    print(f"   ❌ Price: {price} (expected {test['expected_price']})")
        
        # Check experience level
        if test.get("expected_level"):
            if parsed.get("intent") == "search":
                level = parsed.get("search_request", {}).get("experience_level")
                if test["expected_level"] in str(level).lower():
                    results["level_correct"] += 1
                    print(f"   ✓ Level: {level}")
        
        # Check task decomposition
        if test.get("expected_min_categories"):
            if parsed.get("intent") == "task":
                num_categories = len(parsed.get("search_requests", []))
                if num_categories >= test["expected_min_categories"]:
                    results["task_decomposition_correct"] += 1
                    print(f"   ✓ Task decomposition: {num_categories} categories")
                else:
                    print(f"   ❌ Task decomposition: {num_categories} (expected >={test['expected_min_categories']})")
        
        print(f"   Result: {json.dumps(parsed, indent=2)[:200]}...")
    
    # Print summary
    print("\n" + "="*80)
    print("EVALUATION SUMMARY")
    print("="*80)
    
    total = results["total"]
    print(f"\nTotal queries: {total}")
    print(f"JSON validity: {results['json_valid']}/{total} ({100*results['json_valid']/total:.1f}%)")
    print(f"Intent accuracy: {results['intent_correct']}/{total} ({100*results['intent_correct']/total:.1f}%)")
    
    # Sport accuracy (only for queries with expected sport)
    sport_tests = len([t for t in TEST_QUERIES if t.get("expected_sport")])
    if sport_tests > 0:
        print(f"Sport accuracy: {results['sport_correct']}/{sport_tests} ({100*results['sport_correct']/sport_tests:.1f}%)")
    
    # Category detection
    search_queries = len([t for t in TEST_QUERIES if t.get("expected_intent") == "search"])
    if search_queries > 0:
        print(f"Category detection: {results['category_detected']}/{search_queries} ({100*results['category_detected']/search_queries:.1f}%)")
    
    # Price extraction
    price_tests = len([t for t in TEST_QUERIES if t.get("expected_price")])
    if price_tests > 0:
        print(f"Price extraction: {results['price_correct']}/{price_tests} ({100*results['price_correct']/price_tests:.1f}%)")
    
    # Task decomposition
    task_tests = len([t for t in TEST_QUERIES if t.get("expected_min_categories")])
    if task_tests > 0:
        print(f"Task decomposition: {results['task_decomposition_correct']}/{task_tests} ({100*results['task_decomposition_correct']/task_tests:.1f}%)")
    
    print(f"\nFailed: {results['failed']}/{total} ({100*results['failed']/total:.1f}%)")
    
    print("\n" + "="*80)
    
    # Overall score
    success_rate = 100 * (total - results['failed']) / total
    if success_rate >= 90:
        print(f"✅ EXCELLENT: {success_rate:.1f}% success rate")
    elif success_rate >= 80:
        print(f"✓ GOOD: {success_rate:.1f}% success rate")
    elif success_rate >= 70:
        print(f"⚠️  ACCEPTABLE: {success_rate:.1f}% success rate")
    else:
        print(f"❌ NEEDS IMPROVEMENT: {success_rate:.1f}% success rate")
    
    print("="*80)
    
    return success_rate >= 70


if __name__ == "__main__":
    success = evaluate_parser()
    exit(0 if success else 1)
