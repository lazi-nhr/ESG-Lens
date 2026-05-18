from typing import List, Dict
import logging
import os
import time

from app.core.config import HF_MODEL, HF_HOME

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
        result = _run_local_inference(query, retrieved_docs)
        logger.info(f"Answer generated successfully | length={len(result)} characters")
        logger.info("=== Answer Generation Complete ===")
        return result
    except Exception as e:
        logger.error(f"Local inference failed: {type(e).__name__}: {str(e)}", exc_info=True)
        logger.info("Falling back to placeholder answer")
        return _placeholder_answer(retrieved_docs)

def _run_local_inference(query: str, retrieved_docs: List[Dict]) -> str:
    inference_start = time.time()
    logger.debug("Initializing model and tokenizer...")
    model, tokenizer = _get_model()
    
    # Format context
    logger.debug("Formatting context from retrieved documents...")
    context_parts = []
    for i, doc in enumerate(retrieved_docs[:3], start=1):
        content = doc.get("content", "").strip()[:800]
        context_parts.append(f"Excerpt {i}: {content}")
    context = "\n\n".join(context_parts)
    logger.debug(f"Context prepared: {len(context)} characters from {len(retrieved_docs)} documents")
    
    # Read template
    logger.debug("Loading prompt template...")
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "esg_report.md")
    try:
        with open(prompt_path, "r") as f:
            template = f.read()
        logger.debug(f"Template loaded: {len(template)} characters")
    except Exception as e:
        logger.error(f"Failed to load template from {prompt_path}: {type(e).__name__}: {str(e)}", exc_info=True)
        raise
        
    # Extract company name dynamically out of the query string if possible, or leave a fallback
    company_name = "ABB" if "ABB" in query else ("Roche" if "Roche" in query else "Target Company")
    logger.debug(f"Extracted company name: {company_name}")
    
    formatted_prompt = template.format(company=company_name, criterion="Environmental", context=context)
    logger.debug(f"Prompt formatted: {len(formatted_prompt)} characters")

    # Use modern Chat Templates for instruction alignment
    logger.debug("Building chat messages...")
    messages = [
        {"role": "system", "content": "You are a professional ESG assistant. Generate comprehensive structured reports."},
        {"role": "user", "content": formatted_prompt}
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
    logger.info(f"Total inference time: {total_inference_time:.2f}s (tokenization={tokenize_time:.2f}s, generation={generation_time:.2f}s, decoding={decode_time:.2f}s)")
    
    return answer

def _placeholder_answer(retrieved_docs: List[Dict]) -> str:
    logger.info("Using placeholder answer (fallback)")
    best = retrieved_docs[0]
    doc_id = best.get('id', '?')
    content = best.get("content", "").strip()
    snippet = content[:400] + "..." if len(content) > 400 else content
    logger.debug(f"Placeholder answer from document id={doc_id}, snippet_length={len(snippet)}")
    return f"[Showing best matching document (id={doc_id})]\n\n{snippet}"