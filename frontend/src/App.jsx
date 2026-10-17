import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";
const PERSONAS = ["therapist", "tutor", "parent", "friend"];

// localStorage keys — NOT real auth; anyone with the id can use it
const USER_ID_KEY = "mosaic_user_id";
const CONVERSATION_ID_KEY = "mosaic_conversation_id";
const PERSONA_KEY = "mosaic_persona";

export default function App() {
  const [persona, setPersona] = useState(
    () => localStorage.getItem(PERSONA_KEY) || "friend"
  );
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [backendUp, setBackendUp] = useState(null); // null = checking
  const [userId, setUserId] = useState(null);
  const [conversationId, setConversationId] = useState(() => {
    const saved = localStorage.getItem(CONVERSATION_ID_KEY);
    return saved ? Number(saved) : null;
  });
  const [ready, setReady] = useState(false); // true once user + optional history loaded
  const bottomRef = useRef(null);

  // On first visit: create a user (or reuse the id from localStorage)
  useEffect(() => {
    async function ensureUser() {
      try {
        const health = await fetch(`${API_URL}/health`);
        setBackendUp(health.ok);
        if (!health.ok) return;

        let id = localStorage.getItem(USER_ID_KEY);
        if (id) {
          // Confirm the stored user still exists (e.g. after wiping mosaic.db)
          const check = await fetch(`${API_URL}/users/${id}`);
          if (!check.ok) {
            localStorage.removeItem(USER_ID_KEY);
            localStorage.removeItem(CONVERSATION_ID_KEY);
            id = null;
            setConversationId(null);
          }
        }

        if (!id) {
          const res = await fetch(`${API_URL}/users`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          if (!res.ok) throw new Error("Could not create user");
          const data = await res.json();
          id = String(data.id);
          localStorage.setItem(USER_ID_KEY, id);
        }

        setUserId(Number(id));
      } catch {
        setBackendUp(false);
      }
    }
    ensureUser();
  }, []);

  // Once we have a user, reload the open conversation's history (if any)
  useEffect(() => {
    if (userId == null) return;

    async function loadHistory() {
      if (!conversationId) {
        setReady(true);
        return;
      }
      try {
        const res = await fetch(
          `${API_URL}/conversations/${conversationId}/messages?user_id=${userId}`
        );
        if (!res.ok) {
          // Stale id (deleted DB, wrong owner) — start fresh
          localStorage.removeItem(CONVERSATION_ID_KEY);
          setConversationId(null);
          setMessages([]);
          setReady(true);
          return;
        }
        const data = await res.json();
        setMessages(
          data.map((m) => ({
            role: m.role === "assistant" ? "bot" : m.role,
            text: m.content,
          }))
        );
      } catch {
        // Network blip — still allow chatting; history just won't show
      } finally {
        setReady(true);
      }
    }
    loadHistory();
  }, [userId, conversationId]);

  // Scroll to the newest message whenever the list grows
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function persistConversationId(id) {
    setConversationId(id);
    localStorage.setItem(CONVERSATION_ID_KEY, String(id));
  }

  async function sendMessage(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading || userId == null) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const body = { persona, message: text, user_id: userId };
      if (conversationId != null) body.conversation_id = conversationId;

      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();
      persistConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: data.reply,
          crisis: data.crisis,
          disclaimer: data.disclaimer,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "error", text: "Something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function changePersona(p) {
    setPersona(p);
    localStorage.setItem(PERSONA_KEY, p);
    setMessages([]);
    // New persona = new conversation thread
    setConversationId(null);
    localStorage.removeItem(CONVERSATION_ID_KEY);
  }

  function startNewChat() {
    setMessages([]);
    setConversationId(null);
    localStorage.removeItem(CONVERSATION_ID_KEY);
  }

  const disclaimer = [...messages].reverse().find((m) => m.disclaimer)?.disclaimer;

  return (
    <div className="app">
      <h1>Mosaic</h1>
      <p className="status">
        Backend:{" "}
        {backendUp === null ? "checking..." : backendUp ? "online" : "offline"}
        {userId != null ? ` · user #${userId}` : ""}
        {conversationId != null ? ` · chat #${conversationId}` : ""}
      </p>

      <div className="personas">
        {PERSONAS.map((p) => (
          <button
            key={p}
            className={p === persona ? "active" : ""}
            onClick={() => changePersona(p)}
          >
            {p}
          </button>
        ))}
        <button type="button" className="new-chat" onClick={startNewChat}>
          new chat
        </button>
      </div>

      {persona === "therapist" && (
        <p className="disclaimer">
          {disclaimer ||
            "Mosaic is an AI, not a licensed therapist. It can't diagnose or treat."}
        </p>
      )}

      <div className="chat">
        {!ready && <div className="msg bot">loading...</div>}
        {ready &&
          messages.map((m, i) => (
            <div
              key={i}
              className={`msg ${m.role} ${m.crisis ? "crisis" : ""}`}
            >
              {m.text}
            </div>
          ))}
        {loading && <div className="msg bot">typing...</div>}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={sendMessage}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Message the ${persona}...`}
          maxLength={2000}
          disabled={!ready || userId == null}
        />
        <button type="submit" disabled={loading || !ready || userId == null}>
          Send
        </button>
      </form>
    </div>
  );
}
