# ADR 002: Selection of NLP Engine and Model Tier for PII Identification

## Context and Problem Statement

The AI Gateway must intercept incoming prompt text and accurately flag Personally Identifiable Information (PII) before it transits to external LLM providers. 

Because unstructured user prompts can contain highly varied syntactical structures, simple Regular Expressions (Regex) are insufficient for catching names, locations, and unstructured entities. We require a Named Entity Recognition (NER) engine. 

However, running heavy deep-learning NLP models directly within our API request-response loop introduces a massive architectural trade-off between **identification accuracy**, **CPU/Memory utilization**, and **per-request latency overhead**. We must select and configure an NLP framework that minimizes latency while maintaining high precision.

## Decision Drivers

* **Latency Budget:** The PII analysis phase must not add more than 30–50ms of overhead to the total request lifecycle.
* **Deterministic Resource Consumption:** The engine must fit cleanly inside containerized environments (Docker/Kubernetes) without causing out-of-memory (OOM) crashes under concurrent loads.
* **Data Sovereignty:** The token scanning process must occur completely locally on our infrastructure. No text can be sent to a third-party API (e.g., Google Cloud DLP) to find the PII.

## Decision Outcome

**Chosen option:** Microsoft Presidio Analyzer using the `en_core_web_sm` (Small) spaCy pipeline, augmented by stateless compilation hooks.

### Rationale

Microsoft Presidio abstracts the underlying NER framework and allows us to swap models seamlessly. We selected the small spaCy model over larger alternatives for the following critical operational reasons:

* **Resource Footprint:** The `en_core_web_sm` model loads completely into ~50MB of RAM, whereas transformer-based models (like RoBERTa or custom Hugging Face pipelines) require 1GB+ of RAM and often necessitate expensive GPU infrastructure to meet our latency budgets.
* **Execution Speed:** In localized testing, the small spaCy engine processes standard prompts (<2000 tokens) in under 15ms on standard cloud CPU compute nodes, leaving the vast majority of our latency budget available for the subsequent LLM generation phase.
* **Extensibility via Code:** Presidio allows us to layer deterministic, high-speed Regex and Context Recognizers directly on top of the statistical spaCy model. This ensures we can catch highly specific patterns (like corporate API keys or internal tracking numbers) at execution speed without needing to retrain heavy ML models.

## Alternatives Considered

### Hugging Face Transformers (RoBERTa-NER / BERT)

* **Pros:** Exceptionally high accuracy and context awareness; significantly fewer false negatives on complex or intentionally obscured PII.
* **Cons:** Prohibitive operational costs. Requires massive container image footprints, slow cold-start times in auto-scaling groups, and introduces an average latency overhead of 150ms+ per request on standard CPU hardware.

### Google Cloud Data Loss Prevention (DLP) API

* **Pros:** Zero local infrastructure management; highly mature, enterprise-grade classification out of the box.
* **Cons:** Complete violation of our core privacy pillar. Sending unmasked text to a third-party cloud endpoint to check for PII introduces an intermediate data-exposure window and creates a secondary compliance boundary.
