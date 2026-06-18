"""
Ollama-based Query Parser for E-commerce Search
Uses local Qwen3:4b via Ollama API for zero-shot JSON parsing

Flow:
User Query → Ollama Qwen3:4b → Structured JSON → Hybrid Search
"""
import json
import logging
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:4b"
OLLAMA_TIMEOUT = 30  # seconds

# System prompt for structured JSON parsing
SYSTEM_PROMPT = """You are the Query Understanding Engine for a Conversational Commerce Assistant.

Your ONLY responsibility is to convert natural language shopping queries into structured JSON.

You do NOT recommend products.

You do NOT explain.

You do NOT chat.

You ALWAYS return valid JSON only.

No markdown.

No code blocks.

No extra text.

---

There are exactly THREE intents:

1. search

User is looking for a specific type of product.

Examples:

"horse riding boots below 3000"

"organic cereals"

"yoga mat for beginners"

Return:

{
"intent": "search",
"task_name": null,
"search_request": {
"sport": "",
"category": "",
"keywords": [],
"price_limit": null,
"experience_level": null
},
"search_requests": []
}

---

2. task

User wants to perform an activity or start a hobby.

Examples:

"I want to start football"

"I want to go camping"

"Planning home fitness"

"I'm going trekking"

Return:

{
"intent": "task",
"task_name": "",
"search_request": null,
"search_requests": [
{
"sport": "",
"category": "",
"keywords": [],
"price_limit": null,
"experience_level": null
}
]
}

The search_requests array contains ALL categories the user will likely need.

Examples:

User:

I want to start football

Output:

{
"intent": "task",
"task_name": "Start Football",
"search_request": null,
"search_requests": [
{
"sport": "Football",
"category": "Football",
"keywords": [],
"price_limit": null,
"experience_level": null
},
{
"sport": "Football",
"category": "Football Shoes",
"keywords": [],
"price_limit": null,
"experience_level": null
},
{
"sport": "Football",
"category": "Shin Guards",
"keywords": [],
"price_limit": null,
"experience_level": null
},
{
"sport": "Football",
"category": "Football Jersey",
"keywords": [],
"price_limit": null,
"experience_level": null
}
]
}

---

3. compare

User wants to compare products or categories.

Examples:

"compare yoga mats"

"best cereals vs oats"

"compare horse riding helmets"

Return:

{
"intent": "compare",
"task_name": null,
"search_request": {
"sport": "",
"category": "",
"keywords": [],
"price_limit": null,
"experience_level": null
},
"search_requests": []
}

---

Rules

1.

Always output valid JSON.

2.

Never output explanations.

3.

Never output markdown.

4.

If the user specifies a budget:

"below 3000"

"under 50"

"less than 100"

extract:

"price_limit"

5.

If the user specifies experience:

"beginner"

"intermediate"

"advanced"

extract:

"experience_level"

6.

If the user mentions age or audience:

"kids"

"junior"

"women"

"men"

add them to:

"keywords"

7.

If the sport is obvious but not explicitly mentioned, infer it.

Example:

"riding boots"

↓

sport:

"Horse Riding"

8.

For task intent:

Think like an expert shopper.

Return all important categories required to perform the activity.

Example:

"I want to go camping"

↓

Tent

Sleeping Bag

Camping Backpack

Camping Stove

Sleeping Mat

Camping Light

9.

For compare intent:

Return only ONE search_request.

Comparison logic happens elsewhere.

10.

Always use this exact schema:

{
"intent": "search | task | compare",
"task_name": null,
"search_request": {
"sport": "",
"category": "",
"keywords": [],
"price_limit": null,
"experience_level": null
},
"search_requests": []
}

Return JSON only.
"""


def parse_query_with_ollama(user_query: str, retry: bool = True) -> Optional[Dict]:
    """
    Parse user query using Ollama Qwen3:4b.
    
    Args:
        user_query: Natural language query
        retry: Whether to retry once on failure
    
    Returns:
        Structured JSON dict or None if parsing fails
    """
    try:
        # Build prompt
        prompt = f"{SYSTEM_PROMPT}\n\n{user_query}"
        
        # Ollama API request
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,  # Deterministic output
                "top_p": 0.9,
                "num_predict": 512,  # Max tokens
            }
        }
        
        logger.info(f"Parsing query with Ollama: {user_query}")
        
        # Call Ollama API
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )
        
        if response.status_code != 200:
            logger.error(f"Ollama API error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
        
        # Extract response
        result = response.json()
        raw_response = result.get("response", "").strip()
        
        logger.info(f"Ollama raw response: {raw_response[:200]}...")
        
        # Try to parse JSON
        try:
            parsed = json.loads(raw_response)
            logger.info(f"✓ Successfully parsed: intent={parsed.get('intent')}")
            
            # Validate structure
            if not validate_parsed_json(parsed):
                logger.warning("Invalid JSON structure, attempting repair...")
                parsed = repair_json_structure(parsed)
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing error: {e}")
            logger.error(f"Raw response: {raw_response}")
            
            # Try to extract JSON from response (in case model added text)
            extracted = extract_json_from_text(raw_response)
            if extracted:
                logger.info("✓ Extracted JSON from response text")
                return extracted
            
            # Retry once
            if retry:
                logger.info("Retrying query parse...")
                return parse_query_with_ollama(user_query, retry=False)
            
            return None
        
    except requests.Timeout:
        logger.error(f"Ollama API timeout after {OLLAMA_TIMEOUT}s")
        return None
    except Exception as e:
        logger.error(f"Query parsing error: {e}", exc_info=True)
        return None


def validate_parsed_json(parsed: Dict) -> bool:
    """Validate that parsed JSON has correct structure."""
    if "intent" not in parsed:
        return False
    
    intent = parsed.get("intent")
    
    if intent == "search":
        if "search_request" not in parsed:
            return False
        req = parsed["search_request"]
        return "sport" in req and "category" in req and "keywords" in req
    
    elif intent == "task":
        if "search_requests" not in parsed:
            return False
        requests_list = parsed["search_requests"]
        if not isinstance(requests_list, list) or len(requests_list) == 0:
            return False
        return all("sport" in r and "category" in r for r in requests_list)
    
    return False


def repair_json_structure(parsed: Dict) -> Dict:
    """Attempt to repair common JSON structure issues."""
    # Ensure required fields exist
    if "intent" not in parsed:
        parsed["intent"] = "search"  # Default
    
    if parsed["intent"] == "search":
        if "search_request" not in parsed:
            # Try to extract from top level
            parsed["search_request"] = {
                "sport": parsed.get("sport", ""),
                "category": parsed.get("category", ""),
                "keywords": parsed.get("keywords", []),
                "price_limit": parsed.get("price_limit"),
                "experience_level": parsed.get("experience_level")
            }
    
    elif parsed["intent"] == "task":
        if "search_requests" not in parsed:
            if "search_request" in parsed:
                # Single request, convert to list
                parsed["search_requests"] = [parsed["search_request"]]
    
    return parsed


def extract_json_from_text(text: str) -> Optional[Dict]:
    """Extract JSON object from text that may contain other content."""
    import re
    
    # Try to find JSON object in text
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, text, re.DOTALL)
    
    for match in matches:
        try:
            parsed = json.loads(match)
            if validate_parsed_json(parsed):
                return parsed
        except json.JSONDecodeError:
            continue
    
    return None


def test_ollama_connection() -> bool:
    """Test if Ollama is running and model is available."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]
            
            if OLLAMA_MODEL in model_names or any(OLLAMA_MODEL in name for name in model_names):
                logger.info(f"✓ Ollama connected, {OLLAMA_MODEL} available")
                return True
            else:
                logger.error(f"❌ Model {OLLAMA_MODEL} not found in Ollama")
                logger.error(f"   Available models: {model_names}")
                return False
        else:
            logger.error(f"❌ Ollama API returned status {response.status_code}")
            return False
    except requests.ConnectionError:
        logger.error("❌ Cannot connect to Ollama. Is it running?")
        logger.error("   Start with: ollama serve")
        return False
    except Exception as e:
        logger.error(f"❌ Ollama connection error: {e}")
        return False


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test connection
    print("Testing Ollama connection...")
    if not test_ollama_connection():
        print("\n❌ Ollama not available. Please start it with: ollama serve")
        exit(1)
    
    print("\n✓ Ollama connected!\n")
    
    # Test queries
    test_queries = [
        "running shoes under 5000",
        "I want to start playing tennis",
        "kids football below 1000",
        "organic cereals",
        "I want to start running"
    ]
    
    print("Testing query parsing...")
    print("="*80)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        result = parse_query_with_ollama(query)
        if result:
            print(f"✓ Parsed: {json.dumps(result, indent=2)}")
        else:
            print("❌ Failed to parse")
        print("-"*80)
