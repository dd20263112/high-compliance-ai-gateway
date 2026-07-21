# ADR 004: Redis Lifecycle State and Token Storage Strategy

## Status
Accepted

## Context
Our PII Masking Engine outputs an inverted dictionary map of tokens to original sensitive string values (e.g., `{"[MASKED_A1B2]": "John Doe"}`). To keep the API Gateway completely stateless and horizontally scalable, this context must be offloaded to an external cache tier during the LLM round-trip execution window. We evaluated two core architectural patterns for mapping this token state inside Redis memory while balancing network efficiency and high-compliance privacy regulations.

### Evaluated Alternatives
1. **Strategy A (Flat Global Keys):** Storing every individual token as a standalone string key directly in Redis global namespace (e.g., `SET [MASKED_A1B2] "John Doe" EX 300`).
2. **Strategy B (Isolated Hash Maps):** Generating a short, unique transaction tracking identifier (`tx_id`) per request and wrapping all mutated token vectors inside a single grouped Redis Hash data structure (e.g., `HSET tx_83921a [MASKED_A1B2] "John Doe"`), setting an absolute expiration on the parent hash key.

## Decision
We selected **Strategy B (Isolated Hash Maps)** combined with a managed async lifespan connection pool lifecycle.

## Architectural Justification

### 1. Network I/O Efficiency (Microsecond Scale Optimization)
Under Strategy A, if an enterprise prompt contains multiple PII fragments, the gateway is forced to execute an equal number of consecutive network commands over the wire to persist or retrieve keys. This scales network latency linearly ($O(N)$ network operations). Strategy B collapses this lifecycle down to **exactly one inbound and one outbound round-trip** using native Redis `hset` and `hgetall` commands. The actual string replacement loop then happens inside local app container RAM at pure in-memory compute speeds.

### 2. Elimination of Multi-Tenant Namespace Collisions
Our short-token algorithm leverages random permutations. Under massive global scale handling millions of parallel corporate data streams, Strategy A introduces a mathematical reality of token collision (The Birthday Paradox). If two discrete enterprise users are concurrently assigned an identical token string, one will silently overwrite the other in a flat global namespace. Strategy B isolates token scopes cleanly inside a unique parent Transaction ID partition, preventing cross-tenant privacy leaks entirely.

### 3. Atomic Compliance Shredding (Zero-Footprint Integrity)
High-compliance frameworks require deterministic data destruction. Persisting 5 distinct global flat keys requires tracking and setting 5 separate TTL timers. A transient network partition or memory eviction mid-transaction can result in partial writes—leaving orphaned PII data permanently lingering in cache memory. With Strategy B's Hash structure, Redis's internal engine handles the expiration atomically. When the parent `tx_id` hits zero, the entire nested data topology is instantly and securely dropped.

### 4. Fail-Closed Resilience Stance
If the Redis cluster experiences an outage, our code catches the `aioredis.RedisError` exception and deliberately intercepts the execution thread to throw an `HTTP 503 Service Unavailable` error back to the client app. While a junior implementation might "fail-open" and pass the unmasked prompt straight to an LLM provider to protect application uptime, a compliance-focused gateway must treat data leak prevention as the absolute highest priority. No unmasked data is permitted to escape our system perimeter if the safety tier goes offline.
