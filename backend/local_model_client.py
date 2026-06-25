"""
Local Model Client - HTTP client for connecting to local model server

This client runs on Render and makes HTTP requests to the local model server
running on your Mac (exposed via ngrok).

Architecture:
    Render Backend → HTTP → ngrok → Mac Local Server → Qwen Model
"""
import os
import logging
import requests
from typing import Dict, Optional
from requests.exceptions import ConnectionError, Timeout, RequestException

logger = logging.getLogger(__name__)

# Configuration
LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:8001")
REQUEST_TIMEOUT = int(os.getenv("MODEL_REQUEST_TIMEOUT", "120"))  # 2 minutes


class LocalModelClient:
    """
    Client for making requests to the local model server.
    
    The local server runs on your Mac with Qwen2.5-1.5B-Instruct + LoRA.
    This client makes HTTP requests via ngrok.
    """
    
    def __init__(self, base_url: str = None, timeout: int = None):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the local model server (default: from env)
            timeout: Request timeout in seconds (default: from env)
        """
        self.base_url = base_url or LOCAL_MODEL_URL
        self.timeout = timeout or REQUEST_TIMEOUT
        
        # Remove trailing slash
        self.base_url = self.base_url.rstrip('/')
        
        logger.info(f"LocalModelClient initialized")
        logger.info(f"   Base URL: {self.base_url}")
        logger.info(f"   Timeout: {self.timeout}s")
    
    def health_check(self) -> Dict:
        """
        Check if the local model server is healthy.
        
        Returns:
            Health status dict
        
        Raises:
            ConnectionError: If cannot connect to server
            Timeout: If request times out
        """
        try:
            logger.info(f"Health check: {self.base_url}/health")
            response = requests.get(
                f"{self.base_url}/health",
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ Local model server is healthy")
                return response.json()
            else:
                logger.error(f"❌ Health check failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                raise Exception(f"Health check failed: {response.status_code}")
                
        except ConnectionError as e:
            logger.error("❌ Cannot connect to local model server")
            logger.error(f"   URL: {self.base_url}")
            logger.error(f"   Error: {e}")
            raise ConnectionError(
                f"Cannot connect to local model server at {self.base_url}. "
                f"Is the server running? Is ngrok active?"
            )
        except Timeout as e:
            logger.error("❌ Health check timeout")
            raise Timeout(f"Health check timeout after 10s: {e}")
        except RequestException as e:
            logger.error(f"❌ Health check error: {e}")
            raise
    
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        do_sample: bool = False
    ) -> str:
        """
        Generate response from the local model.
        
        Args:
            prompt: Input prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)
            do_sample: Whether to use sampling
        
        Returns:
            Generated text string
        
        Raises:
            ConnectionError: If cannot connect to server
            Timeout: If request times out
            RequestException: For other HTTP errors
            ValueError: If response is invalid
        """
        try:
            logger.info(f"📤 Sending generation request to local model")
            logger.info(f"   Prompt length: {len(prompt)} chars")
            logger.info(f"   Prompt preview: {prompt[:100]}...")
            
            payload = {
                "prompt": prompt,
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "do_sample": do_sample
            }
            
            response = requests.post(
                f"{self.base_url}/generate",
                json=payload,
                timeout=self.timeout
            )
            
            # Check response status
            if response.status_code != 200:
                logger.error(f"❌ Generation failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                raise RequestException(
                    f"Generation failed with status {response.status_code}: {response.text}"
                )
            
            # Parse response
            result = response.json()
            
            if "response" not in result:
                logger.error(f"❌ Invalid response format: {result}")
                raise ValueError("Response missing 'response' field")
            
            generated_text = result["response"]
            tokens = result.get("tokens_generated", 0)
            model = result.get("model", "unknown")
            device = result.get("device", "unknown")
            
            logger.info("✓ Generation successful")
            logger.info(f"   Model: {model}")
            logger.info(f"   Device: {device}")
            logger.info(f"   Tokens: {tokens}")
            logger.info(f"   Response preview: {generated_text[:100]}...")
            
            return generated_text
            
        except ConnectionError as e:
            logger.error("❌ Cannot connect to local model server")
            logger.error(f"   URL: {self.base_url}")
            logger.error(f"   Error: {e}")
            raise ConnectionError(
                f"Cannot connect to local model server at {self.base_url}. "
                f"Is the server running? Is ngrok active? "
                f"Check LOCAL_MODEL_URL environment variable."
            )
        except Timeout as e:
            logger.error(f"❌ Generation timeout after {self.timeout}s")
            raise Timeout(
                f"Generation timeout after {self.timeout}s. "
                f"Try increasing MODEL_REQUEST_TIMEOUT or using a smaller prompt."
            )
        except RequestException as e:
            logger.error(f"❌ Generation request error: {e}")
            raise
        except ValueError as e:
            logger.error(f"❌ Invalid response: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            raise
    
    def parse_query(self, query: str) -> Dict:
        """
        Parse shopping query and get structured JSON directly.
        
        This method calls the /parse-query endpoint which returns
        parsed JSON structure, not a string that needs parsing.
        
        Args:
            query: User's shopping query
        
        Returns:
            Parsed query dict with intent, search_request(s)
        
        Raises:
            ConnectionError: If cannot connect to server
            Timeout: If request times out
            RequestException: For other HTTP errors
            ValueError: If response is invalid
        """
        try:
            logger.info(f"📤 Sending parse query request: {query}")
            
            payload = {"query": query}
            
            response = requests.post(
                f"{self.base_url}/parse-query",
                json=payload,
                timeout=self.timeout
            )
            
            # Check response status
            if response.status_code != 200:
                logger.error(f"❌ Parse failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                raise RequestException(
                    f"Parse failed with status {response.status_code}: {response.text}"
                )
            
            # Parse response
            result = response.json()
            
            # Validate structure
            if "intent" not in result:
                logger.error(f"❌ Invalid response format: {result}")
                raise ValueError("Response missing 'intent' field")
            
            intent = result["intent"]
            
            logger.info("✓ Parse successful")
            logger.info(f"   Intent: {intent}")
            logger.info(f"   Model: {result.get('model', 'unknown')}")
            
            # Build return dict matching expected format
            parsed = {
                "intent": intent
            }
            
            if intent == "search" and result.get("search_request"):
                parsed["search_request"] = result["search_request"]
            elif intent == "task" and result.get("search_requests"):
                parsed["search_requests"] = result["search_requests"]
            
            return parsed
            
        except ConnectionError as e:
            logger.error("❌ Cannot connect to local model server")
            logger.error(f"   URL: {self.base_url}")
            raise ConnectionError(
                f"Cannot connect to local model server at {self.base_url}. "
                f"Is the server running? Is ngrok active?"
            )
        except Timeout as e:
            logger.error(f"❌ Parse timeout after {self.timeout}s")
            raise Timeout(f"Parse timeout after {self.timeout}s.")
        except RequestException as e:
            logger.error(f"❌ Parse request error: {e}")
            raise
        except ValueError as e:
            logger.error(f"❌ Invalid response: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            raise
    
    def embed(self, texts: list) -> list:
        """
        Generate embeddings for the given texts.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        try:
            logger.info(f"📤 Sending embed request: {len(texts)} texts")
            
            payload = {"texts": texts}
            
            response = requests.post(
                f"{self.base_url}/embed",
                json=payload,
                timeout=self.timeout
            )
            
            # Check response status
            if response.status_code != 200:
                logger.error(f"❌ Embed failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                raise ValueError(
                    f"Embed failed with status {response.status_code}: {response.text}"
                )
            
            # Parse response
            result = response.json()
            
            # Validate structure
            if "embeddings" not in result:
                logger.error(f"❌ Invalid response format: {result}")
                raise ValueError("Response missing 'embeddings' field")
            
            embeddings = result["embeddings"]
            dimension = result.get("dimension", 0)
            model_name = result.get("model", "unknown")
            
            logger.info("✓ Embed successful")
            logger.info(f"   Count: {len(embeddings)}")
            logger.info(f"   Dimension: {dimension}")
            logger.info(f"   Model: {model_name}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Unexpected error in embed: {e}")
            raise


# Global singleton instance
_client = None


def get_client() -> LocalModelClient:
    """Get or create the global LocalModelClient instance."""
    global _client
    if _client is None:
        _client = LocalModelClient()
    return _client


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 80)
    print("Testing LocalModelClient")
    print("=" * 80)
    
    client = LocalModelClient()
    
    # Health check
    print("\n1. Health Check:")
    try:
        health = client.health_check()
        print(f"✓ {health}")
    except Exception as e:
        print(f"❌ {e}")
        exit(1)
    
    # Generate
    print("\n2. Generate:")
    try:
        prompt = "Query: running shoes under 5000"
        response = client.generate(prompt, max_new_tokens=128)
        print(f"✓ Response: {response}")
    except Exception as e:
        print(f"❌ {e}")
        exit(1)
    
    print("\n" + "=" * 80)
    print("✅ All tests passed")
    print("=" * 80)
