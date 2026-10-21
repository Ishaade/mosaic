/**
 * Centralized API access.
 *
 * The access token is held in memory and persisted in localStorage so a refresh
 * keeps the user signed in. localStorage is readable by same-origin JavaScript,
 * so XSS could steal the token; an httpOnly cookie is the safer production
 * option.
 */

const API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "mosaic_token";

let token = localStorage.getItem(TOKEN_KEY);
let onUnauthorized = () => {};
let onConnectivityChange = () => {};

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken() {
  return token;
}

export function setToken(value) {
  token = value || null;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function clearToken() {
  setToken(null);
}

export function setOnUnauthorized(callback) {
  onUnauthorized = callback || (() => {});
}

export function setOnConnectivityChange(callback) {
  onConnectivityChange = callback || (() => {});
}

function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function messageFromBody(body, fallback) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
    return body.detail[0].msg;
  }
  return fallback;
}

async function handleResponse(response) {
  if (response.status === 401) {
    const hadToken = Boolean(token);
    clearToken();
    if (hadToken) onUnauthorized();
    const body = await response.json().catch(() => ({}));
    throw new ApiError(messageFromBody(body, "Please sign in again."), 401);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      messageFromBody(body, `Request failed (${response.status})`),
      response.status,
    );
  }
  if (response.status === 204) return null;
  return response.json();
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: { ...authHeaders(), ...options.headers },
    });
  } catch {
    onConnectivityChange(false);
    throw new ApiError("Cannot reach the server. Is the backend running?");
  }
  onConnectivityChange(true);
  return handleResponse(response);
}

export async function health() {
  try {
    const response = await fetch(`${API_URL}/health`, {
      headers: authHeaders(),
    });
    onConnectivityChange(response.ok);
    return response.ok;
  } catch {
    onConnectivityChange(false);
    return false;
  }
}

export function register({ email, password, name }) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name: name || null }),
  });
}

export function login({ email, password }) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function me() {
  return request("/auth/me");
}

export function deleteAccount() {
  return request("/auth/me", { method: "DELETE" });
}

export function listConversations() {
  return request("/conversations");
}

export function listMessages(conversationId) {
  return request(`/conversations/${conversationId}/messages`);
}

export function listMemories() {
  return request("/memories");
}

export function deleteMemory(id) {
  return request(`/memories/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function deleteAllMemories() {
  return request("/memories", { method: "DELETE" });
}

export async function streamChat(body, onEvent) {
  let response;
  try {
    response = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
  } catch {
    onConnectivityChange(false);
    throw new ApiError("Cannot reach the server. Is the backend running?");
  }
  onConnectivityChange(true);

  if (response.status === 401) {
    const hadToken = Boolean(token);
    clearToken();
    if (hadToken) onUnauthorized();
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(messageFromBody(errorBody, "Please sign in again."), 401);
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiError(
      messageFromBody(errorBody, `Server returned ${response.status}`),
      response.status,
    );
  }
  if (!response.body) throw new ApiError("The server did not return a response stream.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let streamError = null;
  let sawDone = false;

  function consumeEvents(final = false) {
    const chunks = buffer.split(/\r?\n\r?\n/);
    buffer = final ? "" : chunks.pop() || "";
    for (const chunk of chunks) {
      for (const line of chunk.split(/\r?\n/)) {
        if (!line.startsWith("data:")) continue;
        let event;
        try {
          event = JSON.parse(line.slice(5).trim());
        } catch {
          throw new ApiError("The server sent an unreadable response.");
        }
        if (event.type === "error") {
          streamError = new ApiError(
            event.detail || "The server could not complete this reply.",
            event.status || 0,
          );
          if (event.status === 401) {
            const hadToken = Boolean(token);
            clearToken();
            if (hadToken) onUnauthorized();
          }
          continue;
        }
        if (event.type === "done") sawDone = true;
        onEvent(event);
      }
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      consumeEvents();
    }
    buffer += decoder.decode();
    consumeEvents(true);
  } finally {
    reader.releaseLock();
  }
  if (streamError) throw streamError;
  if (!sawDone) {
    throw new ApiError("The connection ended before the reply was complete.");
  }
}
