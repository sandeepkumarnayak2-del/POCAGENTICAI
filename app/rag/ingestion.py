from pathlib import Path
from app.rag.store import add_documents

def ingest():
    base = Path("data/documents")
    docs = []
    for p in base.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        paragraphs = [x.strip() for x in text.split("\n\n") if x.strip()]
        for i, chunk in enumerate(paragraphs):
            docs.append({"id": f"{p.stem}-{i}", "text": chunk, "source": p.name, "title": p.stem})
    add_documents(docs)
    print(f"Ingested {len(docs)} chunks.")

if __name__ == "__main__":
    ingest()
