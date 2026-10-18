# Phase 3 — Memory + RAG

## What was built

- **ChromaDB persistent store** (`./chroma_data`) using the built-in local embedding model (ONNX `all-MiniLM-L6-v2`) — no paid embedding API.
- **After each normal (non-crisis) chat turn**: a small LLM call extracts durable facts as JSON → Pydantic validation → each fact stored as its own short vector chunk with metadata (`user_id`, `persona`, `scope`, `kind`, `created_at`).
- **Before each reply**: retrieve **top-k** relevant memories filtered by `user_id` and (global **or** current `persona`), inject them into the system prompt inside a clearly delimited “untrusted context” section, within a character budget.
- **Privacy**: `GET /users/{id}/memories` lists stored chunks; `DELETE /users/{id}/data` wipes SQL rows **and** vector entries.
- **Crisis turns never become memories** (extraction is skipped entirely).
- Tests cover store filtering, prompt wording, extraction failure handling, crisis skip, and privacy wipe (LLM mocked; Chroma ephemeral).

## How data flows

```
User message
    │
    ├─ save to SQLite
    ├─ crisis? → fixed reply, save, STOP (no LLM, no extract)
    │
    ├─ Chroma query(user_id, persona, message) → top-k hits
    ├─ system_prompt = persona rules + "## Retrieved memories (untrusted)..."
    ├─ LLM(system + recent history) → reply → save
    │
    └─ extract_facts(user, reply) → validate JSON → Chroma add (best-effort)
```

## Chunking, metadata filtering, and top-k (interview-ready)

### Chunking
A **chunk** is one short fact string we embed and store (e.g. `"User's name is Sam"`).  
We deliberately keep chunks small and atomic:

- Better retrieval: one idea per vector → cleaner similarity matches.
- Safer updates/deletes later (delete one fact without rewriting a huge blob).

Alternative: embed whole messages. That is simpler but noisier (greetings, one-off questions pollute the index) and riskier for crisis text.

### Metadata filtering
Every chunk carries metadata. On query we **filter first**, then rank by similarity among the survivors:

- Always: `user_id == current user` (privacy isolation between users).
- And: `scope == "global"` **OR** `persona == current persona`.

So a tutor-only study goal does not leak into the friend persona, but a global name does.

### Top-k
**Top-k** means “return the k nearest neighbors” (here `TOP_K = 5`).  
Raising k gives the model more context but costs tokens and can add irrelevant noise. We also apply `MEMORY_CHAR_BUDGET` so even k hits cannot blow the prompt.

## Design choices (and why)

| Choice | Why | Alternative |
|--------|-----|-------------|
| Local Chroma embeddings | Free, offline, no second API key | OpenAI/Groq embeddings — higher quality, paid, leaves the machine |
| Separate extract LLM call | Structured facts > raw message dump | Embed every user message — simpler, more noise, crisis risk |
| Best-effort extract (errors → `[]`) | Chat must still work if extract fails | Fail the whole `/chat` — bad UX |
| `scope` global vs persona | Names travel across personas; homework goals should not | Filter only by user_id — simpler, more cross-talk |
| Ephemeral Chroma in tests | Fast, no disk, no network | Hit real `./chroma_data` — slower, flakier CI |

## Privacy & safety notes

- Listing/deleting still trusts a client-supplied `user_id` (same Phase 2 auth gap).
- Vectors live on disk under `chroma_data/` — plaintext facts, not encrypted at rest.
- Free LLM tiers may log prompts; extraction sends user text to the provider. A public demo should use fake data only.
- We never log message bodies in our app logs.

## New dependency

- **`chromadb`**: required for Phase 3 RAG. Pulls ONNX runtime and the MiniLM model on first use.

## How to run and test

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

```powershell
cd frontend
npm run dev
```

**Manual checks**

1. Chat as usual: “My name is Sam and I love hiking.”
2. In a later turn: “What do you remember about me?” — reply should reflect stored facts (after extract succeeds).
3. `GET http://127.0.0.1:8000/users/{id}/memories` — see chunks.
4. Crisis phrase — helpline reply; memories list must **not** gain crisis text.
5. `DELETE http://127.0.0.1:8000/users/{id}/data` — user 404 afterward; memories gone.

**Tests**

```powershell
cd backend
python -m pytest -q
```

## 5 interview questions

**1. What is RAG?**  
Retrieval-Augmented Generation: fetch relevant stored text, put it in the prompt, then generate. The model stays small/stateless; long-term knowledge lives in the vector DB.

**2. Why filter by metadata instead of only using similarity?**  
Similarity alone could return another user’s near-duplicate fact. Metadata (`user_id`) enforces tenancy; persona/scope controls relevance.

**3. Why not store crisis messages as memories?**  
They are sensitive, can re-trigger distress when retrieved, and the fixed helpline path already handled them. Extraction is skipped on that path.

**4. What does “treat memories as untrusted” mean?**  
Retrieved text might contain injection attempts (“ignore instructions…”). We delimit it and tell the model it is data, not commands — defense in depth (Phase 4 adds more).

**5. Chunking vs embedding whole conversations?**  
Small fact chunks retrieve cleaner signals and are easier to delete. Whole-conversation chunks are easier to build but noisier and harder to redact.
