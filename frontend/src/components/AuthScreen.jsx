import { useState } from "react";

export default function AuthScreen({ backendUp, onSubmit, initialError = "" }) {
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await onSubmit({ email: email.trim(), password, name: name.trim(), registering });
    } catch (submitError) {
      setError(submitError.message || "We couldn’t sign you in. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function changeMode() {
    setRegistering((value) => !value);
    setError("");
    setPassword("");
  }

  return (
    <main className="auth-screen">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">m</span>
          <span>Mosaic</span>
        </div>
        <p className="auth-eyebrow">A little space to think</p>
        <h1 id="auth-title">{registering ? "Create your space" : "Welcome back"}</h1>
        <p className="auth-subtitle">
          {registering
            ? "A thoughtful conversation can start here."
            : "Pick up where you left off, at your own pace."}
        </p>

        {backendUp === false && (
          <div className="auth-alert" role="status">
            The Mosaic server is offline. You can try again once it’s available.
          </div>
        )}
        {(error || initialError) && (
          <div className="auth-alert error-alert" role="alert">
            {error || initialError}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          {registering && (
            <label>
              Name <span className="optional-label">Optional</span>
              <input
                autoComplete="name"
                name="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={100}
                placeholder="What should we call you?"
              />
            </label>
          )}
          <label>
            Email
            <input
              autoComplete="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              maxLength={255}
              placeholder="you@example.com"
            />
          </label>
          <label>
            Password
            <input
              autoComplete={registering ? "new-password" : "current-password"}
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={registering ? 8 : 1}
              maxLength={128}
              placeholder={registering ? "At least 8 characters" : "Your password"}
            />
            {registering && <span className="field-hint">Use at least 8 characters.</span>}
          </label>
          <button className="primary-button auth-submit" type="submit" disabled={loading}>
            {loading
              ? registering ? "Creating your account…" : "Signing in…"
              : registering ? "Create account" : "Sign in"}
          </button>
        </form>

        <p className="auth-switch">
          {registering ? "Already have a space?" : "New to Mosaic?"}{" "}
          <button type="button" onClick={changeMode} disabled={loading}>
            {registering ? "Sign in" : "Create an account"}
          </button>
        </p>
        <p className="auth-footnote">Your conversations are personal. Take your time.</p>
      </section>
    </main>
  );
}
