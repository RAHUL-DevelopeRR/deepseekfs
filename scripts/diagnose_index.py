"""End-to-end search test with the NLP parser."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.search.semantic_search import SemanticSearch

s = SemanticSearch()

tests = [
    ("Give me the list of python files found", 20),
    ("show me all pdf files", 20),
    ("python files about machine learning", 10),
    ("python files in downloads", 20),
    ("find my resume", 10),
    ("large pdf files", 10),
]

for q, k in tests:
    print(f"{'='*60}")
    print(f"  QUERY: {q!r}")
    print(f"{'='*60}")
    results = s.search(q, top_k=k)
    print(f"  Results: {len(results)}")
    for i, x in enumerate(results[:5]):
        name = x['name']
        path = x['path']
        score = x.get('combined_score', 0)
        print(f"    {i+1}. {name} (score={score:.2f})")
        print(f"       {path[:80]}")
    print()
