# Stage A — Real authentication (backend)

## What was built

- **User model** now has `email` (unique, indexed, stored lowercase), `password_hash` (argon2), optional `name`, and `created_at`.
- **Auth endpoints**: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `DELETE /auth/me`.
- **JWT access tokens** (HS256, default 60 min expiry). `JWT_SECRET` is **required** in settings (no default) so the app fails at startup if missing.
- **`get_current_user`** FastAPI dependency: reads Bearer token → verifies signature/expiry → loads user. Protects `/chat`, `/chat/stream`, `/conversations`, `/memories`, `/auth/me`.
- **No client-supplied `user_id`** on chat/conversations/memories. Identity comes from the token only. `ChatRequest` uses `extra="forbid"` so a leftover `user_id` field is rejected.
- **Ownership**: other users' conversations → **404** (not 403).
- **Generic login error** for wrong email or wrong password (`Invalid email or password`).
- **Rate limits** (slowapi) on register (5/min) and login (10/min) by IP.
- **Account wipe**: `DELETE /auth/me` removes SQL rows + Chroma vectors.
- Old unauthenticated `POST /users` / `DELETE /users/{id}/data` removed.

## Before you restart (schema changed)

Delete the old database and vector store, then reinstall deps and start:

```powershell
cd backend
Remove-Item mosaic.db -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force chroma_data -ErrorAction SilentlyContinue
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**Add this line to your `.env` (do not commit it):**

```env
JWT_SECRET=replace-me-with-a-long-random-string
```

Generate a secret in PowerShell if you want:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then:

```powershell
python -m uvicorn app.main:app --reload
```

```powershell
cd backend
python -m pytest -q
```

## How data flows

```
Register → argon2 hash password → INSERT users
Login    → verify hash → sign JWT {sub: user_id, email, exp}
Request  → Authorization: Bearer <token>
         → get_current_user → User row
         → handlers use current_user.id only
Logout   → client deletes token (server is stateless)
Delete   → Chroma wipe + SQL wipe for that user_id
```

## Design choices

| Choice | Why | Alternative |
|--------|-----|-------------|
| argon2-cffi | Modern, memory-hard password hashing | bcrypt — also fine, older default |
| JWT in `Authorization` header | Simple for SPA + API; no cookie CSRF on cross-site POSTs the same way | httpOnly cookies — better XSS resistance (Stage C notes) |
| No default `JWT_SECRET` | Prevents accidentally shipping with a known key | Soft default — unsafe |
| 404 on ownership miss | Don't confirm resource ids to strangers | 403 — clearer but leakier |
| Same login error always | Stops email enumeration | Separate "user not found" — helps attackers |
| slowapi IP limits | Cheap brute-force slowdown for a demo | Redis-backed limits — needed at real scale |
| Stateless JWT | Easy to reason about | Server sessions — instant revoke |

## Logout limitation (important)

JWTs are **stateless**. “Logout” means the **browser deletes the token**. The server cannot invalidate that token early; it stays valid until `exp`.

**What would fix it in production:**

1. Short-lived access tokens (e.g. 5–15 min) + refresh tokens, or
2. A **revocation list** / token version on the user row checked on every request, or
3. Server-side sessions stored in Redis/DB.

## New dependencies

| Package | Why |
|---------|-----|
| `argon2-cffi` | Hash/verify passwords |
| `PyJWT` | Create/verify access tokens |
| `email-validator` | Pydantic `EmailStr` |
| `slowapi` | Rate-limit auth routes |

## Known limitations

- Frontend still uses the old anonymous `user_id` flow until Stage C — call auth APIs with curl/Postman for now.
- Rate limits are per-IP in memory; multi-worker deploys need a shared backend.
- Timing attacks on login are not fully mitigated (constant-time dummy verify is a follow-up).
- XSS that steals a token from localStorage (Stage C) remains a threat until httpOnly cookies.

## Manual API smoke test

```powershell
# Register
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" -d "{\"email\":\"you@example.com\",\"password\":\"password123\"}"

# Login — copy access_token
curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d "{\"email\":\"you@example.com\",\"password\":\"password123\"}"

# Me
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer PASTE_TOKEN"

# Chat (no user_id in body)
curl -X POST http://127.0.0.1:8000/chat -H "Authorization: Bearer PASTE_TOKEN" -H "Content-Type: application/json" -d "{\"persona\":\"friend\",\"message\":\"hello\"}"
```

## 5 interview questions

**1. Why hash passwords instead of encrypting them?**  
Hashing is one-way. Even if the DB leaks, attackers should not recover the original password (if the hash is slow + salted). Encryption is reversible with a key — worse if that key leaks too.

**2. What does a JWT contain and how do you trust it?**  
Claims (user id, expiry) plus a signature made with `JWT_SECRET`. Anyone can read the payload; only someone with the secret can forge a valid signature.

**3. Why not trust `user_id` from the JSON body?**  
Clients can change anything they send. An attacker would set `user_id` to someone else's id. The server must derive identity from a verified credential (here, the JWT).

**4. Why return 404 instead of 403 for another user's chat?**  
403 confirms “this id exists, you just can't see it.” 404 hides that fact and reduces id probing.

**5. What is the downside of stateless JWT logout?**  
You cannot instantly revoke a stolen token without extra machinery (denylist / short TTL + refresh). Until expiry, a stolen token still works.
