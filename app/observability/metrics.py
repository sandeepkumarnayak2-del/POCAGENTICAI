from prometheus_client import Counter, Histogram

REQUESTS = Counter("agent_requests_total", "Total API requests", ["endpoint", "status"])
LLM_CALLS = Counter("llm_calls_total", "LLM calls", ["provider", "model"])
TOOL_CALLS = Counter("tool_calls_total", "Tool calls", ["tool", "status"])
LLM_LATENCY = Histogram("llm_latency_seconds", "LLM latency")
RAG_RETRIEVALS = Counter("rag_retrievals_total", "RAG retrievals")
TOKEN_INPUT = Counter("llm_input_tokens_total", "Input tokens")
TOKEN_OUTPUT = Counter("llm_output_tokens_total", "Output tokens")
