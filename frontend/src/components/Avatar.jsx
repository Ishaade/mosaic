import { personaMeta } from "../personas.js";

export default function Avatar({ persona, size = 36, user = false, label }) {
  const meta = personaMeta(persona);
  const style = {
    width: size,
    height: size,
    fontSize: size * 0.45,
    background: user ? "var(--user-avatar)" : meta.color,
  };
  return (
    <span
      className="avatar"
      style={style}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      title={label || (user ? "You" : meta.name)}
    >
      {user ? "You"[0] : meta.emoji}
    </span>
  );
}
