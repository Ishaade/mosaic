# Phase 2 — Persistence

## What was built

- **Verified SQLite tables** (`users`, `conversations`, `messages`) in `backend/mosaic.db`.
- **User bootstrap**: `POST /users` creates a row; the React app stores `user_id` in `localStorage` on first visit.
- **Chat persistence**: `POST /chat` now requires `user_id`, optionally takes `conversation_id`, saves user + assistant turns (including crisis replies), and sends recent history to the LLM.
- **History APIs**: `GET /conversations?user_id=…` and `GET /conversations/{id}/messages?user_id=…` with a simple ownership check.
- **LLM wrapper hardening**: retries with exponential backoff on 429/5xx/timeouts; clean client errors (no keys, no tracebacks).
- **Frontend**: keeps `conversation_id` across refresh and reloads message history.
- **Tests**: pytest coverage for the safety gate, Pydantic schemas, DB helpers, and chat API (LLM mocked).

## How data flows

```
Browser (localStorage: user_id, conversation_id)
    │
    ├─ first visit → POST /users → save id
    │
    └─ send message → POST /chat { user_id, conversation_id?, persona, message }
            │
            ├─ load/create Conversation
            ├─ INSERT user Message
            ├─ if crisis keywords → INSERT crisis reply → return (no LLM)
            ├─ SELECT recent Messages (char budget)
            ├─ LLM(system + history)
            └─ INSERT assistant Message → return { reply, conversation_id, … }

Refresh → GET /conversations/{id}/messages?user_id=… → redraw chat
```

## Design choices (and why)

| Choice | Why | Alternative considered |
|--------|-----|------------------------|
| SQLite file `mosaic.db` | Zero setup for a portfolio; SQLAlchemy lets us swap to Postgres later via URL | Postgres from day one — more ops for little gain now |
| `user_id` in the request body / query string | Simple to explain; matches "no auth yet" | JWT cookies — correct for production, overkill for Phase 2 |
| Character budget (`HISTORY_CHAR_BUDGET = 6000`) instead of true tokens | No extra tokenizer dependency; easy to reason about | tiktoken / provider token counts — more accurate, more complexity |
| Ownership check returns **404** (not 403) | Avoids confirming that another user's conversation id exists | 403 Forbidden — clearer to the real owner, leakier to attackers |
| Crisis messages **are** saved | Continuity + audit trail for the demo; user can re-read helpline text after refresh | Drop crisis text — loses history; Phase 3 will still refuse to embed crisis text as "memories" |
| Sync SQLAlchemy in async FastAPI routes | Default engine is sync; FastAPI runs sync deps in a threadpool | Async SQLAlchemy — better under heavy load, steeper learning curve |
| Retries only for 429 / 5xx / timeouts | Retrying a bad API key (401) or missing model (404) won't help | Blind retry of every error — wastes time and can amplify outages |

## Important limitation: this is NOT authentication

Anyone who knows (or guesses) a `user_id` can read that user's chats. `localStorage` is trivial to edit.

**What would replace this later:**

1. User signs in (OAuth / email magic link / username+password).
2. Server issues a **JWT** (or session cookie) after verifying identity.
3. Every request sends the token; the server derives `user_id` from the token signature — **never** trusts a client-supplied id for authorization.

The ownership checks in Phase 2 are a teaching stand-in, not security.

## Other limitations

- `Base.metadata.create_all` only **creates** missing tables — it does not alter columns. Schema changes need a DB wipe (dev) or Alembic (Phase 6).
- History trim can drop older turns mid-chat; the model may "forget" early context.
- Message content is stored in plaintext SQLite — fine for local demo, not for real mental-health data at rest.
- We do **not** log message bodies (sensitive); provider logs on the free LLM tier are out of our control.

## How to run and test

From PowerShell:

```powershell
# Backend
cd backend
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

**Manual checks**

1. Open http://localhost:5173 — status should show `user #N`.
2. Send a normal message — reply appears; refresh the page — history reloads.
3. Send a crisis phrase (e.g. "I want to kill myself") — fixed helpline reply; refresh — it is still in history.
4. Click another persona — new empty chat; "new chat" clears the thread.
5. Verify tables: from `backend/`, `python app\db\check_db.py` → should list `users`, `conversations`, `messages`.

**Automated tests** (no API key needed):

```powershell
cd backend
python -m pytest -q
```

## 5 interview questions

**1. Why separate `User`, `Conversation`, and `Message` tables?**  
So one person can have many chats, and each chat can have many turns, without duplicating user data. Foreign keys keep the relationships honest.

**2. How do you stop User A from reading User B's messages in this app?**  
`GET .../messages` checks `conversation.user_id == user_id` and returns 404 on mismatch. But the client still supplies `user_id`, so this is only a demo guard — real auth would take the id from a verified token.

**3. Why send chat history to the LLM at all?**  
Stateless HTTP: the model only sees what you put in the `messages` array. Without history, every reply starts from scratch.

**4. What is a character/token budget and what happens when you exceed it?**  
Models have a max context size. We keep the newest messages whose total length fits `HISTORY_CHAR_BUDGET` and drop older ones so requests stay within limits and cheaper.

**5. Why wrap the OpenAI client in `llm.py` instead of calling Groq from the router?**  
One place for retries, error mapping, and provider config. Swapping to another OpenAI-compatible host is mostly an env-var change, not a rewrite of `/chat`.
