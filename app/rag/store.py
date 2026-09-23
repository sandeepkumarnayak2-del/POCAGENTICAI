import re

from rank_bm25 import BM25Okapi

#_ For internal use
_documents = []
_bm25 = None


def _tokenize(text):
    return re.findall(r"\b\w+\b", text.lower())


def add_documents(docs):
    global _documents, _bm25

    _documents = list(docs)

    tokenized_docs = [
        _tokenize(doc["text"])
        for doc in _documents
    ]

    if tokenized_docs:
        _bm25 = BM25Okapi(tokenized_docs)
    else:
        _bm25 = None


def search(query, k=5):
    if not _documents or _bm25 is None:
        return []

    query_tokens = _tokenize(query)

    if not query_tokens:
        return []

    scores = _bm25.get_scores(query_tokens)

    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )

    results = []

    for index in ranked_indexes[:k]:
        if scores[index] <= 0:
            continue

        doc = _documents[index]

        results.append(
            {
                "text": doc["text"],
                "source": doc.get("source", ""),
                "title": doc.get("title", ""),
            }
        )

    return results