import os
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel, Field

# --- CONFIGURATION & ENVIRONMENT VALIDATION ---
# Emulates production cloud runtime parameter injection (e.g., AWS Secrets Manager/ECS Env)
UPSTREAM_API_KEY = os.getenv("LLM_PROVIDER_API_KEY", "mock_production_credential_key_xyz123")

logger = logging.getLogger("pii_gateway")
logging.basicConfig(level=logging.INFO)

# --- CORE INTERFACES (Day 2 PII Engine Blueprint) ---
class PIIMaskingEngine:
    def mask_prompt(self, text: str) -> tuple[str, Dict[str, str]]:
        """Your Day 2 backward-sorting engine execution footprint."""
        if "John Doe" in text:
            return "Hello [MASKED_A1B2C3], process this request.", {"[MASKED_A1B2C3]": "John Doe"}
        return text, {}
    
    def rehydrate_response(self, text: str, mapping: Dict[str, str]) -> str:
        """Your Day 2 case-insensitive regex restoration execution footprint."""
        for token, raw_value in mapping.items():
            text = text.replace(token, raw_value)
        return text

engine = PIIMaskingEngine()

# --- MOCK OUTBOUND PROXY ADAPTER ---
async def mock_upstream_llm_proxy_call(masked_prompt: str) -> str:
    """Simulates a non-blocking network I/O round-trip via LiteLLM to an upstream vendor."""
    if not UPSTREAM_API_KEY:
        logger.critical("SECURITY CONFIGURATION ERROR: Upstream API credentials missing.")
        raise RuntimeError("Authentication infrastructure failure.")
        
    await asyncio.sleep(0.4) 
    return "Acknowledged receipt. User [MASKED_A1B2C3] has been verified in system systems."

# --- STATE MANAGED LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = aioredis.ConnectionPool.from_url(
        "redis://localhost:6379", 
        decode_responses=True,
        max_connections=50
    )
    app.state.redis = aioredis.Redis(connection_pool=pool)
    yield
    await app.state.redis.close()
    await pool.disconnect()

app = FastAPI(title="Compliance PII Proxy Gateway", lifespan=lifespan)


# --- REQUEST & RESPONSE PAYLOADS (Edge Case 2: OpenAI Compatibility) ---

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message author (e.g., system, user, assistant)")
    content: str = Field(..., min_length=1, description="The raw text content of the message")

class OpenAICompatibleChatRequest(BaseModel):
    model: str = Field(..., description="Target upstream model identifier (e.g., gpt-4o, claude-3)")
    messages: List[ChatMessage] = Field(..., description="Standard conversational dialogue historical tracking matrix")

class GatewayProxyResponse(BaseModel):
    client_transaction_id: str
    processed_response: str


# --- UNIFIED REVERSE PROXY ENDPOINT ---

@app.post(
    "/v1/chat/completions", 
    response_model=GatewayProxyResponse, 
    status_code=status.HTTP_200_OK
)
async def unified_proxy_gateway(payload: OpenAICompatibleChatRequest, request: Request):
    redis_client: aioredis.Redis = request.app.state.redis
    transaction_id = f"gateway_tx_{uuid.uuid4().hex[:12]}"
    
    # 1. Payload Swapability Translation Layer (Edge Case 2)
    # Extracts the latest inbound user message content out of the standard chat array standard
    user_message = next((msg for msg in reversed(payload.messages) if msg.role == "user"), None)
    if not user_message:
        raise HTTPException(status_code=400, detail="Payload validation failed: No user prompt found in message matrix.")
        
    # Execute masking on the extracted prompt text
    masked_text, token_mapping = engine.mask_prompt(user_message.content)
    
    # Optimization Guard: If clean prompt with zero PII, completely bypass Redis storage path
    if not token_mapping:
        upstream_response = await mock_upstream_llm_proxy_call(masked_text)
        return GatewayProxyResponse(client_transaction_id=transaction_id, processed_response=upstream_response)

    # 2. Strategy B Token Caching
    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            await pipe.hset(transaction_id, mapping=token_mapping)
            await pipe.expire(transaction_id, 300)  # 5-minute fallback safety sweep TTL
            await pipe.execute()
    except (aioredis.RedisError, ConnectionError) as e:
        logger.error(f"FAIL-CLOSED EXCEPTION: Storage tier failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security infrastructure fault. Upstream transmission aborted to prevent data exposure."
        )

    # 3. Guaranteed Lifecycle Execution Block (Edge Case 1 & Return Trap Fixed)
    final_clean_text = ""
    
    try:
        # Outbound Proxy Transit (Non-blocking external network leg using safe text)
        try:
            raw_llm_output = await mock_upstream_llm_proxy_call(masked_text)
        except Exception as e:
            logger.error(f"UPSTREAM ROUTING ERROR: Provider network dropped: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Upstream model engine currently unresponsive. Core gateway operational."
            )

        # In-Memory Rehydration Fusion
        try:
            fetched_mapping = await redis_client.hgetall(transaction_id)
            if not fetched_mapping:
                raise HTTPException(status_code=410, detail="Compliance window expired mid-transit loop.")
                
            # Assigning to out-of-scope variable instead of executing an immediate nested return
            final_clean_text = engine.rehydrate_response(raw_llm_output, fetched_mapping)
            
        except (aioredis.RedisError, ConnectionError) as e:
            logger.error(f"POST-TRANSIT STORAGE FAILURE: Token recovery failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security baseline compromised during rehydration phase."
            )
            
    finally:
        # PROACTIVE CRYPTOGRAPHIC SHREDDING GUARANTEE:
        # The finally block executes no matter what. If the external LLM throws a 502, 
        # or if the code succeeds, we wipe the cache tracking key instantly [INDEX].
        # This completely eliminates orphan token maps leaking into memory on failures.
        logger.info(f"Executing proactive compliance shredding for transaction: {transaction_id}")
        await redis_client.delete(transaction_id)

    # Clean return statement evaluated safely at the root level of the route function [INDEX]
    return GatewayProxyResponse(client_transaction_id=transaction_id, processed_response=final_clean_text)
