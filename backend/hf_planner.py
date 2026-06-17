"""
Hugging Face Transformers-based Shopping Planner
Production-ready version compatible with Linux cloud deployment

Flow:
User Query → Fine-tuned Qwen (HF) → Structured JSON → Hybrid Search → Products → Qwen → Recommendations
"""
import json
import logging
import re
import torch
from pathlib import Path
from typing import Dict, List, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

from search_pipeline import (
    hybrid_search,
    search_task,
    format_products_for_llm,
    format_task_products_for_llm
)

logger = logging.getLogger(__name__)


def repair_json(json_str: str) -> str:
    """
    Attempt to repair common JSON syntax errors from LLM output.
    
    Args:
        json_str: Potentially malformed JSON string
    
    Returns:
        Repaired JSON string
    """
    repaired = json_str
    
    # Fix 1: Extract price_limit if it's inside keywords array
    price_limit_match = re.search(r'"keywords"\s*:\s*\[(.*?)"price_limit"\s*:\s*(\d+)', repaired, re.DOTALL)
    extracted_price = None
    if price_limit_match:
        extracted_price = price_limit_match.group(2)
        logger.info(f"Found price_limit={extracted_price} inside keywords array, will relocate it")
    
    # Fix 2: Trailing comma before closing bracket/brace
    repaired = re.sub(r',\s*]', ']', repaired)
    repaired = re.sub(r',\s*}', '}', repaired)
    
    # Fix 3: Missing comma between array close and next field
    repaired = re.sub(r']\s*"', '],"', repaired)
    repaired = re.sub(r'}\s*"', '},"', repaired)
    
    # Fix 4: Remove malformed items in arrays
    def clean_array(match):
        array_content = match.group(1)
        items = re.findall(r'"([^"]+)"(?=\s*[,\]])', array_content)
        return '[' + ','.join(f'"{item}"' for item in items if ':' not in item) + ']'
    
    repaired = re.sub(r'\[([^\]]+)\]', clean_array, repaired)
    
    # Fix 5: Add back extracted price_limit
    if extracted_price:
        repaired = re.sub(
            r'("keywords"\s*:\s*\[[^\]]*\])',
            r'\1,\n    "price_limit": ' + extracted_price,
            repaired
        )
        logger.info(f"Relocated price_limit={extracted_price} to correct position")
    
    return repaired


# Configuration
BASE_MODEL_NAME = "Qwen/Qwen2.5-Coder-3B-Instruct"
ADAPTER_PATH = str(Path(__file__).parent.parent / "training/outputs/shopping_agent_lora_hf")

# Global model cache
_model_cache = None
_tokenizer_cache = None
_device = None


def get_device():
    """Determine the best available device."""
    global _device
    if _device is None:
        if torch.cuda.is_available():
            _device = "cuda"
            logger.info(f"✓ Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        else:
            _device = "cpu"
            logger.info("✓ Using CPU (no GPU available)")
    return _device


def load_fine_tuned_model():
    """Load the fine-tuned model with LoRA adapter (cached)."""
    global _model_cache, _tokenizer_cache
    
    if _model_cache is not None:
        return _model_cache, _tokenizer_cache
    
    device = get_device()
    adapter_path = Path(ADAPTER_PATH)
    
    logger.info(f"Loading tokenizer from {BASE_MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME, trust_remote_code=True)
    
    logger.info(f"Loading base model from {BASE_MODEL_NAME}...")
    # Load with 8-bit quantization if GPU available, otherwise full precision
    if device == "cuda":
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_NAME,
            trust_remote_code=True,
            device_map="auto",
            load_in_8bit=True,  # 8-bit quantization for memory efficiency
            torch_dtype=torch.float16
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_NAME,
            trust_remote_code=True,
            device_map="auto",
            torch_dtype=torch.float32
        )
    
    # Load LoRA adapter if it exists
    if adapter_path.exists():
        logger.info(f"Loading LoRA adapter from {ADAPTER_PATH}...")
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)
        logger.info("✓ LoRA adapter loaded successfully")
    else:
        logger.warning(f"⚠️  No LoRA adapter found at {ADAPTER_PATH}")
        logger.warning("   Using base model without fine-tuning")
    
    model.eval()  # Set to evaluation mode
    
    _model_cache = model
    _tokenizer_cache = tokenizer
    
    logger.info("✓ Model loaded and ready")
    return model, tokenizer


def parse_query_with_qwen(user_query: str) -> Optional[Dict]:
    """
    Parse user query into structured JSON using fine-tuned Qwen.
    
    Args:
        user_query: Natural language query
    
    Returns:
        Structured JSON dict or None if parsing fails
    """
    try:
        logger.info("Loading fine-tuned model...")
        model, tokenizer = load_fine_tuned_model()
        device = get_device()
        
        logger.info("Model loaded, generating response...")
        
        # Format prompt for fine-tuned model
        messages = [
            {"role": "user", "content": user_query}
        ]
        
        # Apply chat template
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        logger.info(f"Parsing query with fine-tuned Qwen: {user_query}")
        
        # Tokenize
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        # Generate response
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,  # Greedy decoding for consistency
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode response
        full_response = tokenizer.decode(outputs[0], skip_special_tokens=False)
        
        logger.info(f"Raw response generated (length: {len(full_response)})")
        
        # Extract JSON from response (remove prompt and special tokens)
        response = full_response.split("<|im_start|>assistant\n")[-1]
        response = response.split("<|im_end|>")[0]
        response = response.strip()
        
        logger.info(f"Qwen response: {response[:200]}...")
        
        # Try to parse JSON
        try:
            parsed = json.loads(response)
            logger.info(f"✓ Successfully parsed: intent={parsed.get('intent')}")
            return parsed
        except json.JSONDecodeError as e:
            # Try to repair common JSON errors
            logger.warning(f"JSON parsing error: {e}. Attempting repair...")
            logger.error(f"Original response: {response}")
            
            # Apply repair
            repaired = repair_json(response)
            logger.info(f"Repaired JSON: {repaired[:200]}...")
            
            try:
                parsed = json.loads(repaired)
                logger.info(f"✓ Successfully repaired and parsed: intent={parsed.get('intent')}")
                return parsed
            except json.JSONDecodeError as e2:
                logger.error(f"JSON repair failed: {e2}")
                logger.error(f"Repaired attempt: {repaired}")
                return None
        
    except Exception as e:
        logger.error(f"Query parsing error: {e}", exc_info=True)
        return None


def execute_search(parsed_query: Dict) -> Dict:
    """
    Execute search based on parsed query.
    
    Args:
        parsed_query: Structured query from Qwen
    
    Returns:
        Search results dictionary
    """
    intent = parsed_query.get('intent')
    
    if intent == 'search':
        # Single search request
        search_req = parsed_query.get('search_request', {})
        
        results = hybrid_search(
            sport=search_req.get('sport'),
            category=search_req.get('category'),
            keywords=search_req.get('keywords', []),
            price_limit=search_req.get('price_limit'),
            experience_level=search_req.get('experience_level'),
            top_k=10
        )
        
        return {
            'intent': 'search',
            'products': results,
            'formatted': format_products_for_llm(results)
        }
        
    elif intent == 'task':
        # Multiple search requests
        search_requests = parsed_query.get('search_requests', [])
        
        task_results = search_task(search_requests)
        
        return {
            'intent': 'task',
            'products_by_category': task_results,
            'formatted': format_task_products_for_llm(task_results)
        }
    
    else:
        logger.warning(f"Unknown intent: {intent}")
        return {'intent': 'unknown', 'products': [], 'formatted': 'No products found.'}


def generate_recommendations(
    user_query: str,
    parsed_query: Dict,
    search_results: Dict
) -> str:
    """
    Generate final recommendations using Qwen.
    
    Args:
        user_query: Original user query
        parsed_query: Structured query from Qwen
        search_results: Products from hybrid search
    
    Returns:
        Natural language recommendations
    """
    try:
        model, tokenizer = load_fine_tuned_model()
        device = get_device()
        
        # Build recommendation prompt
        messages = [
            {
                "role": "system",
                "content": "You are a helpful shopping assistant for Decathlon. Based on the user's query and the following products, provide personalized recommendations."
            },
            {
                "role": "user",
                "content": f"""User Query: {user_query}

Products Found:
{search_results['formatted']}

Provide a helpful response that:
1. Acknowledges the user's needs
2. Recommends the top 3-5 products with reasons
3. Mentions key features (price, rating, brand)
4. Is friendly and concise"""
            }
        ]
        
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        logger.info("Generating recommendations with Qwen")
        
        # Tokenize and generate
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode and extract assistant response
        full_response = tokenizer.decode(outputs[0], skip_special_tokens=False)
        response = full_response.split("<|im_start|>assistant\n")[-1]
        response = response.split("<|im_end|>")[0]
        response = response.strip()
        
        logger.info("✓ Recommendations generated")
        return response
        
    except Exception as e:
        logger.error(f"Recommendation generation error: {e}")
        # Fallback: Simple recommendation
        if search_results.get('products'):
            top_product = search_results['products'][0]
            return (
                f"I found some great options for you! "
                f"I'd recommend the {top_product['name']} "
                f"by {top_product.get('brand', 'Decathlon')} "
                f"priced at ₹{top_product['price']}."
            )
        return "I couldn't find any products matching your criteria. Please try a different search."


def shopping_planner_hf(user_query: str) -> Dict:
    """
    Complete shopping planner pipeline with Hugging Face fine-tuned model.
    
    Flow:
        1. Parse query with fine-tuned Qwen → Structured JSON
        2. Execute hybrid search → Products
        3. Generate recommendations with Qwen → Natural language
    
    Args:
        user_query: Natural language user query
    
    Returns:
        Complete response dictionary
    """
    logger.info(f"Processing query: {user_query}")
    
    try:
        # Step 1: Parse query with fine-tuned Qwen
        parsed_query = parse_query_with_qwen(user_query)
        
        if not parsed_query:
            return {
                'status': 'error',
                'error': 'Failed to parse query',
                'user_query': user_query
            }
        
        # Step 2: Execute search
        search_results = execute_search(parsed_query)
        
        # Step 3: Generate recommendations
        recommendations = generate_recommendations(
            user_query=user_query,
            parsed_query=parsed_query,
            search_results=search_results
        )
        
        # Build response
        device = get_device()
        response = {
            'status': 'success',
            'user_query': user_query,
            'parsed_query': parsed_query,
            'intent': parsed_query.get('intent'),
            'recommendations': recommendations,
            'metadata': {
                'model': 'Qwen 2.5 Coder 3B (Hugging Face)',
                'device': device,
                'search_type': 'hybrid',
                'products_found': len(search_results.get('products', []))
            }
        }
        
        # Add products based on intent
        if parsed_query.get('intent') == 'search':
            response['products'] = search_results.get('products', [])
        elif parsed_query.get('intent') == 'task':
            response['products_by_category'] = search_results.get('products_by_category', {})
        
        logger.info(f"✓ Query processed successfully: {response['metadata']['products_found']} products found")
        
        return response
        
    except Exception as e:
        logger.error(f"Shopping planner error: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'user_query': user_query
        }


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test
    print("Testing Hugging Face planner...")
    result = shopping_planner_hf("running shoes under 5000")
    print(json.dumps(result, indent=2))
