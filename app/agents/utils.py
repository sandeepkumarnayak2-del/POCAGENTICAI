"""Deterministic routing, evidence and action helpers used around LLM decisions."""
from __future__ import annotations


def direct_route(message: str) -> str | None:
    """Return a safe deterministic route for unambiguous, read-only commands.

    The LLM does not need to decide how to handle an exact "my tickets" request.
    This also prevents conversation history from causing the request to be routed
    to a different specialist.
    """
    text = " ".join(message.lower().split())
    ticket_phrases = (
        "show me my tickets",
        "show my tickets",
        "list my tickets",
        "what are my tickets",
        "show my open tickets",
        "list my open tickets",
        "show my open tickets",
    )
    if text in ticket_phrases or text.startswith("show me my tickets "):
        return "ticket"
    return None


def external_or_investigation_requested(message: str) -> bool:
    text = message.lower()
    markers = (
        "investigate", "investigation", "research", "analyze", "analyse",
        "look into", "find out", "if the documentation", "if documentation",
        "latest information", "current information", "why is", "known issue",
    )
    return any(m in text for m in markers)


def has_relevant_docs(question: str, docs: list[dict]) -> bool:
    """Conservative relevance check for enterprise RAG.

    Generic IT terms such as authentication, failure, update, configuration,
    issue, problem, etc. are ignored. A document must contain meaningful
    domain-specific terms from the user's question.
    """
    import re

    STOP_WORDS = {
        "the", "and", "for", "with", "that", "this", "what", "when",
        "where", "which", "about", "from", "into", "after", "before",
        "according", "internal", "documentation", "document", "company",
        "exact", "root", "cause", "configuration", "change", "fix",
        "failure", "issue", "problem", "authentication", "update",
        "introduced", "related", "information",
    }

    def tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"\b[a-z0-9]+\b", text.lower())
            if len(token) > 2 and token not in STOP_WORDS
        }

    question_tokens = tokens(question)

    for doc in docs:
        document_text = str(
            doc.get("text", doc.get("content", ""))
        )
        document_tokens = tokens(document_text)

        overlap = question_tokens.intersection(document_tokens)

        if len(overlap) >= 1:
            return True

    return False


def action_requested(message: str) -> bool:
    """Detect an explicit request to create/raise/open a ticket.

    Conditional wording is intentionally excluded. The Investigation Agent
    must decide whether an action is needed.
    """
    text = " ".join(message.lower().split())
    explicit_markers = (
        "create a ticket",
        "create ticket",
        "prepare a ticket",
        "raise a ticket",
        "raise ticket",
        "open a ticket",
        "open ticket",
        "submit a ticket",
        "log a ticket",
        "file a ticket",
    )
    return any(marker in text for marker in explicit_markers)
