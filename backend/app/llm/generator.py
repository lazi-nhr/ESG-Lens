from typing import List, Dict
import logging
import time
import aiohttp

from app.core.config import HF_MODEL, HF_API_MODEL, HF_API_KEY, HF_HOME

logger = logging.getLogger(__name__)

# 1. Update the model target
MODEL_NAME = HF_MODEL
CACHE_DIR = HF_HOME
_model = None
_tokenizer = None

def _get_model():
    global _model, _tokenizer
    if _model is None:
        # Changed to Auto classes for decoder-only architectures
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        logger.info("=== Model Loading Started ===")
        logger.info(f"Model: {MODEL_NAME}")
        logger.info(f"Cache directory: {CACHE_DIR}")
        
        load_start = time.time()
        
        try:
            logger.info("Loading tokenizer...")
            tokenizer_start = time.time()
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=CACHE_DIR)
            tokenizer_time = time.time() - tokenizer_start
            logger.info(f"Tokenizer loaded in {tokenizer_time:.2f}s")
            
            logger.info("Loading model...")
            model_start = time.time()
            _model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME, 
                cache_dir=CACHE_DIR, 
                device_map="auto",  # automatically selects device (GPU or CPU)
                torch_dtype="auto"
            )
            model_time = time.time() - model_start
            logger.info(f"Model loaded in {model_time:.2f}s")
            
            # Log device information
            if hasattr(_model, 'device'):
                logger.info(f"Model device: {_model.device}")
            else:
                # For models with multiple devices
                devices = set()
                for param in _model.parameters():
                    devices.add(str(param.device))
                logger.info(f"Model devices: {devices}")
            
            param_count = _model.num_parameters()
            logger.info(f"Model parameters: {param_count:,}")
            logger.info(f"Total load time: {time.time() - load_start:.2f}s")
            logger.info("=== Model Loading Complete ===")
            
        except Exception as e:
            logger.error(f"Model loading failed: {type(e).__name__}: {str(e)}", exc_info=True)
            raise
    
    return _model, _tokenizer

async def generate_answer(query: str, retrieved_docs: List[Dict]) -> str:
    logger.info("=== Answer Generation Started ===")
    logger.info(f"Query: {query[:100]}..." if len(query) > 100 else f"Query: {query}")
    logger.info(f"Documents available: {len(retrieved_docs)}")
    
    if not retrieved_docs:
        logger.warning("No documents retrieved - returning fallback response")
        return "No relevant documents found in the database."
    
    try:
        logger.info("Attempting local inference...")
        result = await _run_local_inference(query, retrieved_docs)
        logger.info(f"Local inference successful | answer_length={len(result)} characters")
        logger.info("=== Answer Generation Complete ===")
        return result
    except Exception as e:
        logger.warning(f"Local inference failed: {type(e).__name__}: {str(e)}")
        
        # Fallback to HF Inference API if configured
        if HF_API_KEY:
            try:
                logger.info("Falling back to HF Inference API...")
                result = await _call_hf_api(query, retrieved_docs)
                logger.info(f"HF API inference successful | answer_length={len(result)} characters")
                logger.info("=== Answer Generation Complete (via HF API) ===")
                return result
            except Exception as api_error:
                logger.error(f"HF API also failed: {type(api_error).__name__}: {str(api_error)}")
        else:
            logger.warning("HF_API_KEY not configured, cannot fallback to API")
        
        # Final fallback to placeholder
        logger.info("Using placeholder answer")
        return _placeholder_answer(retrieved_docs)

async def _run_local_inference(query: str, retrieved_docs: List[Dict]) -> str:
    """
    Run local inference using the loaded model and tokenizer.
    
    Args:
        query: The user's question.
        retrieved_docs: List of similar documents.
    
    Returns: LLM-generated answer.
    """
    inference_start = time.time()
    logger.debug("Initializing model and tokenizer...")
    model, tokenizer = _get_model()
    
    # Format context from retrieved documents
    logger.debug("Formatting context from retrieved documents...")
    context_parts = []
    for i, doc in enumerate(retrieved_docs[:3], start=1):
        content = doc.get("content", "").strip()[:800]
        context_parts.append(f"Excerpt {i}: {content}")
    context = "\n\n".join(context_parts)
    logger.debug(f"Context prepared: {len(context)} characters from {len(retrieved_docs)} documents")

    # Build messages for the model
    logger.debug("Building chat messages...")
    messages = [
        {"role": "system", "content": "You are a professional ESG assistant. Generate comprehensive structured reports based on the provided documents."},
        {"role": "user", "content": f"Based on the following documents, provide a professional ESG evaluation response.\n\nDocuments:\n{context}\n\nQuestion: {query}\n\nResponse:"}
    ]
    logger.debug(f"Messages prepared: {len(messages)} messages")
    
    logger.debug("Applying chat template...")
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    logger.debug(f"Chat template applied: {len(text)} characters")
    
    logger.debug("Tokenizing input...")
    tokenize_start = time.time()
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    tokenize_time = time.time() - tokenize_start
    input_tokens = model_inputs.input_ids.shape[1]
    logger.info(f"Input tokenized in {tokenize_time:.2f}s | tokens={input_tokens}")
    
    # Generate with specified parameters
    logger.info("Starting generation (max_new_tokens=800, temperature=0.3)...")
    generation_start = time.time()
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=800, 
        temperature=0.3,  # Lower temperature prevents hallucinating metrics
        do_sample=True
    )
    generation_time = time.time() - generation_start
    output_tokens = generated_ids.shape[1] - input_tokens
    logger.info(f"Generation completed in {generation_time:.2f}s | output_tokens={output_tokens}")
    
    # Trim prompt tokens from output
    logger.debug("Decoding generated tokens...")
    generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
    decode_start = time.time()
    answer = tokenizer.decode(generated_ids[0], skip_special_tokens=True).strip()
    decode_time = time.time() - decode_start
    logger.debug(f"Decoding completed in {decode_time:.2f}s | answer_length={len(answer)}")
    
    total_inference_time = time.time() - inference_start
    logger.info(f"Total local inference time: {total_inference_time:.2f}s (tokenization={tokenize_time:.2f}s, generation={generation_time:.2f}s, decoding={decode_time:.2f}s)")
    
    return answer


async def _call_hf_api(query: str, retrieved_docs: List[Dict]) -> str:
    """
    Fallback: Call Hugging Face Inference API for answer generation.
    Used when local inference fails and HF_API_KEY is configured.
    
    Args:
        query: The user's question.
        retrieved_docs: List of similar documents.
    
    Returns: LLM-generated answer from HF API.
    """
    logger.info(f"HF API Model: {HF_API_MODEL}")
    
    # Build context
    context_parts = []
    for i, doc in enumerate(retrieved_docs[:3], start=1):
        content = doc.get("content", "").strip()[:500]
        context_parts.append(f"Document {i}: {content}")
    context = "\n\n".join(context_parts)
    
    # Build prompt
    prompt = f"""You are a professional ESG assistant. Based on the following documents, provide a professional ESG evaluation response.

Documents:
{context}

Question: {query}

Response:"""
    
    # Call HF Inference API
    api_url = f"https://api-inference.huggingface.co/models/{HF_API_MODEL}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 500}}
    
    logger.debug(f"Calling HF API: {api_url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                logger.debug(f"HF API response status: {resp.status}")
                if resp.status == 200:
                    result = await resp.json()
                    # HF returns list of dicts with 'generated_text'
                    if isinstance(result, list) and len(result) > 0:
                        generated = result[0].get("generated_text", "").strip()
                        logger.debug(f"HF API generated: {len(generated)} characters")
                        return generated
                    logger.warning(f"Unexpected HF API response format: {result}")
                    return str(result)
                else:
                    error_text = await resp.text()
                    logger.error(f"HF API error ({resp.status}): {error_text}")
                    raise Exception(f"HF API error ({resp.status}): {error_text}")
    except aiohttp.ClientError as e:
        logger.error(f"Failed to connect to HF API: {type(e).__name__}: {str(e)}")
        raise


def _placeholder_answer(retrieved_docs: List[Dict]) -> str:
    logger.info("Using placeholder answer (fallback)")
    best = retrieved_docs[0]
    doc_id = best.get('id', '?')
    content = best.get("content", "").strip()
    snippet = content[:400] + "..." if len(content) > 400 else content
    logger.debug(f"Placeholder answer from document id={doc_id}, snippet_length={len(snippet)}")
    return f"[Showing best matching document (id={doc_id})]\n\n{snippet}"