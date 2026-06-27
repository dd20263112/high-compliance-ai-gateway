# ADR 001: Selection of Cache Tier for Ephemeral PII Token Mapping

## Context and Problem Statement

Our application handles high-risk Personally Identifiable Information (PII) tokens that must be mapped dynamically during real-time LLM streaming responses. 

To eliminate the compliance blast radius of a persistent storage breach, transient PII tokens must leave zero permanent disk footprint. Real-time LLM streaming requires microsecond lookup performance. 

Because disk-backed structures (SQL/NoSQL) introduce prohibitive latency and prolonged data-exposure windows, an ephemeral, volatile, in-memory data store is an architectural baseline requirement. The practical evaluation is narrowed to the industry-standard memory caches: Redis and Memcached.

## Decision Drivers

* **Strict TTL Enforcement:** Expired keys must be strictly inaccessible immediately upon API request lifecycle completion.
* **Memory Management Predictability:** Avoid unpredictable cache eviction or memory fragmentation under highly dynamic payloads.
* **Data Structure Support:** Efficiently querying or grouping token mappings without heavy client-side serialization overhead.

## Decision Outcome

**Chosen option:** Redis (specifically deploying an ephemeral configuration with persistence explicitly disabled).

### Rationale

While both systems deliver the necessary sub-millisecond streaming speeds, Redis is selected due to how it handles data eviction and structure overhead:

* **Deterministic Eviction:** Memcached uses passive, "lazy" expiration (items are only truly purged when requested or when memory fills up, risking stale data lingering in RAM). Redis combines lazy expiration with an active background sweeping cron, providing a more reliable timeline for PII destruction.
* **Rich Data Primitives:** Redis allows us to use Hashes or Sets to group multiple PII tokens under a single request ID transaction. Memcached only supports flat strings, which would force us to handle complex serialization on the application side.
* **Licensing Context:** While Redis 8+ uses an AGPLv3/SSPL license model, our architecture utilizes standard cloud-managed infrastructure (e.g., AWS ElastiCache / Google Cloud Memorystore), meaning native cloud compliance abstracts the license friction for our proprietary application layer.

## Alternatives Considered

### Memcached

* **Pros:** Multi-threaded architecture out-of-the-box can edge out single-threaded Redis on raw string processing; incredibly lightweight memory footprint per key.
* **Cons:** Slab allocation algorithm can suffer from severe memory fragmentation if token sizes vary wildly over time. Lack of complex data structures forces bad application-side hacks to group tokens.

### Valkey

* **Pros:** Fully open-source Linux Foundation fork of Redis maintaining the permissive BSD license.
* **Cons:** Excellent alternative, but bypassed for this iteration purely to lower onboarding friction for standard cloud vendor infrastructure deployments, though we retain it as our primary fallback path.
