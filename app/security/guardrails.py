import re

INJECTION_PATTERNS = [
    r"ignore (all|any|the) previous instructions",
    r"reveal (the )?(system|developer) prompt",
    r"show me (the )?(api key|secret|password)",
    r"disable (your|the) safety",
]

def detect_prompt_injection(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in INJECTION_PATTERNS)

#Guardrails for both input and op using some patterns etc
#TODO
def output_guardrail(text: str) -> str:
    secret_words = ["OPENAI_API_KEY=", "GROQ_API_KEY=", "SECRET_KEY="]
    for s in secret_words:
        if s in text:
            return "[Output blocked: sensitive information detected.]"
    return text


