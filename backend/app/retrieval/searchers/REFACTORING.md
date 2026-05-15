# Refactoring: Hybrid Search Architecture

## Changes

The hybrid search has been refactored from a monolithic `HybridRetriever` class into modular, composable search components:

### Before (Monolithic)
```python
class HybridRetriever:
    def build_index(self)
    def bm25_search(...)      # Internal method
    def pgvector_search(...)  # Internal method
    def hybrid_search(...)    # Main method
    def hybrid_search_with_details(...)
```

### After (Modular)
```
searchers/
├── base.py         # BaseSearcher abstract class
├── vector.py       # VectorSearcher
├── keyword.py      # BM25Searcher
├── hybrid.py       # HybridSearcher (composes both)
└── __init__.py     # Exports
```

## New Classes

### BaseSearcher (Abstract)
```python
from app.retrieval.searchers import BaseSearcher

class BaseSearcher(ABC):
    def search(query: str, top_k: int) -> List[Dict]
    def build_index()
    def refresh_index()
```

### VectorSearcher
```python
from app.retrieval.searchers import VectorSearcher

searcher = VectorSearcher()
results = searcher.search("query", top_k=5)
# Returns: [{...doc..., 'similarity': 0.85}, ...]
```

### BM25Searcher (Keyword)
```python
from app.retrieval.searchers import BM25Searcher

searcher = BM25Searcher()
results = searcher.search("query", top_k=5)
# Returns: [{...doc..., 'bm25_score': 12.5}, ...]
```

### HybridSearcher
```python
from app.retrieval.searchers import HybridSearcher

# Using default searchers
searcher = HybridSearcher(enable_reranking=True)
results = searcher.search("query", top_k=5)

# Or with custom searchers
vector = VectorSearcher()
bm25 = BM25Searcher()
searcher = HybridSearcher(
    vector_searcher=vector,
    bm25_searcher=bm25,
    enable_reranking=True
)
```

## Migration Guide

### Option 1: Use New Modular Classes (Recommended)

```python
# Old
from app.retrieval.hybrid_search import HybridRetriever
retriever = HybridRetriever()
results = retriever.hybrid_search(query)

# New
from app.retrieval.searchers import HybridSearcher
searcher = HybridSearcher()
results = searcher.search(query)
```

### Option 2: Keep Using HybridRetriever (Backward Compatible)

```python
# Still works - HybridRetriever is an alias to HybridSearcher
from app.retrieval.hybrid_search import HybridRetriever
retriever = HybridRetriever()
results = retriever.hybrid_search(query)
```

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Reusability** | Can only use via HybridRetriever | Use individual searchers separately |
| **Testing** | Hard to unit test | Each searcher independently testable |
| **Flexibility** | Fixed implementation | Easy to swap implementations |
| **Clarity** | Mixed concerns | Single responsibility per class |
| **Extension** | Hard to extend | Easy to create new searchers |

## Examples

### Use Only Vector Search
```python
from app.retrieval.searchers import VectorSearcher

searcher = VectorSearcher()
results = searcher.search("query", top_k=10)
```

### Use Only BM25 Search
```python
from app.retrieval.searchers import BM25Searcher

searcher = BM25Searcher()
results = searcher.search("query", top_k=10)
```

### Hybrid with Details
```python
from app.retrieval.searchers import HybridSearcher

searcher = HybridSearcher()
results = searcher.search_with_details("query", top_k=5)

for doc in results:
    print(f"BM25: {doc['bm25_score']:.2f}")
    print(f"Vector: {doc['vector_score']:.2f}")
    print(f"Hybrid: {doc['hybrid_score']:.2f}")
    print(f"Rerank: {doc.get('rerank_score', 'N/A'):.2f}")
```

### Custom Searcher
```python
from app.retrieval.searchers import BaseSearcher

class ElasticsearchSearcher(BaseSearcher):
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        # Your Elasticsearch implementation
        pass
    
    def build_index(self):
        pass
    
    def refresh_index(self):
        pass

# Use in hybrid
hybrid = HybridSearcher(
    vector_searcher=ElasticsearchSearcher(),
    bm25_searcher=BM25Searcher()
)
```

## Method Name Changes

| Old | New | Status |
|-----|-----|--------|
| `hybrid_search()` | `search()` | Cleaner, more generic |
| `hybrid_search_with_details()` | `search_with_details()` | Improved clarity |
| `bm25_search()` | Public in BM25Searcher | Now standalone |
| `pgvector_search()` | Public in VectorSearcher | Now standalone |
| `hybrid_search()` | Available on HybridRetriever | Backward compatible |

## Backward Compatibility

`HybridRetriever` is now an alias to `HybridSearcher`:
```python
# Both work identically
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.searchers import HybridSearcher

retriever = HybridRetriever()    # Works!
searcher = HybridSearcher()       # Recommended
```

## File Structure

```
app/retrieval/
├── __init__.py
├── searchers/                    # New module
│   ├── __init__.py              # Exports all searchers
│   ├── base.py                  # Abstract base class
│   ├── vector.py                # VectorSearcher
│   ├── keyword.py               # BM25Searcher
│   └── hybrid.py                # HybridSearcher
├── embedder.py                   # Unchanged
├── reranker.py                   # Unchanged
├── hybrid_search.py              # Now just a compatibility shim
└── vector_search.py              # Unchanged (for API routes)
```

## Next Steps

1. Update existing imports to use new classes (optional - backward compatibility works)
2. Use individual searchers for specific use cases
3. Create custom searchers by extending BaseSearcher
