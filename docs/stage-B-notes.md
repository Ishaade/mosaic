# Stage B — Smart persona routing

## What was built

- **`app/services/router.py`**: LLM-as-classifier. Input = current message + last few turns. Output = Pydantic-validated JSON `{suggested_persona, confidence, reason}`.
- User / history text is wrapped in `<user_message>` / `<recent_history>` and labeled as **data, not instructions**.
- Failures (bad JSON, provider errors) → **no suggestion**. Chat continues.
- **Crisis always wins**: if the safety gate fires, routing is skipped (`suggestion: null`).
- **Never auto-switch**: the API only *suggests*. The user must accept (UI in Stage C).
- Suggestion is attached to `POST /chat` and to the SSE `meta` event on `/chat/stream` when:
  1. confidence ≥ `ROUTING_CONFIDENCE_THRESHOLD` (default `0.65`), and
  2. suggested persona ≠ current persona, and
  3. anti-nag cooldown allows it (`ROUTING_COOLDOWN_MESSAGES`, default every 3rd user turn, including turn 1).
- **Eval script**: `scripts/eval_routing.py` + ~20 labeled examples (incl. injection attempts).
- Tests mock the LLM; no API key required for pytest.

## How data flows

```
User message (authenticated)
    │
    ├─ safety crisis? ──yes──► helpline reply, suggestion=null, STOP routing
    │
    ├─ cooldown allows? ──no──► suggestion=null
    │
    ├─ LLM router (short prompt, max_tokens≈120) → JSON
    │     invalid/fail → suggestion=null
    │     same persona / low confidence → suggestion=null
    │     else → suggestion {persona, reason, confidence}
    │
    └─ normal chat / stream reply (unchanged persona)
```

## Design choices

| Choice | Why | Alternative |
|--------|-----|-------------|
| Suggest only, never switch | User stays in control; wrong routes won't hijack the chat | Auto-switch — snappier, riskier UX |
| Short prompt + `max_tokens=120` | Routing is an *extra* LLM call every few turns — keep it cheap/fast | Large reasoning prompt — higher cost, little gain for 4 labels |
| Cooldown every N turns | Avoid nagging “switch to tutor?” on every message | Suggest every turn — noisy |
| Crisis skips routing | Helpline path must not be delayed or diluted by a persona nudge | Route anyway — confusing in a crisis |
| Fail-open to `null` | Chat must work if the router is down | Fail the request — bad UX |

## Cost / latency trade-off

Each cooldown-eligible turn adds **one small LLM call** before (or alongside) the main reply. That adds latency and token cost. We mitigate with:

- tiny system prompt,
- truncated history (last 4 turns, 200 chars each),
- `temperature=0`,
- `max_tokens=120`,
- cooldown so we don't call every message.

If cost matters more, raise `ROUTING_COOLDOWN_MESSAGES` or increase the confidence threshold.

## Config (optional `.env`)

```env
ROUTING_CONFIDENCE_THRESHOLD=0.65
ROUTING_COOLDOWN_MESSAGES=3
```

## How to run and test

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

```powershell
cd backend
python -m pytest -q
python scripts\eval_routing.py --dry-run
python scripts\eval_routing.py          # needs LLM_API_KEY
```

**Manual check (after login):**

1. Chat as `friend` with “explain photosynthesis step by step”.
2. Response JSON (or SSE meta) may include `"suggestion": {"persona":"tutor", ...}`.
3. Crisis message → `suggestion` is null; router not called.
4. Send two more casual messages → suggestion suppressed by cooldown until the next eligible turn.

## Known limitations

- Labels are subjective (parent vs friend vs therapist overlap). Eval accuracy will not be 100%.
- Injection attempts are scored as “still classify the real topic”; we do not prove the model ignored the jailbreak — prompt rules + delimiters are defense in depth.
- Frontend banner for Accept/Dismiss arrives in Stage C; until then inspect the API field.

## 5 interview questions

**1. What is LLM-as-classifier routing?**  
A small model call that maps text → a label (here, a persona) as structured JSON, instead of hand-written keyword rules for every topic.

**2. Why not auto-switch the persona?**  
Classifiers are wrong sometimes. Auto-switch would change tone mid-conversation without consent; a suggestion keeps the human in the loop.

**3. Why does crisis skip routing?**  
Safety is higher priority than UX polish. Extra latency or a “try tutor?” banner during a crisis is inappropriate.

**4. How do you stop prompt injection from forcing a persona?**  
Delimit user text, instruct the classifier to ignore instructions inside it, validate output with Pydantic, and never execute free-form commands from the model — only a closed persona enum.

**5. What is a confidence threshold for?**  
The model always returns some label. Thresholding hides weak guesses so we only nudge the user when the classifier is reasonably sure.
