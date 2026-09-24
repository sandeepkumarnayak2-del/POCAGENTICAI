"""Enterprise RAG/knowledge agent."""
from __future__ import annotations
import json
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from .base import AgentResult, BaseAgent, clean_response
from .utils import external_or_investigation_requested, has_relevant_docs, relevant_terms
from app.rag.agentic import agentic_retrieve
from app.llm.provider import SYSTEM
from app.observability.logging import logger

class KnowledgeAgent(BaseAgent):
    name = "knowledge"
    def __init__(self, llm=None):
        @tool
        def search_knowledge_base(query: str) -> list[dict]:
            """Search the enterprise IT knowledge base."""
            _, docs = agentic_retrieve(query)
            return docs
        self.search_tool = search_knowledge_base
        super().__init__(llm=llm, tools=[search_knowledge_base])
        self.tool_llm = self.llm.bind_tools(self.tools)

    def run(self, message: str, memories: list[dict], conversation: str = "") -> AgentResult:
        context = f"""Relevant recent conversation:
{conversation}""" if conversation else ""
        messages = [
            SystemMessage(content=f"""{SYSTEM}

You are the Knowledge Agent.
Own internal IT troubleshooting and enterprise knowledge questions.
Use search_knowledge_base when company evidence is needed. You may refine the query.
Do not invent company procedures. If evidence is insufficient, say so clearly.
Do not perform or claim external web search.

GROUNDING RULES:
- Treat retrieved documents as evidence, not as proof that the user's named
  product or system is the same as a product or system mentioned in a document.
- Never replace a documented entity with the user's entity.
  Example: if the document says "VPN client" and the user says "AcmeVision",
  do not write "AcmeVision client" unless the document explicitly identifies
  AcmeVision as that client.
- If the retrieved document is generic or unrelated to the named system,
  do not use it as specific evidence.
- When evidence is insufficient, explicitly say that the internal
  documentation does not contain information specific to the named system.
{memories or '[none]'}
{context}
Focus on the CURRENT request."""),
            HumanMessage(content=message),
        ]
        all_docs: list[dict] = []
        seen_docs: set[tuple[str, str]] = set()
        for _ in range(3):
            result = self.tool_llm.invoke(messages)
            messages.append(result)
            calls = getattr(result, "tool_calls", [])
            if not calls:
                overlap_terms = relevant_terms(message, all_docs)
                relevant = bool(overlap_terms)
                investigation_requested = external_or_investigation_requested(message)

                logger.info(
                    "knowledge_handoff_check",
                    relevant_docs=relevant,
                    relevant_terms=overlap_terms,
                    investigation_requested=investigation_requested,
                    document_count=len(all_docs),
                )

                handoff = None
                if not relevant and investigation_requested:
                    handoff = "investigation"

                return AgentResult(
                    clean_response(result.content),
                    messages,
                    {
                        "documents": all_docs,
                        "handoff": handoff,
                    },
                )
            for call in calls:
                if call["name"] != self.search_tool.name:
                    continue
                docs = self.search_tool.invoke(call.get("args", {}))
                for doc in docs:
                    key = (str(doc.get("source", "")), str(doc.get("text", doc.get("content", ""))))
                    if key not in seen_docs:
                        seen_docs.add(key)
                        all_docs.append(doc)
                logger.info(
                        "agent_tool_call",
                        agent="knowledge",
                        tool="search_knowledge_base",
                        query=call.get("args", {}).get("query", ""),
                        result_count=len(docs),
                        documents=docs,
                        action="rag_retrieval",
                    )
                messages.append(ToolMessage(content=json.dumps(docs, default=str), tool_call_id=call["id"]))
        handoff = "investigation" if not has_relevant_docs(message, all_docs) and external_or_investigation_requested(message) else None
        return AgentResult("I could not complete the knowledge search safely.", messages, {"documents": all_docs, "handoff": handoff})
