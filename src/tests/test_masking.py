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
