"""
Workflow Agent - Integrates SLM (Qwen3-4B) with Backend API

Architecture:
    User Query → This Agent → Qwen3-4B → Structured JSON → Backend API → Results → User
"""
import os
import sys
import json
import logging
import requests
from mlx_lm import load, generate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000/api/v1/agent")
API_KEY = os.getenv("API_KEY", "decathlon_agent_api_key_2024")
MODEL_NAME = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
ADAPTER_PATH = "training/outputs/qwen3_4b_lora_mlx"


class WorkflowAgent:
    """
    Workflow Agent that orchestrates:
    1. User query → SLM parsing → Structured JSON
    2. Structured JSON → Backend API → Results
    3. Results → SLM formatting → User response
    """
    
    def __init__(self, use_adapter=True):
        """
        Initialize the Workflow Agent.
        
        Args:
            use_adapter: Whether to use fine-tuned adapter (default: True)
        """
        logger.info("=" * 80)
        logger.info("Initializing Workflow Agent")
        logger.info("=" * 80)
        
        # Load SLM
        logger.info("Loading Qwen3-4B-Instruct...")
        if use_adapter and os.path.exists(ADAPTER_PATH):
            logger.info(f"Using fine-tuned adapter: {ADAPTER_PATH}")
            self.model, self.tokenizer = load(MODEL_NAME, adapter_path=ADAPTER_PATH)
        else:
            logger.info("Using base model (no adapter)")
            self.model, self.tokenizer = load(MODEL_NAME)
        
        logger.info("✓ Model loaded successfully")
        logger.info("=" * 80)
    
    def parse_query(self, user_query: str) -> dict:
        """
        Parse user's natural language query into structured JSON.
        
        Args:
            user_query: Natural language query
        
        Returns:
            Structured JSON dict
        """
        logger.info(f"Parsing query: {user_query}")
        
        # Build prompt for SLM
        prompt = f"""<|im_start|>user
{user_query}<|im_end|>
<|im_start|>assistant
"""
        
        # Generate with SLM
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=256,
            temp=0.0
        )
        
        # Clean response
        response = response.split("<|im_end|>")[0].strip()
        
        logger.info(f"SLM output: {response}")
        
        # Parse JSON
        try:
            structured = json.loads(response)
            logger.info(f"✓ Parsed intent: {structured.get('intent')}")
            return structured
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Raw response: {response}")
            raise ValueError(f"Invalid JSON from SLM: {response}")
    
    def call_backend(self, structured_json: dict) -> dict:
        """
        Call backend API with structured JSON.
        
        Args:
            structured_json: Structured request
        
        Returns:
            Backend response
        """
        logger.info(f"Calling backend: {BACKEND_URL}")
        
        headers = {
            "Api-Key": API_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            BACKEND_URL,
            headers=headers,
            json=structured_json,
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info("✓ Backend call successful")
            return response.json()
        else:
            logger.error(f"Backend error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            raise Exception(f"Backend error: {response.status_code}")
    
    def format_response(self, backend_results: dict, user_query: str) -> str:
        """
        Format backend results into natural language response.
        
        Args:
            backend_results: Results from backend
            user_query: Original user query
        
        Returns:
            Natural language response
        """
        logger.info("Formatting response...")
        
        # Build context from results
        result_type = backend_results.get('type')
        
        if result_type == 'search':
            products = backend_results.get('products', [])
            context = f"Found {len(products)} products.\n"
            for i, p in enumerate(products[:5], 1):
                context += f"{i}. {p['name']} - ₹{p['price']} (Rating: {p.get('rating', 'N/A')})\n"
        
        elif result_type == 'task':
            activity = backend_results.get('activity')
            budget = backend_results.get('budget')
            items = backend_results.get('items', [])
            context = f"Activity: {activity}\n"
            if budget:
                context += f"Budget: ₹{budget}\n"
                context += f"Total cost: ₹{backend_results.get('total_cost')}\n"
            for item in items:
                context += f"- {item['name']}: {len(item['products'])} options\n"
        
        elif result_type == 'compare':
            products = backend_results.get('products', [])
            context = f"Comparing {len(products)} products:\n"
            for p in products:
                context += f"- {p['name']}: ₹{p['price']}, Rating: {p.get('rating', 'N/A')}\n"
        
        elif result_type == 'alternatives':
            source = backend_results.get('source_product', {})
            products = backend_results.get('products', [])
            context = f"Source: {source['name']} (₹{source['price']})\n"
            context += f"Found {len(products)} alternatives:\n"
            for i, p in enumerate(products[:5], 1):
                context += f"{i}. {p['name']} - ₹{p['price']}\n"
        
        else:
            context = str(backend_results)
        
        # Use SLM to format response
        prompt = f"""<|im_start|>user
Based on the query "{user_query}", format this data into a helpful response:

{context}

Provide a concise, helpful response.<|im_end|>
<|im_start|>assistant
"""
        
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=512,
            temp=0.7
        )
        
        response = response.split("<|im_end|>")[0].strip()
        
        logger.info("✓ Response formatted")
        return response
    
    def process_query(self, user_query: str) -> str:
        """
        Complete workflow: User query → Backend → Response.
        
        Args:
            user_query: Natural language query
        
        Returns:
            Natural language response
        """
        logger.info("=" * 80)
        logger.info(f"Processing: {user_query}")
        logger.info("=" * 80)
        
        try:
            # Step 1: Parse query with SLM
            structured_json = self.parse_query(user_query)
            
            # Step 2: Call backend
            backend_results = self.call_backend(structured_json)
            
            # Step 3: Format response
            response = self.format_response(backend_results, user_query)
            
            logger.info("=" * 80)
            logger.info("✅ Query processed successfully")
            logger.info("=" * 80)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return f"Sorry, I encountered an error: {str(e)}"


def main():
    """Main function for CLI usage"""
    print("=" * 80)
    print("WORKFLOW AGENT - Qwen3-4B + Backend API")
    print("=" * 80)
    
    # Check if backend is running
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code != 200:
            print("❌ Backend is not running!")
            print("   Start it with: cd backend && ./start_api.sh")
            sys.exit(1)
        print("✓ Backend is running")
    except:
        print("❌ Backend is not running!")
        print("   Start it with: cd backend && ./start_api.sh")
        sys.exit(1)
    
    # Initialize agent
    agent = WorkflowAgent(use_adapter=True)
    
    print("\nWorkflow Agent ready!")
    print("Type your query (or 'quit' to exit)")
    print("=" * 80)
    
    # Interactive loop
    while True:
        try:
            query = input("\nYou: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            response = agent.process_query(query)
            print(f"\nAgent: {response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()
