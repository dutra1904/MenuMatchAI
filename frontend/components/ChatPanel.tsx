"use client";

import { FormEvent, useEffect, useRef, useState, type ReactNode } from "react";
import { ProfileBar } from "@/components/ProfileBar";
import {
  brl,
  createOrder,
  getHealth,
  getRestaurants,
  sendChat,
  type Dish,
  type Health,
  type Order,
  type Restaurant,
} from "@/lib/api";
import {
  ZONES,
  buildSuggestions,
  enrichMessage,
  firstName,
  greeting,
  isControlMessage,
  orderPhrase,
  preferenceSummary,
} from "@/lib/profile";
import { useProfile } from "@/lib/useProfile";

type UiMessage = {
  role: "user" | "assistant";
  content: string;
  sent?: string;
  recommendations?: Dish[];
  meta?: { latency_ms: number; provider: string; tools_used: string[] };
};

const PROVIDERS: Record<string, string> = {
  local: "orquestrador local",
  "langchain-gemini": "Gemini via LangChain",
  "langchain-openai": "GPT via LangChain",
};

const TOOLS: Record<string, string> = {
  search_menu: "busca semântica",
  calculate_order: "cálculo do pedido",
  create_order: "registro do pedido",
};

export function ChatPanel() {
  const { profile, setProfile } = useProfile();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [offline, setOffline] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef(profile);
  profileRef.current = profile;

  const who = firstName(profile);
  const summary = preferenceSummary(profile);
  const suggestions = buildSuggestions(profile);
  const servedZones = restaurants.find((restaurant) => restaurant.id === order?.restaurant_id)?.zones ?? [];

  useEffect(() => {
    const stored = sessionStorage.getItem("mm-session");
    if (stored) setSessionId(stored);
    getHealth()
      .then((data) => {
        setHealth(data);
        setOffline(false);
      })
      .catch(() => setOffline(true));
    getRestaurants()
      .then(setRestaurants)
      .catch(() => setRestaurants([]));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function send(text: string) {
    const visible = text.trim();
    if (!visible || loading) return;
    const outbound = enrichMessage(visible, profileRef.current);
    const history = messages.map((item) => ({
      role: item.role,
      content: item.role === "user" ? item.sent || item.content : item.content,
    }));
    setMessages((current) => [...current, { role: "user", content: visible, sent: outbound }]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const data = await sendChat({ message: outbound, session_id: sessionId, history });
      setSessionId(data.session_id);
      sessionStorage.setItem("mm-session", data.session_id);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.reply,
          recommendations: data.recommendations,
          meta: {
            latency_ms: data.latency_ms,
            provider: data.provider,
            tools_used: data.tools_used,
          },
        },
      ]);
      setOrder(data.order);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao falar com o agente.");
    } finally {
      setLoading(false);
    }
  }

  async function confirmOrder() {
    if (!order || order.status === "confirmed" || confirming) return;
    setConfirming(true);
    setError(null);
    try {
      const saved = await createOrder({
        restaurant_id: order.restaurant_id,
        zone: order.zone,
        items: order.items.map((item) => ({ dish_id: item.dish_id, qty: item.qty })),
        dietary_notes: order.dietary_notes,
        customer_query: order.customer_query,
      });
      setOrder(saved);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `Pedido ${saved.id} confirmado no ${saved.restaurant_name}. Total ${brl(saved.total)}. Ele já entrou no painel do restaurante.`,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não consegui confirmar o pedido.");
    } finally {
      setConfirming(false);
    }
  }

  function resetChat() {
    if (loading || confirming) return;
    setMessages([]);
    setOrder(null);
    setSessionId(null);
    setError(null);
    sessionStorage.removeItem("mm-session");
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  const preview = input.trim() ? enrichMessage(input, profile) : "";
  const previewAdds = preview && preview !== input.trim();

  return (
    <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="min-w-0">
        <p className="text-xs uppercase tracking-[0.18em] text-clay">{who ? "Para você" : "Atendimento"}</p>
        <h1 className="mt-2 font-display text-4xl leading-tight sm:text-5xl">
          {who ? greeting(profile.name) : "Diga o que você quer comer."}
        </h1>
        <p className="mt-3 max-w-xl text-ink/70">
          {summary.length
            ? `Cada busca já sai com ${summary.join(", ")}. Escreva o prato, toque numa sugestão ou escolha o restaurante.`
            : "O agente entende restrição, pressa e orçamento, busca no cardápio e devolve o pedido."}
        </p>

        {offline && (
          <p className="mt-4 rounded-2xl border border-clay/30 bg-white px-4 py-3 text-sm">
            A API não respondeu. No diretório backend, suba o servidor com{" "}
            <code className="rounded bg-paper px-1">uvicorn app.main:app --port 8000</code>.
          </p>
        )}

        {health && (
          <p className="mt-4 text-sm text-ink/60">
            {health.dishes} pratos · {health.restaurants} restaurantes · embeddings {health.embedder.toUpperCase()} ·{" "}
            {health.dimensions} dimensões · {PROVIDERS[health.llm] || health.llm}
          </p>
        )}

        <ProfileBar profile={profile} onChange={setProfile} />

        {restaurants.length > 0 && (
          <ul className="mt-5 flex gap-2 overflow-x-auto pb-1">
            {restaurants.map((restaurant) => (
              <li key={restaurant.id} className="shrink-0">
                <button
                  type="button"
                  onClick={() => void send(`Quero algo da cozinha ${restaurant.cuisine.toLowerCase()} no ${restaurant.name}`)}
                  className="rounded-full border border-line bg-card px-3 py-1.5 text-left text-sm transition hover:border-clay/50 hover:bg-white"
                >
                  <span className="font-medium">{restaurant.name}</span>
                  <span className="text-ink/50"> · {restaurant.cuisine}</span>
                  <span className="text-ink/40"> · {restaurant.rating.toLocaleString("pt-BR")}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {messages.length === 0 && (
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => void send(suggestion)}
                className="rounded-2xl border border-line bg-card p-4 text-left text-sm leading-relaxed shadow-ticket transition hover:-translate-y-0.5 hover:border-clay/40"
              >
                <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-clay">Sugestão</span>
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <div className="mt-6 space-y-4">
          {messages.map((message, index) => (
            <article key={`${message.role}-${index}`} className={message.role === "user" ? "flex justify-end" : ""}>
              <div
                className={`max-w-[42rem] rounded-3xl px-4 py-3 ${
                  message.role === "user" ? "bg-clay text-white" : "border border-line bg-card"
                }`}
              >
                {message.content.split("\n\n").map((paragraph, paragraphIndex) => (
                  <p key={paragraphIndex} className="mb-2 last:mb-0 leading-relaxed">
                    {paragraph}
                  </p>
                ))}
                {message.sent && message.sent !== message.content && (
                  <p className="mt-2 text-xs text-white/75">Incluí {addedHints(message.content, message.sent)}</p>
                )}
                {message.recommendations && message.recommendations.length > 0 && (
                  <div className="mt-3 grid gap-2">
                    {message.recommendations.map((dish) => (
                      <div key={dish.id} className="rounded-2xl border border-line bg-paper px-3 py-2 text-ink">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">{dish.name}</p>
                            <p className="mt-1 text-xs leading-relaxed text-ink/60">{dish.description}</p>
                          </div>
                          <p className="shrink-0 text-sm">{brl(dish.price)}</p>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs text-ink/60">
                            {dish.restaurant_name} · {dish.prep_minutes} min
                            {dish.badges.length ? ` · ${dish.badges.join(" · ")}` : ""}
                          </p>
                          <button
                            type="button"
                            onClick={() => void send(orderPhrase(dish.name, 1, profile.zone || order?.zone || ""))}
                            disabled={loading}
                            className="rounded-full bg-ink px-3 py-1.5 text-xs text-paper disabled:opacity-40"
                          >
                            Quero este
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {message.meta && (
                  <p className={`mt-3 text-xs ${message.role === "user" ? "text-white/80" : "text-ink/50"}`}>
                    {message.meta.tools_used.map((tool) => TOOLS[tool] || tool).join(" · ") || "sem ferramenta"} ·{" "}
                    {message.meta.latency_ms} ms · {PROVIDERS[message.meta.provider] || message.meta.provider}
                  </p>
                )}
              </div>
            </article>
          ))}
          {loading && (
            <p className="flex items-center gap-2 text-sm text-ink/60">
              <span className="flex gap-1" aria-hidden>
                <span className="mm-dot" />
                <span className="mm-dot [animation-delay:140ms]" />
                <span className="mm-dot [animation-delay:280ms]" />
              </span>
              {who ? `Olhando o cardápio para ${who}…` : "Consultando o cardápio…"}
            </p>
          )}
          <div ref={endRef} />
        </div>

        {error && <p className="mt-4 text-sm text-clay">{error}</p>}

        <div className="mt-4 flex flex-wrap gap-2">
          <Quick onClick={() => void send("outra opção")} disabled={loading || messages.length === 0}>
            Outra opção
          </Quick>
          <Quick onClick={() => void send("mais barato")} disabled={loading || messages.length === 0}>
            Mais barato
          </Quick>
          <Quick onClick={() => void send("mais rápido")} disabled={loading || messages.length === 0}>
            Mais rápido
          </Quick>
          {order?.status === "draft" && (
            <Quick onClick={() => void confirmOrder()} disabled={confirming || loading}>
              {confirming ? "Registrando…" : "Confirmar pedido"}
            </Quick>
          )}
          {messages.length > 0 && (
            <Quick onClick={resetChat} disabled={loading || confirming}>
              Nova conversa
            </Quick>
          )}
        </div>

        <form onSubmit={onSubmit} className="mt-3 flex gap-2">
          <label className="sr-only" htmlFor="pedido">
            Mensagem para o agente
          </label>
          <input
            id="pedido"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={who ? `${who}, o que vai ser hoje?` : "Ex.: sem lactose, rápido, até R$ 40"}
            className="min-w-0 flex-1 rounded-full border border-line bg-card px-4 py-3 outline-none ring-clay/30 focus:ring-2"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-full bg-ink px-5 py-3 text-sm text-paper disabled:opacity-40"
          >
            Enviar
          </button>
        </form>
        {previewAdds && !isControlMessage(input) && (
          <p className="mt-2 text-xs text-ink/50">Esta mensagem sai assim: {preview}</p>
        )}
      </section>

      <aside className="mm-ticket h-fit rounded-[28px] border border-line bg-card p-5 shadow-ticket lg:sticky lg:top-24">
        <p className="text-xs uppercase tracking-[0.16em] text-ink/50">{who ? `Pedido de ${who}` : "Pedido"}</p>
        {!order && (
          <p className="mt-3 text-sm leading-relaxed text-ink/70">
            {summary.length
              ? "Quando você escolher um prato, o rascunho aparece aqui com região, quantidade e total."
              : "O pedido estruturado aparece aqui quando o agente fechar uma sugestão."}
          </p>
        )}
        {order && (
          <div className="mt-3">
            <h2 className="font-display text-2xl leading-tight">{order.restaurant_name}</h2>
            <p className="text-sm text-ink/60">
              {order.zone_label} · {order.prep_minutes} min · {order.status === "confirmed" ? "confirmado" : "rascunho"}
            </p>
            <ul className="mt-4 space-y-3 border-t border-dashed border-line pt-4 text-sm">
              {order.items.map((item) => (
                <li key={item.dish_id} className="flex items-center justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block">{item.name}</span>
                    <span className="text-xs text-ink/50">{brl(item.unit_price)} cada</span>
                  </span>
                  <span className="flex items-center gap-2">
                    {order.status === "draft" && (
                      <span className="flex items-center rounded-full border border-line">
                        <button
                          type="button"
                          aria-label={`Diminuir ${item.name}`}
                          disabled={loading || item.qty <= 1}
                          onClick={() => void send(orderPhrase(item.name, item.qty - 1, order.zone))}
                          className="h-7 w-7 rounded-full text-base leading-none disabled:opacity-30"
                        >
                          −
                        </button>
                        <span className="w-4 text-center text-xs">{item.qty}</span>
                        <button
                          type="button"
                          aria-label={`Aumentar ${item.name}`}
                          disabled={loading || item.qty >= 10}
                          onClick={() => void send(orderPhrase(item.name, item.qty + 1, order.zone))}
                          className="h-7 w-7 rounded-full text-base leading-none disabled:opacity-30"
                        >
                          +
                        </button>
                      </span>
                    )}
                    <span>{brl(item.unit_price * item.qty)}</span>
                  </span>
                </li>
              ))}
            </ul>
            {order.status === "draft" && servedZones.length > 1 && order.items[0] && (
              <div className="mt-4">
                <p className="text-xs text-ink/50">Trocar a região recalcula a entrega</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {ZONES.filter((zone) => servedZones.includes(zone.id)).map((zone) => (
                    <button
                      key={zone.id}
                      type="button"
                      disabled={loading || zone.id === order.zone}
                      onClick={() => void send(orderPhrase(order.items[0].name, order.items[0].qty, zone.id))}
                      className={`rounded-full border px-2.5 py-1 text-xs ${
                        zone.id === order.zone ? "border-moss bg-moss/10 text-moss" : "border-line hover:border-clay/40"
                      } disabled:opacity-70`}
                    >
                      {zone.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <dl className="mt-4 space-y-1 border-t border-dashed border-line pt-4 text-sm">
              <div className="flex justify-between">
                <dt>Subtotal</dt>
                <dd>{brl(order.subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Entrega</dt>
                <dd>{brl(order.delivery_fee)}</dd>
              </div>
              <div className="flex justify-between text-base font-semibold">
                <dt>Total</dt>
                <dd>{brl(order.total)}</dd>
              </div>
            </dl>
            {order.dietary_notes.length > 0 && (
              <p className="mt-3 text-xs text-moss">Notas: {order.dietary_notes.join(", ")}</p>
            )}
            {order.status === "draft" ? (
              <button
                type="button"
                onClick={() => void confirmOrder()}
                disabled={confirming}
                className="mt-4 w-full rounded-full bg-clay px-4 py-3 text-sm text-white disabled:opacity-50"
              >
                {confirming ? "Registrando…" : "Confirmar pedido"}
              </button>
            ) : (
              <p className="mt-4 rounded-2xl bg-moss/10 px-3 py-2 text-sm text-moss">Registrado como {order.id}</p>
            )}
            <details className="mt-4">
              <summary className="cursor-pointer text-xs text-ink/50">JSON pronto para a API</summary>
              <pre className="mt-2 overflow-x-auto rounded-2xl bg-ink px-3 py-3 text-[11px] leading-relaxed text-paper">
                {JSON.stringify(order, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </aside>
    </main>
  );
}

function addedHints(visible: string, sent: string) {
  if (sent.startsWith(visible)) return sent.slice(visible.length).replace(/^\.\s*/, "");
  return sent;
}

function Quick({
  children,
  onClick,
  disabled,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-full border border-line bg-card px-3 py-1.5 text-xs text-ink/80 transition hover:border-clay/40 disabled:opacity-40"
    >
      {children}
    </button>
  );
}
