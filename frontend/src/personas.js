/** Display metadata for the four Mosaic personas (sidebar "contacts"). */

export const PERSONAS = [
  {
    id: "therapist",
    name: "Listener",
    description: "Calm, non-judgmental support",
    emoji: "🌿",
    color: "#5b8c6a",
  },
  {
    id: "tutor",
    name: "Tutor",
    description: "Patient, step-by-step help",
    emoji: "📚",
    color: "#4a7ab5",
  },
  {
    id: "parent",
    name: "Parent",
    description: "Warm, practical guidance",
    emoji: "🏡",
    color: "#c47a3a",
  },
  {
    id: "friend",
    name: "Friend",
    description: "Casual, honest company",
    emoji: "☀️",
    color: "#6b5bb8",
  },
];

export function personaMeta(id) {
  return PERSONAS.find((p) => p.id === id) || PERSONAS[3];
}
