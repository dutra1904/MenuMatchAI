"use client";

import type { ReactNode } from "react";
import { BUDGETS, DIETS, EMPTY_PROFILE, ZONES, preferenceSummary, type Profile } from "@/lib/profile";

export function ProfileBar({ profile, onChange }: { profile: Profile; onChange: (profile: Profile) => void }) {
  const summary = preferenceSummary(profile);
  const active = summary.length > 0 || profile.name.trim().length > 0;

  function toggleZone(id: string) {
    onChange({ ...profile, zone: profile.zone === id ? "" : id });
  }

  function toggleDiet(id: string) {
    const selected = profile.diets.includes(id);
    let diets = selected ? profile.diets.filter((item) => item !== id) : [...profile.diets, id];
    if (!selected && id === "vegan") diets = diets.filter((item) => item !== "vegetarian");
    if (!selected && id === "vegetarian") diets = diets.filter((item) => item !== "vegan");
    onChange({ ...profile, diets });
  }

  return (
    <section className="mt-5 rounded-[28px] border border-line bg-card/90 p-4 shadow-ticket">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-clay">Seu jeito de pedir</p>
          <p className="mt-1 text-sm text-ink/70">
            {summary.length
              ? `Levo em cada busca: ${summary.join(" · ")}.`
              : "Marque região, restrição, pressa e teto. A próxima frase já sai com isso."}
          </p>
        </div>
        {active && (
          <button
            type="button"
            onClick={() => onChange(EMPTY_PROFILE)}
            className="rounded-full border border-line px-3 py-1.5 text-xs text-ink/70 hover:border-clay/40 hover:text-ink"
          >
            Limpar
          </button>
        )}
      </div>

      <label className="mt-4 block text-xs text-ink/50" htmlFor="nome">
        Como te chamo
      </label>
      <input
        id="nome"
        value={profile.name}
        maxLength={32}
        onChange={(event) => onChange({ ...profile, name: event.target.value })}
        placeholder="Seu nome"
        className="mt-1 w-full max-w-xs rounded-full border border-line bg-paper px-4 py-2 text-sm outline-none ring-clay/30 focus:ring-2"
      />

      <fieldset className="mt-4">
        <legend className="text-xs text-ink/50">Onde entrega</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {ZONES.map((zone) => (
            <Chip key={zone.id} active={profile.zone === zone.id} onClick={() => toggleZone(zone.id)}>
              {zone.label}
            </Chip>
          ))}
        </div>
      </fieldset>

      <fieldset className="mt-4">
        <legend className="text-xs text-ink/50">Restrição</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {DIETS.map((diet) => (
            <Chip key={diet.id} active={profile.diets.includes(diet.id)} onClick={() => toggleDiet(diet.id)}>
              {diet.label}
            </Chip>
          ))}
        </div>
      </fieldset>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <fieldset>
          <legend className="text-xs text-ink/50">Teto do prato</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip active={profile.budget == null} onClick={() => onChange({ ...profile, budget: null })}>
              Sem teto
            </Chip>
            {BUDGETS.map((budget) => (
              <Chip
                key={budget}
                active={profile.budget === budget}
                onClick={() => onChange({ ...profile, budget: profile.budget === budget ? null : budget })}
              >
                R$ {budget}
              </Chip>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend className="text-xs text-ink/50">Pressa</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip active={profile.pace === "any"} onClick={() => onChange({ ...profile, pace: "any" })}>
              Tanto faz
            </Chip>
            <Chip active={profile.pace === "fast"} onClick={() => onChange({ ...profile, pace: "fast" })}>
              Rápido
            </Chip>
          </div>
        </fieldset>
        <fieldset>
          <legend className="text-xs text-ink/50">Clima do prato</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip active={profile.mood === "any"} onClick={() => onChange({ ...profile, mood: "any" })}>
              Tanto faz
            </Chip>
            <Chip active={profile.mood === "light"} onClick={() => onChange({ ...profile, mood: "light" })}>
              Leve
            </Chip>
            <Chip active={profile.mood === "hearty"} onClick={() => onChange({ ...profile, mood: "hearty" })}>
              Caprichado
            </Chip>
          </div>
        </fieldset>
      </div>
    </section>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-sm transition ${
        active ? "border-clay bg-clay text-white" : "border-line bg-paper text-ink hover:border-clay/40"
      }`}
    >
      {children}
    </button>
  );
}
