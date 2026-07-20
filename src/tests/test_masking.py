import pytest
from app.masking import PIIMaskingEngine

@pytest.fixture
def engine():
    return PIIMaskingEngine()

def test_mask_and_rehydrate_lifecycle(engine):
    # Prepare a realistic raw client enterprise prompt
    raw_prompt = "Hello, my name is John Doe and my email is john.doe@example.com. Please review my file."
    
    # Execute Masking Engine
    masked_text, token_map = engine.mask_prompt(raw_prompt)
    
    # Assertions: Verify data leakage is completely mitigated
    assert "John Doe" not in masked_text    
    assert "john.doe@example.com" not in masked_text
    assert "[MASKED_" in masked_text
    
    # Assertions: Verify mapping integrity targeted items exist
    assert any(val == "John Doe" for val in token_map.values())
    assert any(val == "john.doe@example.com" for val in token_map.values())
    
    # Extract keys safely for token verification
    john_token = next(k for k, v in token_map.items() if v == "John Doe")
    email_token = next(k for k, v in token_map.items() if v == "john.doe@example.com")
    
    mock_llm_reply_with_tokens = f"Assigned task to {john_token} and sent confirmation to {email_token}."
    
    # Execute Re-hydration Engine
    final_output = engine.rehydrate_response(mock_llm_reply_with_tokens, token_map)
    
    # Assertions: Verify real data successfully restored for client delivery
    assert "John Doe" in final_output
    assert "john.doe@example.com" in final_output
    assert "[MASKED_" not in final_output


def test_production_edge_cases(engine):
    # --- EDGE CASE 1: Duplicate Entities ---
    # Does your engine reuse the same token, or does it waste memory/tokens?
    dup_prompt = "My name is John Doe. Please tell John Doe to call me."
    masked_dup, map_dup = engine.mask_prompt(dup_prompt)
    
    # Architect Question: How many unique keys should be in the map?
    # If the same name has 2 different tokens, you are leaking memory and confusing the LLM.
    assert len(map_dup) == 1, "Fail: Engine created duplicate tokens for the exact same entity value!"


    # --- EDGE CASE 2: LLM Casing Alteration ---
    # LLMs frequently hallucinate or alter token casing (e.g., [MASKED_A] -> [masked_a]).
    # Does your rehydration strategy survive lowercase changes?
    borked_llm_response = "Hello [masked_a], your request is processed."
    # We simulate your inverted cache map
    mock_map = {"[MASKED_A]": "John Doe"} 
    
    final_output = engine.rehydrate_response(borked_llm_response, mock_map)
    assert "John Doe" in final_output, "Fail: Rehydration is case-sensitive and failed to restore PII!"


 

