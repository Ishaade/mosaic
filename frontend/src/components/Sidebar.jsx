import { useState } from "react";
import { PERSONAS } from "../personas.js";
import Avatar from "./Avatar.jsx";

function formatConversationDate(value) {
  if (!value) return "New conversation";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Conversation";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

export default function Sidebar({
  activePersona,
  conversations,
  currentConversationId,
  user,
  onNewChat,
  onOpenConversation,
  onSelectPersona,
  onSettings,
  onLogout,
  onClose,
}) {
  const [expandedPersona, setExpandedPersona] = useState(activePersona);

  function choosePersona(persona) {
    setExpandedPersona(persona);
    onSelectPersona(persona);
  }

  return (
    <aside className="sidebar" aria-label="Main navigation">
      <div className="sidebar-brand-row">
        <div className="brand-lockup sidebar-brand">
          <span className="brand-mark" aria-hidden="true">m</span>
          <span>Mosaic</span>
        </div>
        <button
          type="button"
          className="icon-button sidebar-close"
          onClick={onClose}
          aria-label="Close navigation"
        >
          ×
        </button>
      </div>

      <button
        type="button"
        className="new-chat-button"
        onClick={() => onNewChat(activePersona)}
      >
        <span aria-hidden="true">＋</span> New chat
        <kbd>⌘ K</kbd>
      </button>

      <p className="sidebar-section-label">YOUR PEOPLE</p>
      <nav className="persona-list" aria-label="Conversation personas">
        {PERSONAS.map((item) => {
          const ownChats = conversations.filter(
            (conversation) => conversation.persona === item.id,
          );
          const expanded = expandedPersona === item.id || activePersona === item.id;
          return (
            <section className="persona-group" key={item.id}>
              <button
                type="button"
                className={`persona-contact ${activePersona === item.id ? "is-active" : ""}`}
                aria-expanded={expanded}
                onClick={() => choosePersona(item.id)}
              >
                <Avatar persona={item.id} size={38} />
                <span className="persona-contact-copy">
                  <strong>{item.name}</strong>
                  <span>{item.description}</span>
                </span>
                <span className="persona-chevron" aria-hidden="true">{expanded ? "⌄" : "›"}</span>
              </button>
              {expanded && (
                <div className="persona-chats">
                  {ownChats.length ? (
                    ownChats.map((conversation) => (
                      <button
                        type="button"
                        className={`conversation-link ${conversation.id === currentConversationId ? "is-current" : ""}`}
                        key={conversation.id}
                        onClick={() => onOpenConversation(conversation)}
                      >
                        <span className="conversation-dot" aria-hidden="true" />
                        <span>Conversation</span>
                        <time>{formatConversationDate(conversation.created_at)}</time>
                      </button>
                    ))
                  ) : (
                    <p className="no-conversations">No conversations yet</p>
                  )}
                  <button
                    type="button"
                    className="persona-new-chat"
                    onClick={() => onNewChat(item.id)}
                  >
                    + New chat
                  </button>
                </div>
              )}
            </section>
          );
        })}
      </nav>

      <div className="sidebar-bottom">
        <button type="button" className="sidebar-action" onClick={onSettings}>
          <span aria-hidden="true">⚙</span>
          <span>Memories & privacy</span>
        </button>
        <div className="account-row">
          <span className="account-avatar" aria-hidden="true">
            {(user?.name || user?.email || "M").charAt(0).toUpperCase()}
          </span>
          <span className="account-copy">
            <strong>{user?.name || "Your account"}</strong>
            <span>{user?.email}</span>
          </span>
          <button
            type="button"
            className="logout-button"
            onClick={onLogout}
            aria-label="Log out"
            title="Log out"
          >
            ↪
          </button>
        </div>
      </div>
    </aside>
  );
}
