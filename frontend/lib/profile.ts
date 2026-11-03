export const ZONES = [
  { id: "centro", label: "Centro", phrase: "no centro" },
  { id: "zona_sul", label: "Zona Sul", phrase: "na zona sul" },
  { id: "zona_norte", label: "Zona Norte", phrase: "na zona norte" },
  { id: "zona_oeste", label: "Zona Oeste", phrase: "na zona oeste" },
  { id: "zona_leste", label: "Zona Leste", phrase: "na zona leste" },
] as const;

export const DIETS = [
  { id: "lactose", label: "Sem lactose", phrase: "sem lactose" },
  { id: "gluten", label: "Sem glúten", phrase: "sem glúten" },
  { id: "vegan", label: "Vegano", phrase: "vegano" },
  { id: "vegetarian", label: "Vegetariano", phrase: "vegetariano" },
] as const;

export const BUDGETS = [30, 40, 60] as const;

export type Pace = "any" | "fast";
export type Mood = "any" | "light" | "hearty";

export type Profile = {
  name: string;
  zone: string;
  diets: string[];
  budget: number | null;
  pace: Pace;
  mood: Mood;
};

export const EMPTY_PROFILE: Profile = {
  name: "",
  zone: "",
  diets: [],
  budget: null,
  pace: "any",
  mood: "any",
};

const STORAGE_KEY = "mm-profile";

export const DEFAULT_SUGGESTIONS = [
  "Quero algo sem lactose, rápido e por menos de R$ 40",
  "Um poke ou sushi sem glúten na zona sul",
  "Opção vegana e leve para o almoço",
];

const CONTROL =
  /^(confirmar( o pedido)?|sim,? confirmar|outra opcao|outro|mais barato|mais rapido|troca)$/;

export function fold(value: string) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

export function loadProfile(): Profile {
  if (typeof window === "undefined") return EMPTY_PROFILE;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_PROFILE;
    const parsed = JSON.parse(raw) as Partial<Profile>;
    return {
      name: typeof parsed.name === "string" ? parsed.name.slice(0, 32) : "",
      zone: ZONES.some((zone) => zone.id === parsed.zone) ? String(parsed.zone) : "",
      diets: Array.isArray(parsed.diets)
        ? parsed.diets.filter((id): id is string => DIETS.some((diet) => diet.id === id))
        : [],
      budget: BUDGETS.some((value) => value === parsed.budget) ? (parsed.budget as number) : null,
      pace: parsed.pace === "fast" ? "fast" : "any",
      mood: parsed.mood === "light" || parsed.mood === "hearty" ? parsed.mood : "any",
    };
  } catch {
    return EMPTY_PROFILE;
  }
}

export function saveProfile(profile: Profile) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  window.dispatchEvent(new Event("mm-profile"));
}

export function firstName(profile: Profile) {
  return profile.name.trim().split(/\s+/)[0] || "";
}

export function greeting(name: string, now = new Date()) {
  const hour = now.getHours();
  const hello = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
  const who = name.trim().split(/\s+/)[0];
  return who ? `${hello}, ${who}` : hello;
}

export function preferenceSummary(profile: Profile) {
  const parts: string[] = [];
  const zone = ZONES.find((item) => item.id === profile.zone);
  if (zone) parts.push(zone.label);
  for (const diet of DIETS) {
    if (profile.diets.includes(diet.id)) parts.push(diet.label.toLowerCase());
  }
  if (profile.budget) parts.push(`até R$ ${profile.budget}`);
  if (profile.pace === "fast") parts.push("rápido");
  if (profile.mood === "light") parts.push("leve");
  if (profile.mood === "hearty") parts.push("caprichado");
  return parts;
}

export function isControlMessage(message: string) {
  return CONTROL.test(fold(message));
}

export function enrichMessage(message: string, profile: Profile) {
  const trimmed = message.trim();
  if (!trimmed || isControlMessage(trimmed)) return trimmed;

  const folded = fold(trimmed);
  const hints: string[] = [];
  const mentionsZone = ZONES.some((zone) => folded.includes(fold(zone.label)));
  const zone = ZONES.find((item) => item.id === profile.zone);
  if (zone && !mentionsZone) hints.push(zone.phrase);

  const mentionsDiet = /\bveganas?\b|\bveganos?\b|\bvegetarian/.test(folded);
  if (!mentionsDiet) {
    const diet = DIETS.find((item) => profile.diets.includes(item.id) && (item.id === "vegan" || item.id === "vegetarian"));
    if (diet) hints.push(diet.phrase);
  }
  for (const diet of DIETS) {
    if (diet.id !== "lactose" && diet.id !== "gluten") continue;
    if (profile.diets.includes(diet.id) && !folded.includes(fold(diet.phrase))) hints.push(diet.phrase);
  }
  if (profile.budget != null && !/\d/.test(trimmed)) hints.push(`por menos de R$ ${profile.budget}`);
  if (profile.pace === "fast" && !/\brapid|\bmin/.test(folded)) hints.push("rápido");
  if (profile.mood === "light" && !folded.includes("leve") && !folded.includes("caprichado")) hints.push("leve");
  if (profile.mood === "hearty" && !folded.includes("caprichado") && !folded.includes("leve")) hints.push("caprichado");

  if (!hints.length) return trimmed;
  return `${trimmed}. ${hints.join(", ")}`;
}

export function buildSuggestions(profile: Profile) {
  const parts = preferenceSummary(profile);
  if (!parts.length) return DEFAULT_SUGGESTIONS;

  const zone = ZONES.find((item) => item.id === profile.zone);
  const diet = DIETS.find((item) => profile.diets.includes(item.id) && (item.id === "vegan" || item.id === "vegetarian"));
  const allergen = DIETS.filter((item) => (item.id === "lactose" || item.id === "gluten") && profile.diets.includes(item.id)).map(
    (item) => item.phrase,
  );
  const tone = profile.mood === "light" ? "leve" : profile.mood === "hearty" ? "caprichado" : "";
  const speed = profile.pace === "fast" ? "rápido" : "";
  const cap = profile.budget ? `por menos de R$ ${profile.budget}` : "";
  const place = zone?.phrase || "";

  const main = ["Quero algo", ...allergen, diet?.phrase || "", tone, speed, cap, place].filter(Boolean).join(" ");
  const second = ["Quero um prato", tone === "leve" ? "caprichado" : "leve", ...allergen, place].filter(Boolean).join(" ");
  const third = ["Me indica um prato para agora", speed, diet?.phrase || "", place].filter(Boolean).join(" ");
  return [main, second, third];
}

export function orderPhrase(name: string, qty: number, zoneId: string) {
  const zone = ZONES.find((item) => item.id === zoneId);
  const item = qty <= 1 ? name : `${qty} unidades de ${name}`;
  return `Monta o pedido com ${item}${zone ? ` ${zone.phrase}` : ""}`;
}
