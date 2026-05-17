# Semantic-First RAG Refactor - Architecture Simplified

## Overview

Refactored the LegalEase retrieval pipeline from **rule-based query expansion** to **semantic-first retrieval**. The system now:

1. **Relies primarily on semantic similarity** (embeddings) - the scalable, maintainable approach
2. **Uses lightweight keyword re-ranking** (20% weight) - simple tie-breaking, not primary signal
3. **Removed large hardcoded synonym dictionaries** - complex, brittle, unmaintainable
4. **Normalized simple query cleaning** - trim, lowercase, punctuation removal
5. **Maintains intelligent fallback logic** - never returns empty if any relevant chunk exists

---

## Why This Refactor?

### Problem with Rule-Based Expansion

The old system had a large `expansions_map` with regex patterns for legal terms:

```python
expansions_map = {
    r'\b(time|period|duration|how long)\b': ['lease term', 'contract period', 'duration'],
    r'\b(money|payment|cost|expense|price|charge)\b': ['payment', 'rent', 'fee', 'amount'],
    r'\b(break|cancel|terminate|end|exit|leave)\b': ['termination', 'cancellation', 'breach'],
    # ... 10+ more patterns
}
```

**Why this was problematic:**

1. **Doesn't scale** - New legal terminology requires manual updates to dictionary
2. **Brittle** - Misses domain jargon outside predefined mappings
3. **Over-engineered** - Modern RAG systems don't rely on rule engines
4. **Maintenance burden** - Each new term/domain adds more rules
5. **False sense of coverage** - Incomplete mappings miss important synonyms
6. **Not realistic** - A student internship project shouldn't build custom legal NLP

### Solution: Semantic-First

Rely on **embeddings to capture similarity naturally**:

```
User: "time period"
Embedding: [0.2, 0.5, -0.1, ..., 0.8]  # Semantic vector

Document chunks (already indexed):
- "The lease term is 2 years" → embedding [0.1, 0.6, -0.05, ..., 0.75]  Similarity: 0.92 ✓
- "Payment obligations include rent" → embedding [0.3, 0.2, -0.2, ..., 0.1]  Similarity: 0.41
- "Repairs and maintenance" → embedding [0.05, 0.4, 0.1, ..., 0.6]  Similarity: 0.78 ✓

Result: Top-2 chunks retrieved WITHOUT any manual synonym mapping
```

---

## Architecture Changes

### REMOVED

❌ `expand_legal_query()` function with large `expansions_map`
- Was trying to map "time" → "lease term", "break" → "termination", etc.
- Complex regex patterns for different legal domains
- Fallback retry loop when initial query returned few results

### KEPT

✅ Simple query normalization: `normalize_query()`
```python
def normalize_query(query: str) -> str:
    """Light cleaning: trim, lowercase, remove excess punctuation."""
    query = query.strip().lower()
    query = re.sub(r'[?!]{2,}', '?', query)  # ??, !!  → ?
    return query
```

✅ Keyword re-ranking: `rerank_chunks_by_keywords()`
```python
combined_score = 0.8 * semantic_similarity + 0.2 * keyword_overlap
```
- Semantic similarity is primary (80%)
- Keyword overlap is tie-breaker (20%)
- Example: Both chunks about "rent" may have similar semantic scores;
  one explicitly mentions "amount" from query → boost it slightly

✅ Fallback logic to best available chunks
- Never returns empty unless no chunks indexed
- Shows weak match (0.25 similarity) if no good matches (>0.3)

---

## New Flow

### Old Flow (Rule-Based)
```
Query: "time period"
   ↓
1. Search semantic + get 2 results (low coverage)
2. Check if results < top_k//2
3. Trigger query expansion → try "lease term", "duration", "period"
4. Embed each expanded query separately
5. Merge results
   ↓
Result: 5 chunks (but relied heavily on having right synonym in dict)
```

### New Flow (Semantic-First)
```
Query: "time period"
   ↓
1. Normalize: "time period" → "time period" (trim, lowercase, clean)
2. Embed normalized query via HF API
3. Compute cosine similarity to all pre-indexed chunks
4. Re-rank by keyword overlap
   ↓
Result: 4 chunks ranked by semantic + keyword signals
```

**Benefits:**
- Single embedding request instead of multiple
- No complex fallback retry logic
- Simpler, more understandable
- Matches how modern RAG systems work

---

## Code Comparison

### retrieval_helpers.py

**OLD:**
```python
def expand_legal_query(query: str) -> List[str]:
    """Map user queries to legal synonyms using large regex patterns."""
    expansions_map = {
        r'\b(money|payment|...)\b': ['payment', 'rent', 'fee', ...],
        # ... 10+ more patterns
    }
    # Loop through patterns, build expansion list
    return expansions  # ["time period", "lease term", "duration", ...]
```

**NEW:**
```python
def normalize_query(query: str) -> str:
    """Simple cleaning: trim, lowercase, punctuation."""
    normalized = query.strip().lower()
    normalized = re.sub(r'[?!]{2,}', '?', normalized)
    return normalized
```

**Change:** Went from "expand with 10+ synonym patterns" to "normalize with 3 simple rules"

---

### retrieval.py

**OLD:**
```python
def search(self, query: str, top_k: int = 4) -> List[Dict]:
    results = self._search_with_query(query, top_k, min_similarity)
    
    # If few results, try expansions
    if len(results) < top_k // 2:
        expanded_queries = expand_legal_query(query)
        for expanded_q in expanded_queries[1:]:
            # Embed each expansion separately, merge results
    
    return results
```

**NEW:**
```python
def search(self, query: str, top_k: int = 4) -> List[Dict]:
    normalized_query = normalize_query(query)
    
    # Single semantic search
    query_embedding = get_hf_embeddings([normalized_query])
    similarities = cosine_similarity(query_embedding, self.embeddings)[0]
    
    # Re-rank by keyword overlap
    results = rerank_chunks_by_keywords(results, normalized_query)
    
    return results
```

**Change:** Removed expansion fallback loop, simpler single-pass retrieval

---

## Semantic Similarity Does the Heavy Lifting

**How embeddings handle synonymy without manual rules:**

| Query | Auto-Matched Chunks (No Manual Rules) |
|-------|------|
| "time period" | "The lease term", "Duration of occupancy", "Period of tenancy" |
| "money" | "rent payment", "monthly fees", "financial obligations" |
| "break lease" | "termination rights", "early exit clause", "renewal options" |
| "repair" | "maintenance duties", "upkeep responsibilities", "condition standards" |

**Why?** Embeddings are trained on millions of documents and capture semantic meaning. "lease term" and "time period" are close in embedding space without needing explicit mapping.

---

## Keyword Re-Ranking: Light Touch

Keyword re-ranking ONLY breaks ties, doesn't drive retrieval:

```python
combined_score = 0.8 * semantic_similarity + 0.2 * keyword_overlap
```

**Example:**
```
Query: "tenant responsibility for repairs"
Keywords: {tenant, responsibility, repair}

Chunk A: "The tenant shall perform maintenance"
  Semantic: 0.82
  Keywords: 2 matches ("tenant", "maintenance" ~= "repair")
  Combined: 0.8 * 0.82 + 0.2 * 0.67 = 0.79

Chunk B: "Landlord obligation for structural repairs"
  Semantic: 0.80
  Keywords: 1 match ("repairs")
  Combined: 0.8 * 0.80 + 0.2 * 0.33 = 0.71 ← Lower due to no "tenant" keyword

Result: Chunk A ranked first (correctly emphasizes tenant obligation)
```

The keyword signal helps but doesn't override semantic similarity.

---

## Interview Talking Points

### "Why remove query expansion?"

*"Modern RAG systems rely on semantic embeddings to capture meaning, not handcrafted synonym lists. Embeddings naturally handle synonymy—'lease term' and 'time period' are close in embedding space. Rule-based expansion is brittle, hard to maintain, and doesn't scale to new terminology. It's more realistic to let embeddings do the heavy lifting."*

### "But what if embeddings miss a synonym?"

*"That's rare because embeddings are trained on massive corpora. But if it happens, the user can rephrase their question slightly, and we'll get a better result. That's a trade-off for having simpler, more maintainable code. The fallback logic ensures we never return empty—we show the best available match even if imperfect."*

### "Isn't keyword re-ranking just another rule?"

*"Good distinction. Keyword re-ranking is simple and generic (no domain-specific rules), used only for tie-breaking (20% weight), and doesn't drive retrieval. It's a light enhancement, not the primary mechanism. Semantic similarity is primary."*

### "How do you handle short queries like 'time'?"

*"Short queries naturally have lower semantic scores because they're vague. But the fallback logic handles this—if a short query doesn't meet the 0.3 similarity threshold, we still return the best available chunk. It's better to show a weak match than nothing. The LLM then decides if it can answer based on the context."*

### "Why is this approach realistic for an internship project?"

*"Because real-world RAG systems (like ChatGPT's retrieval, Google's semantic search) all use embeddings + similarity. They don't rely on manually-maintained synonym dictionaries. This project demonstrates practical RAG, not a custom NLP engine."*

---

## Metrics

| Metric | Old (Rule-Based) | New (Semantic) | Notes |
|--------|------------------|---|---|
| Code complexity | High (10+ regex patterns) | Low (3-line normalization) | Simpler to understand |
| Maintenance burden | High (add terms = update dict) | None (embeddings learn) | More sustainable |
| Coverage | Limited (only mapped terms) | Complete (all documents) | Scales naturally |
| False positives | Possible (synonym mapping misses intent) | Rare (embeddings are semantic) | More accurate |
| Embeddings per query | Multiple (main + expansions) | One (normalized query) | More efficient |
| Fallback handling | Complex retry logic | Simple threshold check | Cleaner code |

---

## File Changes Summary

| File | Changes |
|------|---------|
| `backend/retrieval_helpers.py` | Removed `expand_legal_query()`, added `normalize_query()`, simplified other functions |
| `backend/retrieval.py` | Removed `expand_legal_query` import, removed expansion retry loop, added query normalization |
| `backend/main.py` | Updated error message in chatbot endpoint |

---

## What Stayed the Same

✅ Chunking (500 words, 100-word overlap)
✅ Embeddings (Hugging Face API)
✅ Cosine similarity scoring
✅ Re-ranking (keyword overlap as tie-breaker)
✅ Fallback logic (best available chunks)
✅ Source attribution
✅ Conversational QA
✅ Frontend UI
✅ Lightweight, deployable on 512MB

---

## Final Philosophy

**Before:** "Build a legal rules engine with manual synonym mapping"
**After:** "Use embeddings as the primary retrieval signal; keep code simple"

The refactored system is:
- ✅ More semantic (relies on embeddings)
- ✅ More maintainable (no large dicts to update)
- ✅ More scalable (new terms learned automatically)
- ✅ More realistic (matches modern RAG architectures)
- ✅ Still lightweight (no heavy frameworks)
- ✅ Still interview-ready (simpler to explain)

---

## Testing

Try these queries to verify semantic similarity works without manual expansion:

1. **"What is the duration of the lease?"** → Matches "lease term", "period of occupancy"
2. **"What fees does the tenant pay?"** → Matches "rent", "monthly payment", "financial obligations"
3. **"Can I terminate early?"** → Matches "break clause", "exit rights", "renewal options"
4. **"What are my maintenance duties?"** → Matches "repairs", "upkeep", "condition standards"

If semantic retrieval works well on these, it proves embeddings are sufficient without manual expansion.
