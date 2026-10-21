import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { personaMeta } from "../personas.js";
import Avatar from "./Avatar.jsx";

function Message({ message, persona }) {
  const isUser = message.role === "user";
  const isError = message.failed;
  return (
    <article
      className={`message-row ${isUser ? "user-row" : "assistant-row"} ${message.crisis ? "crisis-message" : ""} ${isError ? "failed-message" : ""}`}
      aria-label={isUser ? "Your message" : `${personaMeta(persona).name} reply`}
    >
      {!isUser && <Avatar persona={persona} size={34} />}
      <div className={`message-bubble ${isUser ? "user-bubble" : "assistant-bubble"}`}>
        {message.crisis && <span className="crisis-label">Urgent support</span>}
        {message.text ? (
          <div className="markdown-content">
            <ReactMarkdown>{message.text}</ReactMarkdown>
          </div>
        ) : message.streaming ? (
          <span className="typing-indicator" aria-label="Writing a reply">
            <i /><i /><i />
          </span>
        ) : null}
        {message.streaming && message.text && (
          <span className="streaming-cursor" aria-label="Reply is still being written" />
        )}
      </div>
      {isUser && <Avatar persona={persona} user size={34} />}
    </article>
  );
}

export default function ChatView({
  persona,
  messages,
  historyLoading,
  backendUp,
  bottomRef,
  onSend,
  disclaimer,
}) {
  const [input, setInput] = useState("");
  const textareaRef = useRef(null);
  const sending = messages.at(-1)?.role === "assistant" && messages.at(-1)?.streaming;
  const disabled = historyLoading || backendUp === false;

  function updateInput(event) {
    setInput(event.target.value);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 180)}px`;
  }

  function submit(event) {
    event.preventDefault();
    const text = input.trim();
    if (!text || sending || disabled) return;
    onSend(text);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  const meta = personaMeta(persona);
  const currentDisclaimer =
    disclaimer ||
    "Mosaic is an AI, not a licensed therapist. It can offer support, but can’t diagnose or treat.";

  return (
    <section className="chat-stage" aria-label={`Chat with ${meta.name}`}>
      <div className="chat-column">
        <div className="chat-heading">
          <span className="chat-heading-kicker">A CONVERSATION WITH</span>
          <h1>{meta.name}</h1>
          <p>{meta.description}</p>
        </div>

        {persona === "therapist" && (
          <aside className="therapist-disclaimer" role="note">
            <span className="disclaimer-icon" aria-hidden="true">✳</span>
            <span>{currentDisclaimer}</span>
          </aside>
        )}

        <div className="messages-scroll" aria-live="polite" aria-relevant="additions text">
          {historyLoading ? (
            <div className="history-loading" role="status">
              <span className="loading-spinner" aria-hidden="true" />
              Opening your conversation…
            </div>
          ) : messages.length === 0 ? (
            <div className="empty-chat">
              <Avatar persona={persona} size={54} />
              <h2>What’s on your mind?</h2>
              <p>
                {backendUp === false
                  ? "Your conversation will be ready when Mosaic is back online."
                  : `Start wherever you are. ${meta.name} is here to listen.`}
              </p>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message, index) => (
                <Message
                  key={message.id || `${message.role}-${index}`}
                  message={message}
                  persona={persona}
                />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="chat-input">
            Message {meta.name}
          </label>
          <textarea
            id="chat-input"
            ref={textareaRef}
            value={input}
            onChange={updateInput}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${meta.name}…`}
            maxLength={2000}
            rows={1}
            disabled={disabled}
            aria-describedby="composer-help"
          />
          <div className="composer-footer">
            <span id="composer-help">Enter to send · Shift + Enter for a new line</span>
            <button
              className="send-button"
              type="submit"
              disabled={disabled || sending || !input.trim()}
              aria-label={sending ? "Reply in progress" : "Send message"}
            >
              <span>{sending ? "Thinking" : "Send"}</span>
              {!sending && <span aria-hidden="true">↑</span>}
            </button>
          </div>
        </form>
        <p className="privacy-note">
          Mosaic can make mistakes. For urgent help, contact your local emergency service.
        </p>
      </div>
    </section>
  );
}
