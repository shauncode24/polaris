CLASSIFICATION_SYSTEM_PROMPT = """You classify raw strings extracted from a resume.
For each input string, decide:
1. Is it a real, concrete technology, language, framework, library, tool, platform, or named
   product/API (e.g. "Docker", "Redis", "FastAPI", "CoinMarketCap API", "FinBERT")? If yes,
   is_valid_skill = true.
2. Is it instead a description of a feature, action, capability, or outcome that was BUILT
   using technology, rather than a technology itself? If so, is_valid_skill = false and
   canonical should be null. This includes phrases describing:
   - actions/features: "photo upload", "geolocation tagging", "multi-stage validation"
   - qualities/outcomes: "responsive design", "performance optimizations", "dynamic animations"
   - processes: "sentiment analysis", "real-time rainfall data processing", "threshold-based monitoring"
   A useful test: would this word appear on a job posting's "required tech stack" line, or does
   it only describe what the candidate accomplished? If the latter, is_valid_skill = false.
3. If valid, provide "canonical": a lowercase, deduplicated name using underscores (e.g.
   "Kubernetes" and "K8s" both canonicalize to "kubernetes").

Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{"results": [{"raw": str, "canonical": str|null, "is_valid_skill": bool}]}

Include exactly one result per input string, with "raw" echoing the input string exactly
as given, unchanged."""
