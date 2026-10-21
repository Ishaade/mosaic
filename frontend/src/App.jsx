import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import * as api from "./api.js";
import { PERSONAS, personaMeta } from "./personas.js";
import { applyTheme, persistTheme, readStoredTheme, resolveTheme } from "./theme.js";
import AuthScreen from "./components/AuthScreen.jsx";
import ChatView from "./components/ChatView.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import Sidebar from "./components/Sidebar.jsx";

const PERSONA_KEY = "mosaic_persona";
const CONVERSATION_KEY = "mosaic_conversation_id";

function savedPersona() {
  const value = localStorage.getItem(PERSONA_KEY);
  return PERSONAS.some((persona) => persona.id === value) ? value : "friend";
}

function messageFromApi(message) {
  return {
    id: message.id,
    role: message.role === "assistant" ? "assistant" : "user",
    text: message.content,
  };
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(!api.getToken());
  const [backendUp, setBackendUp] = useState(null);
  const [persona, setPersona] = useState(savedPersona);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [suggestion, setSuggestion] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setTheme] = useState(() => resolveTheme(readStoredTheme()));
  const bottomRef = useRef(null);
  const closeSettings = useCallback(() => setSettingsOpen(false), []);

  const handleUnauthorized = useCallback(() => {
    setUser(null);
    setConversations([]);
    setConversationId(null);
    setMessages([]);
    setSuggestion(null);
    setChatError("");
    setAuthReady(true);
    localStorage.removeItem(CONVERSATION_KEY);
  }, []);

  useEffect(() => {
    api.setOnUnauthorized(handleUnauthorized);
    api.setOnConnectivityChange(setBackendUp);
    return () => {
      api.setOnUnauthorized(null);
      api.setOnConnectivityChange(null);
    };
  }, [handleUnauthorized]);

  useEffect(() => {
    if (!sidebarOpen) return undefined;
    function closeDrawerOnEscape(event) {
      if (event.key === "Escape") setSidebarOpen(false);
    }
    document.addEventListener("keydown", closeDrawerOnEscape);
    return () => document.removeEventListener("keydown", closeDrawerOnEscape);
  }, [sidebarOpen]);

  useEffect(() => {
    let cancelled = false;
    api.health().then((online) => {
      if (!cancelled) setBackendUp(online);
    });

    if (!api.getToken()) {
      return () => {
        cancelled = true;
      };
    }

    api.me()
      .then((currentUser) => {
        if (!cancelled) setUser(currentUser);
      })
      .catch((error) => {
        if (!cancelled && error.status !== 401) setChatError(error.message);
      })
      .finally(() => {
        if (!cancelled) setAuthReady(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    applyTheme(theme);
    if (readStoredTheme()) return undefined;

    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!media) return undefined;
    const update = () => setTheme(media.matches ? "dark" : "light");
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, [theme]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;

    async function loadWorkspace() {
      setConversationLoading(true);
      setChatError("");
      try {
        const items = await api.listConversations();
        if (cancelled) return;
        setConversations(items);

        const rememberedId = Number(localStorage.getItem(CONVERSATION_KEY));
        const remembered = items.find((item) => item.id === rememberedId);
        if (!remembered) {
          setConversationId(null);
          setMessages([]);
          localStorage.removeItem(CONVERSATION_KEY);
          return;
        }

        const matchedPersona = personaMeta(remembered.persona).id;
        setPersona(matchedPersona);
        localStorage.setItem(PERSONA_KEY, matchedPersona);
        setConversationId(remembered.id);
        setHistoryLoading(true);
        const history = await api.listMessages(remembered.id);
        if (!cancelled) setMessages(history.map(messageFromApi));
      } catch (error) {
        if (!cancelled && error.status !== 401) setChatError(error.message);
      } finally {
        if (!cancelled) {
          setConversationLoading(false);
          setHistoryLoading(false);
        }
      }
    }

    loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function signIn({ email, password, name, registering }) {
    if (registering) await api.register({ email, password, name });
    const result = await api.login({ email, password });
    api.setToken(result.access_token);
    const currentUser = await api.me();
    setBackendUp(true);
    setChatError("");
    setUser(currentUser);
  }

  function logout() {
    api.clearToken();
    setUser(null);
    setConversations([]);
    setMessages([]);
    setConversationId(null);
    setSuggestion(null);
    setChatError("");
    setHistoryLoading(false);
    setConversationLoading(false);
    setSidebarOpen(false);
    setSettingsOpen(false);
    localStorage.removeItem(CONVERSATION_KEY);
  }

  async function retryBackend() {
    const online = await api.health();
    setBackendUp(online);
    if (online) setChatError("");
  }

  function startNewChat(nextPersona = persona) {
    setPersona(nextPersona);
    localStorage.setItem(PERSONA_KEY, nextPersona);
    setConversationId(null);
    setMessages([]);
    setSuggestion(null);
    setChatError("");
    localStorage.removeItem(CONVERSATION_KEY);
    setSidebarOpen(false);
  }

  async function openConversation(conversation) {
    const nextPersona = personaMeta(conversation.persona).id;
    setPersona(nextPersona);
    localStorage.setItem(PERSONA_KEY, nextPersona);
    setConversationId(conversation.id);
    localStorage.setItem(CONVERSATION_KEY, String(conversation.id));
    setMessages([]);
    setSuggestion(null);
    setChatError("");
    setHistoryLoading(true);
    setSidebarOpen(false);
    try {
      const history = await api.listMessages(conversation.id);
      setMessages(history.map(messageFromApi));
    } catch (error) {
      if (error.status !== 401) setChatError(error.message);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function sendMessage(text) {
    setChatError("");
    setSuggestion(null);
    setMessages((current) => [
      ...current,
      { role: "user", text },
      { role: "assistant", text: "", streaming: true },
    ]);

    try {
      await api.streamChat(
        {
          persona,
          message: text,
          ...(conversationId ? { conversation_id: conversationId } : {}),
        },
        (event) => {
          if (event.type === "meta") {
            if (event.conversation_id) {
              setConversationId(event.conversation_id);
              localStorage.setItem(CONVERSATION_KEY, String(event.conversation_id));
              setConversations((current) => {
                if (current.some((item) => item.id === event.conversation_id)) {
                  return current;
                }
                return [
                  {
                    id: event.conversation_id,
                    persona,
                    created_at: new Date().toISOString(),
                  },
                  ...current,
                ];
              });
            }
            setSuggestion(event.suggestion || null);
            setMessages((current) => {
              const next = [...current];
              const last = { ...next[next.length - 1] };
              last.crisis = Boolean(event.crisis);
              last.disclaimer = event.disclaimer || null;
              next[next.length - 1] = last;
              return next;
            });
          } else if (event.type === "token") {
            setMessages((current) => {
              const next = [...current];
              const last = { ...next[next.length - 1] };
              last.text += event.text || "";
              next[next.length - 1] = last;
              return next;
            });
          } else if (event.type === "done") {
            setMessages((current) => {
              const next = [...current];
              const last = { ...next[next.length - 1], streaming: false };
              next[next.length - 1] = last;
              return next;
            });
          }
        },
      );
    } catch (error) {
      if (error.status === 401) return;
      setChatError(error.message);
      setMessages((current) => {
        const next = [...current];
        const last = next[next.length - 1];
        if (last?.role === "assistant" && last.streaming) {
          next[next.length - 1] = {
            ...last,
            streaming: false,
            text: last.text || "I couldn't complete that reply. Please try again.",
            failed: true,
          };
        }
        return next;
      });
    }
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    persistTheme(nextTheme);
  }

  const switchSuggestion = suggestion
    ? `${personaMeta(suggestion.persona).name}: ${suggestion.reason}`
    : "";

  if (!authReady) {
    return (
      <main className="app-loading" aria-live="polite">
        <div className="loading-mark" aria-hidden="true">m</div>
        <p>Preparing your space…</p>
      </main>
    );
  }

  if (!user) {
    return (
      <AuthScreen
        backendUp={backendUp}
        onSubmit={signIn}
        initialError={chatError}
      />
    );
  }

  return (
    <div className={`app-shell ${sidebarOpen ? "sidebar-is-open" : ""}`}>
      {sidebarOpen && (
        <button
          className="drawer-scrim"
          type="button"
          aria-label="Close navigation menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <Sidebar
        activePersona={persona}
        conversations={conversations}
        currentConversationId={conversationId}
        user={user}
        onNewChat={startNewChat}
        onOpenConversation={openConversation}
        onSelectPersona={(selectedPersona) => startNewChat(selectedPersona)}
        onSettings={() => {
          setSettingsOpen(true);
          setSidebarOpen(false);
        }}
        onLogout={logout}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="main-panel">
        <header className="topbar">
          <button
            className="icon-button mobile-menu-button"
            type="button"
            aria-label="Open navigation menu"
            onClick={() => setSidebarOpen(true)}
          >
            <span className="menu-glyph" aria-hidden="true">☰</span>
          </button>
          <div className="topbar-persona">
            <span className="topbar-eyebrow">YOUR SPACE WITH</span>
            <strong>{personaMeta(persona).name}</strong>
          </div>
          <div className="topbar-actions">
            <span className={`connection-status ${backendUp ? "is-online" : ""}`}>
              <span aria-hidden="true" />
              {backendUp === null ? "Connecting" : backendUp ? "Online" : "Offline"}
            </span>
            <button
              type="button"
              className="icon-button theme-toggle"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              <span aria-hidden="true">{theme === "dark" ? "☀" : "◐"}</span>
            </button>
          </div>
        </header>

        {backendUp === false && (
          <div className="offline-banner" role="status">
            <span>
              <strong>Can’t reach Mosaic right now.</strong> Check that the backend is running, then try again.
            </span>
            <button type="button" onClick={retryBackend}>Retry</button>
          </div>
        )}

        {chatError && backendUp !== false && (
          <div className="inline-alert" role="alert">
            {chatError}
            <button type="button" onClick={() => setChatError("")} aria-label="Dismiss error">×</button>
          </div>
        )}

        {suggestion && (
          <div className="suggestion-banner" role="status">
            <span>
              <strong>Switch to {personaMeta(suggestion.persona).name}?</strong>
              <span className="suggestion-reason">{suggestion.reason}</span>
            </span>
            <div className="suggestion-actions">
              <button
                type="button"
                className="suggestion-accept"
                onClick={() => startNewChat(suggestion.persona)}
              >
                Accept
              </button>
              <button type="button" onClick={() => setSuggestion(null)}>Dismiss</button>
            </div>
          </div>
        )}

        <ChatView
          persona={persona}
          messages={messages}
          historyLoading={historyLoading || conversationLoading}
          backendUp={backendUp}
          bottomRef={bottomRef}
          onSend={sendMessage}
          disclaimer={messages.find((message) => message.disclaimer)?.disclaimer}
        />
      </main>

      {settingsOpen && (
        <SettingsPanel
          user={user}
          onClose={closeSettings}
          onAccountDeleted={logout}
        />
      )}
      <span className="sr-only" aria-live="polite">
        {switchSuggestion ? `Persona suggestion: ${switchSuggestion}` : ""}
      </span>
    </div>
  );
}
