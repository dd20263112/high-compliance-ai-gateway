# ADR 003: String Rehydration Strategy for Case-Insensitive LLM Alterations

## Context and Problem Statement

When processing responses from generative Large Language Models (LLMs), the gateway must substitute secure placeholder tokens (e.g., `[MASKED_A1B2C3]`) back into their original Personally Identifiable Information (PII) data points before returning the payload to the client application.

During production testing, we observed that LLMs frequently alter token casing, capitalization, or formatting when generating responses (e.g., converting an upper-case placeholder `[MASKED_A1B2C3]` to lower-case `[masked_a1b2c3]`). 

Standard string replacement methods (such as Python's `str.replace()`) are strictly case-sensitive. When the LLM mutates token case, these standard string methods fail silently, leaving the raw placeholder exposed to the client and failing to restore the customer's PII. We need a robust string transformation strategy that guarantees PII restoration regardless of LLM capitalization quirks.

## Decision Drivers

* **Deterministic Recovery:** Guarantee that 100% of hidden PII is successfully restored even if the LLM alters token casing.
* **Format Preservation:** Ensure that the original layout, formatting, and syntax of the LLM's response are not modified or degraded during the restoration phase.
* **Runtime Efficiency:** Minimise CPU overhead and memory allocation penalties inside the high-throughput response rehydration loop.

## Decision Outcome

**Chosen option:** Compiled regular expressions using Python's `re.compile()` paired with the `re.IGNORECASE` flag and evaluated via `pattern.sub()`.

### Rationale

Using case-insensitive compiled regular expressions perfectly balances compliance safety with runtime performance requirements:

* **Case Resilience:** The `re.IGNORECASE` flag ensures that variations like `[MASKED_A]`, `[masked_a]`, and `[Masked_A]` are all successfully matched against the lookup key, eliminating silent data restoration failures.
* **Syntax Protection:** Characters inside our custom tokens (such as square brackets `[` and `]`) are explicitly escaped using `re.escape()`. This prevents the regex engine from misinterpreting token wrappers as regex character classes.
* **Targeted Mutation:** Unlike global text normalization, `pattern.sub()` only mutates the matched token string. The rest of the LLM's generated response remains completely untouched, preserving its original casing, formatting, and grammar.

## Alternatives Considered

### Global Text Lowercasing (`.lower()` Normalization)

* **Pros:** Highly performant; allows simple case-insensitive matching using low-overhead string primitives.
* **Cons:** Completely destroys the original casing and stylistic format of the LLM's response before returning it to the user (e.g., turning formal sentences entirely lower-case), which degrades the user experience.

### Standard `str.replace()` with Multi-Case Matrix Lookups

* **Pros:** Fastest native execution speed within the Python standard library.
* **Cons:** Fails to scale. It forces the application layer to guess and execute replacements for every possible casing permutation (`.upper()`, `.lower()`, `.title()`) for every token in the map. This increases code complexity and incurs repetitive string scanning loops over large payloads.