# NLP intent routing

The app originally described intent routing as "no hardcoded keywords" because
it used embedded example sentences and centroids instead of direct `if word in
query` rules. That is still partially curated: the examples in
`storage/intent_examples.json` define what `chat`, `query`, and `action` mean.

## Current approach

The classifier now blends two semantic signals:

- Intent centroid similarity: good for broad category shape.
- Nearest example similarity: good for near-exact commands such as
  "organize my downloads folder".

This keeps routing local and fast without sending every input to the LLM.

## Better alternatives

- Embedding k-nearest-neighbor classifier: compare against all examples and use
  weighted voting instead of one centroid per class.
- Lightweight local classifier: train logistic regression or linear SVM on
  embeddings and store the small classifier locally.
- Transformer zero-shot classifier: better generalization, but heavier and
  slower than the current approach.
- LLM router: ask a local model for structured intent JSON. Good for nuanced
  routing, but more latency and more failure modes.
- Hybrid router: deterministic guards for dangerous actions, embedding routing
  for normal paths, and LLM routing only for ambiguous requests.

## Recommended path

Use a hybrid router:

1. Guard destructive operations with explicit validation.
2. Route obvious file-search requests to `query`.
3. Route obvious tool/file-operation requests to `action`.
4. Use embedding nearest-neighbor for normal cases.
5. Use Qwen Coder only when the user asks for code/file-operation planning or
   when the embedding route is ambiguous.
