import { useEffect, useRef, useState } from "react";
import * as api from "../api.js";
import { personaMeta } from "../personas.js";

export default function SettingsPanel({ user, onClose, onAccountDeleted }) {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [deletingAll, setDeletingAll] = useState(false);
  const dialogRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api.listMemories()
      .then((items) => {
        if (!cancelled) setMemories(items);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const previousFocus = document.activeElement;
    const dialog = dialogRef.current;
    const focusable = () =>
      [...(dialog?.querySelectorAll(
        'button:not(:disabled), [href], input:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      ) || [])];
    focusable()[0]?.focus();

    function trapFocus(event) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", trapFocus);
    return () => {
      document.removeEventListener("keydown", trapFocus);
      previousFocus?.focus?.();
    };
  }, [onClose]);

  async function removeMemory(memory) {
    setBusyId(memory.id);
    setError("");
    try {
      await api.deleteMemory(memory.id);
      setMemories((items) => items.filter((item) => item.id !== memory.id));
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setBusyId("");
    }
  }

  async function removeAllMemories() {
    if (!memories.length || !window.confirm("Delete all saved memories? Your conversations will remain.")) {
      return;
    }
    setDeletingAll(true);
    setError("");
    try {
      await api.deleteAllMemories();
      setMemories([]);
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setDeletingAll(false);
    }
  }

  async function removeAccount() {
    const confirmed = window.confirm(
      "Permanently delete your account, conversations, and saved memories? This cannot be undone.",
    );
    if (!confirmed) return;
    setError("");
    setDeletingAll(true);
    try {
      await api.deleteAccount();
      api.clearToken();
      onAccountDeleted();
    } catch (deleteError) {
      setError(deleteError.message);
      setDeletingAll(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section
        ref={dialogRef}
        className="settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <header className="settings-header">
          <div>
            <span className="section-kicker">YOUR SPACE</span>
            <h2 id="settings-title">Memories & privacy</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close settings">
            ×
          </button>
        </header>
        <div className="settings-scroll">
          <p className="settings-intro">
            Mosaic may save helpful details to make future conversations more personal.
            You’re in control of what stays.
          </p>
          <div className="memory-section-heading">
            <div>
              <h3>What Mosaic remembers</h3>
              <p>{loading ? "Loading your memories…" : `${memories.length} saved ${memories.length === 1 ? "memory" : "memories"}`}</p>
            </div>
            <button
              type="button"
              className="text-danger"
              onClick={removeAllMemories}
              disabled={loading || !memories.length || deletingAll}
            >
              {deletingAll ? "Deleting…" : "Delete all"}
            </button>
          </div>

          {error && <div className="settings-error" role="alert">{error}</div>}
          {loading ? (
            <div className="settings-loading" role="status">
              <span className="loading-spinner" aria-hidden="true" /> Loading memories
            </div>
          ) : memories.length ? (
            <ul className="memory-list">
              {memories.map((memory) => (
                <li key={memory.id} className="memory-card">
                  <div className="memory-card-copy">
                    <span className="memory-persona">{personaMeta(memory.persona).name} · {memory.kind}</span>
                    <p>{memory.text}</p>
                  </div>
                  <button
                    type="button"
                    className="memory-delete"
                    onClick={() => removeMemory(memory)}
                    disabled={busyId === memory.id}
                    aria-label={`Delete memory: ${memory.text}`}
                  >
                    {busyId === memory.id ? "…" : "Delete"}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="memory-empty">
              <span aria-hidden="true">✧</span>
              <strong>Nothing saved just yet</strong>
              <p>When Mosaic remembers something helpful, you’ll find it here.</p>
            </div>
          )}

          <div className="account-settings">
            <h3>Account</h3>
            <p>{user?.email}</p>
            <button
              type="button"
              className="text-danger account-delete"
              onClick={removeAccount}
              disabled={deletingAll}
            >
              Delete account and all data
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
