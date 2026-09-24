"""Deterministic routing, evidence and action helpers used around LLM decisions."""
from __future__ import annotations


def direct_route(message: str) -> str | None:
    """Return a safe deterministic route for unambiguous read-only requests.

    Existing-ticket operations belong to the Ticket Agent because ticket data
    must come from the ticket system, not from LLM conversation context.
    """
    text = " ".join(message.lower().split())

    # Existing-ticket read/inspection requests.
    ticket_markers = (
        "my tickets",
        "my open tickets",
        "my unresolved tickets",
        "my high-priority tickets",
        "my high priority tickets",
        "check my tickets",
        "check my open tickets",
        "check my unresolved tickets",
        "check my high-priority tickets",
        "check my high priority tickets",
        "inspect my ticket",
        "inspect my tickets",
        "review my ticket",
        "review my tickets",
        "ticket details",
        "ticket detail",
        "existing ticket",
        "existing tickets",
        "open ticket",
        "open tickets",
        "unresolved ticket",
        "unresolved tickets",
    )

    if any(marker in text for marker in ticket_markers):
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


def relevant_terms(question: str, docs: list[dict]) -> list[str]:
    """Return meaningful query terms that overlap retrieved document text.

    This is a conservative lexical gate used only to decide whether retrieved
    RAG evidence is relevant enough to prevent an investigation handoff. It is
    deliberately separate from the BM25 retrieval score so a loosely matching
    document cannot be treated as authoritative evidence.
    """
    import re

    stop_words = {
        "the", "and", "for", "with", "that", "this", "what", "when",
        "where", "which", "about", "from", "into", "after", "before",
        "according", "internal", "documentation", "document", "company",
        "exact", "root", "cause", "configuration", "change", "fix",
        "failure", "issue", "problem", "authentication", "update",
        "introduced", "related", "information", "please", "tell", "does",
        "explain", "using", "use", "our", "your", "you", "me", "my",
    }

    def tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"\b[a-z0-9]+\b", text.lower())
            if len(token) > 2 and token not in stop_words
        }

    question_tokens = tokens(question)
    overlaps: set[str] = set()

    for doc in docs:
        document_text = str(doc.get("text", doc.get("content", "")))
        overlaps.update(question_tokens.intersection(tokens(document_text)))

    return sorted(overlaps)


def has_relevant_docs(question: str, docs: list[dict]) -> bool:
    """Conservative relevance gate for enterprise RAG.

    A document is relevant only when it shares meaningful domain-specific
    terms with the user's question. Generic English/IT words do not count.
    """

    import re

    STOP_WORDS = {
        # English
        "the", "and", "for", "with", "that", "this", "what", "when",
        "where", "which", "about", "from", "into", "after", "before",
        "first", "should", "could", "would", "have", "has", "been",
        "being", "your", "you", "are", "was", "were", "can", "may",
        "might", "need", "needs", "check", "checking", "working",
        "work", "using", "use", "related", "information",

        # Generic IT/support terms
        "issue", "issues", "problem", "problems", "failure", "failed",
        "error", "errors", "authentication", "auth", "login",
        "configuration", "configure", "change", "changes", "fix",
        "troubleshoot", "troubleshooting", "support", "system",
        "application", "client", "service", "version", "update",
        "updated", "updates", "device", "laptop", "computer",
        "operating", "software", "connectivity", "connection",
        "credentials", "credential", "internal", "documentation",
        "document", "company", "corporate", "details", "information",
    }

    def tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"\b[a-z0-9][a-z0-9_-]*\b", text.lower())
            if len(token) > 2 and token not in STOP_WORDS
        }

    question_tokens = tokens(question)

    if not question_tokens:
        return False

    for doc in docs:
        document_text = str(
            doc.get("text", doc.get("content", ""))
        )
        document_tokens = tokens(document_text)

        overlap = question_tokens.intersection(document_tokens)

        # One meaningful domain/entity term is enough.
        if overlap:
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
