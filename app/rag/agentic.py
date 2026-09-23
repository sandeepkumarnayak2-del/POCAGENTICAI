from app.llm.provider import invoke_llm, SYSTEM
from app.rag.store import search
from app.observability.metrics import RAG_RETRIEVALS

def rewrite_query(question: str) -> str:
    result = invoke_llm([
        ("system", "Rewrite the user's IT support question into one concise search query. Return only the query."),
        ("human", question),
    ])
    return result.content.strip()

def grade(docs, question):
    if not docs:
        return False
    # Lightweight deterministic relevance gate for the POC.
    q = set(question.lower().split())
    overlap = []
    for d in docs:
        #Does at least one retrieved document share at least two words with the original question?”
        overlap.append(len(q.intersection(set(d["text"].lower().split()))))
    return max(overlap, default=0) >= 2

def agentic_retrieve(question: str):
    query = rewrite_query(question)
    docs = search(query, k=5)
    RAG_RETRIEVALS.inc()
    if not grade(docs, question):
        # Self-correction: second retrieval with original query.
        docs = search(question, k=5)
        RAG_RETRIEVALS.inc()
    return query, docs
