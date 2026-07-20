import uuid
import re
from typing import Dict, Tuple
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

class PIIMaskingEngine:
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def mask_prompt(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Scans raw text for PII, replaces found entities with deterministic pseudonyms,
        and returns the anonymised text along with the lookup dictionary.
        """
        if not text.strip():
            return text, {}

        # 1. Analyze text to locate entities
        analysis_results = self.analyzer.analyze(text=text, language="en")
        
        # Local registry to track mappings: Placeholder -> Original Text
        inverted_cache: Dict[str, str] = {}
        # Tracking registry to reuse identical tokens for identical text items
        text_to_token: Dict[str, str] = {}

        # 2. Sort results backward to safely manipulate string positions without offset drift
        sorted_results = sorted(analysis_results, key=lambda x: x.start, reverse=True)
        
        masked_text = text
        for result in sorted_results:
            # Extract the literal raw text that triggered the PII match
            raw_value = text[result.start:result.end]
            
            # Ensure consistent token generation if the same value appears multiple times
            if raw_value not in text_to_token:
                token = f"[MASKED_{uuid.uuid4().hex[:6].upper()}]"
                text_to_token[raw_value] = token
                inverted_cache[token] = raw_value
            else:
                token = text_to_token[raw_value]
                
            # Replace the precise slice of PII text with our token
            masked_text = masked_text[:result.start] + token + masked_text[result.end:]

        return masked_text, inverted_cache


    def rehydrate_response(self, text: str, token_mapping: Dict[str, str]) -> str:
        """
        Replaces safe pseudonyms inside an LLM response back with original PII,
        ensuring case insensitivity to handle LLM capitalization quirks.
        """
        rehydrated_text = text
        
        # Loop over each token-to-PII pair in our inversion mapping
        for token, original_value in token_mapping.items():
            # Escape the token characters (in case your token uses special regex chars like [ or ])
            escaped_token = re.escape(token)
            
            # Compile a regex pattern that ignores casing entirely
            pattern = re.compile(escaped_token, re.IGNORECASE)
            
            # Replace any variation of the token with the correct, original PII string
            rehydrated_text = pattern.sub(original_value, rehydrated_text)
            
        return rehydrated_text

