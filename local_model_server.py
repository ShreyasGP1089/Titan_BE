"""
Local Model Server - Runs on Mac with ngrok
Hosts Qwen2.5-1.5B-Instruct + LoRA for inference

This server runs LOCALLY on your Mac and handles all LLM inference.
The Render backend calls this server via HTTP.

Compatible with Apple Silicon (M1/M2/M3/M4/M5) - MPS Backend
NO bitsandbytes, NO CUDA

Start with:
    python3 local_model_server.py
    
Expose with ngrok:
    ngrok http 8001
"""
import os
import json
import logging
import torch
from pathlib import Path
from typing import Optional, Literal, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import uvicorn

# Print diagnostics on import
print("=" * 80)
print("ENVIRONMENT DIAGNOSTICS")
print("=" * 80)
print(f"PyTorch version: {torch.__version__}")
try:
    import transformers
    print(f"Transformers version: {transformers.__version__}")
except Exception as e:
    print(f"Transformers version: ERROR - {e}")

try:
    import peft
    print(f"PEFT version: {peft.__version__}")
except Exception as e:
    print(f"PEFT version: ERROR - {e}")

try:
    import numpy as np
    print(f"NumPy version: {np.__version__}")
    if np.__version__.startswith('2.'):
        print("⚠️  WARNING: NumPy 2.x detected - this may cause compatibility issues")
        print("   Recommended: numpy<2.0.0")
except Exception as e:
    print(f"NumPy version: ERROR - {e}")

print(f"CUDA available: {torch.cuda.is_available()}")
print(f"MPS available: {torch.backends.mps.is_available()}")
print(f"MPS built: {torch.backends.mps.is_built()}")

if torch.cuda.is_available():
    print(f"Selected device: CUDA")
elif torch.backends.mps.is_available():
    print(f"Selected device: MPS (Apple Silicon)")
else:
    print(f"Selected device: CPU")
print("=" * 80)
print()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_PATH = "training/outputs/qwen25_1_5b_lora_hf"
PORT = int(os.getenv("PORT", 8001))

# Global model cache
_model = None
_tokenizer = None
_device = None
_embedding_model = None

app = FastAPI(
    title="Local Model Server",
    description="Qwen2.5-1.5B-Instruct + LoRA + Embeddings inference server",
    version="1.0.0"
)


class GenerateRequest(BaseModel):
    """Request model for generation."""
    prompt: str
    max_new_tokens: int = 256
    temperature: float = 0.0
    do_sample: bool = False


class GenerateResponse(BaseModel):
    """Response model for generation."""
    response: str
    model: str
    device: str
    tokens_generated: int


class ParseQueryRequest(BaseModel):
    """Request model for query parsing."""
    query: str


class ParseQueryResponse(BaseModel):
    """
    Response model for query parsing.
    
    Supports both search and task intents:
    - search: returns search_request (single request)
    - task: returns search_requests (list of requests)
    """
    intent: Literal["search", "task"]
    search_request: Optional[dict] = None
    search_requests: Optional[list] = None
    raw_response: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_intent_fields(self):
        """Validate that the correct field is present based on intent."""
        if self.intent == "search":
            if self.search_request is None:
                raise ValueError("search_request is required when intent is 'search'")
        elif self.intent == "task":
            if self.search_requests is None:
                raise ValueError("search_requests is required when intent is 'task'")
        return self


class DebugPromptRequest(BaseModel):
    """Request model for debug prompt comparison."""
    query: str


class DebugPromptResponse(BaseModel):
    """Response model for debug prompt comparison."""
    query: str
    chat_template_found: bool
    chat_template_prompt: str = None
    chat_template_tokens: list = None
    chat_template_output: str = None
    chatml_prompt: str
    chatml_tokens: list
    chatml_output: str
    comparison: dict
    recommendation: str


class EmbedRequest(BaseModel):
    """Request model for embeddings."""
    texts: list


class EmbedResponse(BaseModel):
    """Response model for embeddings."""
    embeddings: list
    model: str
    dimension: int
    count: int


def get_device():
    """Determine the best available device."""
    global _device
    if _device is None:
        if torch.cuda.is_available():
            _device = "cuda"
            logger.info(f"✓ Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        elif torch.backends.mps.is_available():
            _device = "mps"
            logger.info("✓ Using Apple Metal (MPS) GPU acceleration")
        else:
            _device = "cpu"
            logger.info("✓ Using CPU (no GPU available)")
    return _device


def load_model():
    """Load the model with LoRA adapter at startup."""
    global _model, _tokenizer
    
    if _model is not None:
        return _model, _tokenizer
    
    logger.info("=" * 80)
    logger.info("🤖 LOADING MODEL")
    logger.info("=" * 80)
    
    device = get_device()
    
    # Load tokenizer
    logger.info(f"📥 Loading tokenizer from {BASE_MODEL}...")
    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token
    
    logger.info("✓ Tokenizer loaded")
    
    # Print chat template for debugging
    logger.info("=" * 80)
    logger.info("CHAT TEMPLATE INSPECTION")
    logger.info("=" * 80)
    if hasattr(_tokenizer, 'chat_template') and _tokenizer.chat_template:
        logger.info(f"Chat template found:")
        logger.info(f"{_tokenizer.chat_template}")
    else:
        logger.info("⚠️  No chat template found")
    logger.info("=" * 80)
    
    # Load base model (NO bitsandbytes, NO quantization)
    logger.info(f"📥 Loading base model from {BASE_MODEL}...")
    logger.info("⏳ This will take 30-60 seconds...")
    
    # Use float16 on GPU, float32 on CPU
    use_float16 = device in ["cuda", "mps"]
    dtype = torch.float16 if use_float16 else torch.float32
    
    logger.info(f"   Device: {device}")
    logger.info(f"   Dtype: {dtype}")
    logger.info(f"   Low CPU memory usage: True")
    
    _model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        trust_remote_code=True,
        torch_dtype=dtype,
        low_cpu_mem_usage=True
        # NO device_map - we'll move to device manually
        # NO quantization_config - we don't use bitsandbytes
        # NO load_in_4bit or load_in_8bit
    )
    
    logger.info("✓ Base model loaded")
    
    # Move to device (MPS for Apple Silicon)
    if device != "cpu":
        logger.info(f"📦 Moving model to {device.upper()}...")
        _model = _model.to(device)
        logger.info(f"✓ Model moved to {device.upper()}")
    
    # Load LoRA adapter (REQUIRED)
    adapter_path = Path(ADAPTER_PATH)
    if not adapter_path.exists():
        error_msg = f"LoRA adapter not found at {ADAPTER_PATH}"
        logger.error(f"❌ {error_msg}")
        logger.error("   Train the adapter first: python3 training/train_hf.py")
        raise FileNotFoundError(error_msg)
    
    logger.info(f"📦 Loading LoRA adapter from {ADAPTER_PATH}...")
    try:
        _model = PeftModel.from_pretrained(_model, str(adapter_path))
        logger.info("✓ LoRA adapter loaded successfully!")
        logger.info("   Using fine-tuned Qwen2.5-1.5B for better JSON parsing")
    except Exception as e:
        logger.error(f"❌ LoRA adapter loading failed: {e}")
        raise
    
    _model.eval()  # Set to evaluation mode
    
    logger.info(f"✓ Model ready on {device.upper()}")
    logger.info("=" * 80)
    
    return _model, _tokenizer


def load_embedding_model():
    """Load the embedding model at startup."""
    global _embedding_model
    
    if _embedding_model is not None:
        return _embedding_model
    
    logger.info("=" * 80)
    logger.info("🔤 LOADING EMBEDDING MODEL")
    logger.info("=" * 80)
    
    try:
        from sentence_transformers import SentenceTransformer
        
        embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info(f"📥 Loading {embedding_model_name}...")
        
        _embedding_model = SentenceTransformer(embedding_model_name)
        
        logger.info(f"✓ Embedding model loaded")
        logger.info(f"   Dimension: {_embedding_model.get_sentence_embedding_dimension()}")
        logger.info("=" * 80)
        
        return _embedding_model
        
    except Exception as e:
        logger.error(f"❌ Embedding model loading failed: {e}")
        raise


@app.on_event("startup")
async def startup_event():
    """Load models on startup."""
    logger.info("🚀 Starting Local Model Server")
    logger.info(f"   Port: {PORT}")
    logger.info(f"   LLM: {BASE_MODEL}")
    logger.info(f"   Adapter: {ADAPTER_PATH}")
    logger.info(f"   Embeddings: sentence-transformers/all-MiniLM-L6-v2")
    
    try:
        # Load LLM + LoRA
        load_model()
        
        # Load embedding model
        load_embedding_model()
        
        logger.info("✅ All models ready for requests")
    except Exception as e:
        logger.error(f"❌ Failed to load models: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Local Model Server",
        "model": BASE_MODEL,
        "adapter": ADAPTER_PATH,
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    device = get_device()
    return {
        "status": "healthy",
        "model": BASE_MODEL,
        "device": device,
        "adapter_loaded": _model is not None
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Generate response from the model using ChatML format.
    
    This matches the training data format exactly:
    <|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n
    
    Args:
        request: GenerateRequest with prompt and generation parameters
    
    Returns:
        GenerateResponse with generated text
    """
    try:
        logger.info(f"📥 Generation request: {request.prompt[:100]}...")
        
        model, tokenizer = load_model()
        device = get_device()
        
        # Use ChatML format (matches training data)
        chatml_prompt = f"<|im_start|>user\n{request.prompt}<|im_end|>\n<|im_start|>assistant\n"
        
        # Tokenize input
        inputs = tokenizer(chatml_prompt, return_tensors="pt").to(device)
        
        # Generate
        logger.info("⏳ Generating response...")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=request.max_new_tokens,
                do_sample=request.do_sample,
                temperature=request.temperature if request.do_sample else None,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode only generated tokens (not the prompt)
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        response = tokenizer.decode(generated, skip_special_tokens=False)
        
        # Remove <|im_end|> token if present
        response = response.split("<|im_end|>")[0].strip()
        
        tokens_generated = len(generated)
        
        logger.info(f"✓ Generated {tokens_generated} tokens")
        logger.info(f"   Response: {response[:100]}...")
        
        return GenerateResponse(
            response=response,
            model=BASE_MODEL,
            device=device,
            tokens_generated=tokens_generated
        )
        
    except Exception as e:
        logger.error(f"❌ Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse-query", response_model=ParseQueryResponse)
async def parse_query(request: ParseQueryRequest):
    """
    Parse shopping query and return structured JSON directly.
    
    Uses ChatML format (matches training data):
    <|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n
    
    This endpoint handles the full parsing logic and returns parsed JSON,
    not a string that needs to be parsed again.
    
    Args:
        request: ParseQueryRequest with user query
    
    Returns:
        ParseQueryResponse with parsed intent and search parameters
    """
    try:
        logger.info(f"📥 Parse query request: {request.query}")
        
        model, tokenizer = load_model()
        device = get_device()
        
        # Build ChatML prompt (matches training format exactly)
        user_message = f"""You are a JSON parser for shopping queries. You MUST respond with ONLY valid JSON, no other text.

Output format:
{{
  "intent": "search" or "task",
  "search_request": {{...}} (if intent is "search"),
  "search_requests": [{{...}}, {{...}}] (if intent is "task")
}}

Examples:
Query: "running shoes under 5000"
{{"intent": "search", "search_request": {{"sport": "Running", "category": "Running Shoes", "keywords": ["shoes"], "price_limit": 5000}}}}

Query: "I want to start playing football"
{{"intent": "task", "search_requests": [{{"sport": "Football", "category": "Football", "keywords": []}}, {{"sport": "Football", "category": "Football Shoes", "keywords": ["shoes"]}}]}}

Now parse this query:
{request.query}"""
        
        chatml_prompt = f"<|im_start|>user\n{user_message}<|im_end|>\n<|im_start|>assistant\n"
        
        # Tokenize
        inputs = tokenizer(chatml_prompt, return_tensors="pt").to(device)
        
        # Generate
        logger.info("⏳ Parsing query...")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                temperature=0.0,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode only generated tokens (not the prompt)
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        response = tokenizer.decode(generated, skip_special_tokens=False)
        
        # Remove <|im_end|> token if present
        response = response.split("<|im_end|>")[0].strip()
        
        logger.info(f"✓ Raw response: {response[:100]}...")
        
        # Parse JSON
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            logger.error(f"   Response: {response}")
            raise HTTPException(
                status_code=500,
                detail=f"Model returned invalid JSON: {response[:200]}"
            )
        
        # Validate structure
        if "intent" not in parsed:
            raise HTTPException(
                status_code=500,
                detail="Model response missing 'intent' field"
            )
        
        intent = parsed["intent"]
        
        logger.info(f"✓ Parsed successfully: intent={intent}")
        
        # Return structured response
        return ParseQueryResponse(
            intent=intent,
            search_request=parsed.get("search_request"),
            search_requests=parsed.get("search_requests"),
            raw_response=response,
            model=BASE_MODEL,
            device=device
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Parse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    """
    Generate embeddings for the given texts.
    
    Uses sentence-transformers/all-MiniLM-L6-v2 (384 dimensions).
    
    Args:
        request: EmbedRequest with list of texts
    
    Returns:
        EmbedResponse with embeddings for each text
    """
    try:
        if not request.texts:
            raise HTTPException(status_code=400, detail="texts cannot be empty")
        
        logger.info(f"📥 Embed request: {len(request.texts)} texts")
        
        embedding_model = load_embedding_model()
        
        # Generate embeddings
        logger.info("⏳ Generating embeddings...")
        embeddings = embedding_model.encode(request.texts, convert_to_numpy=True)
        
        # Convert to list of lists
        embeddings_list = embeddings.tolist()
        
        dimension = len(embeddings_list[0]) if embeddings_list else 0
        
        logger.info(f"✓ Generated {len(embeddings_list)} embeddings")
        logger.info(f"   Dimension: {dimension}")
        
        return EmbedResponse(
            embeddings=embeddings_list,
            model="sentence-transformers/all-MiniLM-L6-v2",
            dimension=dimension,
            count=len(embeddings_list)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/debug-prompt", response_model=DebugPromptResponse)
async def debug_prompt(request: DebugPromptRequest):
    """
    Debug endpoint to compare chat template vs ChatML prompt formats.
    
    This helps diagnose prompt format mismatches between training and inference.
    Training uses ChatML format:
        <|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n
    
    Args:
        request: DebugPromptRequest with user query
    
    Returns:
        DebugPromptResponse with both formats compared
    """
    try:
        logger.info("=" * 80)
        logger.info(f"🔍 DEBUG PROMPT COMPARISON")
        logger.info("=" * 80)
        logger.info(f"Query: {request.query}")
        
        model, tokenizer = load_model()
        device = get_device()
        
        # Check if chat template exists
        has_chat_template = hasattr(tokenizer, 'chat_template') and tokenizer.chat_template is not None
        
        chat_template_prompt = None
        chat_template_tokens = None
        chat_template_output = None
        
        # Method 1: apply_chat_template (if available)
        if has_chat_template:
            logger.info("\n--- Method 1: apply_chat_template ---")
            try:
                messages = [{"role": "user", "content": request.query}]
                chat_template_prompt = tokenizer.apply_chat_template(
                    messages, 
                    tokenize=False, 
                    add_generation_prompt=True
                )
                logger.info(f"Prompt:\n{chat_template_prompt}")
                
                # Tokenize and generate
                inputs = tokenizer(chat_template_prompt, return_tensors="pt").to(device)
                chat_template_tokens = inputs.input_ids[0].tolist()
                logger.info(f"Token IDs: {chat_template_tokens[:20]}... ({len(chat_template_tokens)} total)")
                
                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=128,
                        do_sample=False,
                        eos_token_id=tokenizer.eos_token_id,
                        pad_token_id=tokenizer.eos_token_id
                    )
                
                # Decode only generated tokens
                generated_ids = outputs[0][inputs.input_ids.shape[1]:].tolist()
                chat_template_output = tokenizer.decode(generated_ids, skip_special_tokens=False)
                logger.info(f"Generated token IDs: {generated_ids[:20]}...")
                logger.info(f"Output:\n{chat_template_output[:200]}...")
                
            except Exception as e:
                logger.warning(f"apply_chat_template failed: {e}")
                has_chat_template = False
        
        # Method 2: Manual ChatML format (training format)
        logger.info("\n--- Method 2: Manual ChatML Format ---")
        chatml_prompt = f"<|im_start|>user\n{request.query}<|im_end|>\n<|im_start|>assistant\n"
        logger.info(f"Prompt:\n{chatml_prompt}")
        
        # Tokenize and generate
        inputs = tokenizer(chatml_prompt, return_tensors="pt").to(device)
        chatml_tokens = inputs.input_ids[0].tolist()
        logger.info(f"Token IDs: {chatml_tokens[:20]}... ({len(chatml_tokens)} total)")
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.eos_token_id
            )
        
        # Decode only generated tokens
        generated_ids = outputs[0][inputs.input_ids.shape[1]:].tolist()
        chatml_output_raw = tokenizer.decode(generated_ids, skip_special_tokens=False)
        
        # Extract response before <|im_end|>
        chatml_output = chatml_output_raw.split("<|im_end|>")[0].strip()
        
        logger.info(f"Generated token IDs: {generated_ids[:20]}...")
        logger.info(f"Output (raw):\n{chatml_output_raw[:200]}...")
        logger.info(f"Output (cleaned):\n{chatml_output[:200]}...")
        
        # Compare
        logger.info("\n--- Comparison ---")
        comparison = {
            "prompts_match": chat_template_prompt == chatml_prompt if has_chat_template else None,
            "output_length_chat_template": len(chat_template_output) if chat_template_output else 0,
            "output_length_chatml": len(chatml_output),
            "token_count_chat_template": len(chat_template_tokens) if chat_template_tokens else 0,
            "token_count_chatml": len(chatml_tokens)
        }
        
        # Recommendation
        if not has_chat_template:
            recommendation = "USE_CHATML - No chat_template found, use manual ChatML format"
        elif chat_template_prompt == chatml_prompt:
            recommendation = "FORMATS_MATCH - Both methods produce identical prompts"
        else:
            recommendation = "USE_CHATML - Training used ChatML format, inference should match"
        
        logger.info(f"Recommendation: {recommendation}")
        logger.info("=" * 80)
        
        return DebugPromptResponse(
            query=request.query,
            chat_template_found=has_chat_template,
            chat_template_prompt=chat_template_prompt,
            chat_template_tokens=chat_template_tokens,
            chat_template_output=chat_template_output,
            chatml_prompt=chatml_prompt,
            chatml_tokens=chatml_tokens,
            chatml_output=chatml_output,
            comparison=comparison,
            recommendation=recommendation
        )
        
    except Exception as e:
        logger.error(f"❌ Debug error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("LOCAL MODEL SERVER - Qwen2.5-1.5B-Instruct")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This server runs on your Mac and handles LLM inference.")
    logger.info("The Render backend will call this server via HTTP.")
    logger.info("")
    logger.info("Steps:")
    logger.info("1. Start this server: python3 local_model_server.py")
    logger.info("2. Expose with ngrok: ngrok http 8001")
    logger.info("3. Set LOCAL_MODEL_URL in Render env vars")
    logger.info("")
    logger.info("=" * 80)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
