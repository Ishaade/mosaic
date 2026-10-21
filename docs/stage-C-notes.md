# Stage C — UI redesign

## What changed

- Replaced the starter chat page with responsive sign-in/register screens and a two-column conversation workspace.
- Added the four persona contacts, per-persona conversation history, new-chat actions, streamed Markdown replies, therapist disclaimer, and visible crisis reply styling.
- Added settings for inspecting/deleting individual memories, deleting all memories, and permanently deleting an account.
- Added a light/dark toggle that follows the system preference until the user chooses a mode.
- Centralized backend requests in `frontend/src/api.js`; authenticated requests attach the Bearer token and protected-request 401s clear the session and return to sign-in.

## Authentication storage note

The frontend keeps the JWT in memory and `localStorage` so the session survives a refresh. This is convenient for the demo, but any successful same-origin XSS could read and exfiltrate the token. A production deployment should prefer a server-set `httpOnly`, `Secure`, `SameSite` cookie (and account for CSRF protections), rather than exposing the token to JavaScript.

## Manual test checklist

1. Start the backend and frontend, open the app, register an account, and verify duplicate email and invalid form values show useful errors.
2. Sign out and sign back in; refresh while signed in and confirm the session and latest selected conversation restore.
3. Send a multi-paragraph reply; verify Markdown is rendered, HTML is not interpreted, streaming appears, and the view follows the newest message.
4. Send with Enter; use Shift+Enter for a newline; verify the send control disables while the reply is in progress.
5. Switch personas, create chats for each, revisit history, and verify persona-specific conversation lists.
6. Trigger a Stage B persona suggestion; accept it and confirm a fresh chat opens with the suggested persona. Dismiss it and verify it stays dismissed.
7. Open Listener/therapist and confirm the disclaimer is visible. Trigger the crisis safety path and confirm the reply has a distinct urgent-support style.
8. Inspect and delete one saved memory, delete all memories, and verify conversations remain. Confirm both memory wipe and account deletion prompts; cancel once to verify no deletion occurs.
9. Delete the account and confirm the app returns to sign-in. Separately, expire/remove the token and verify a protected-request 401 also signs out.
10. Stop the backend and verify the offline state, then restart it and retry. Test dark/light mode, keyboard focus, Escape/close behavior, and the mobile navigation drawer at narrow viewport sizes.
