"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
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

type UiMessage = {
  role: "user" | "assistant";
  content: string;
  recommendations?: Dish[];
  meta?: { latency_ms: number; provider: string; tools_used: string[] };
};

const SUGGESTIONS = [
  "Quero algo sem lactose, rápido e por menos de R$ 40",
  "Um poke ou sushi sem glúten na zona sul",
  "Opção vegana e leve para o almoço",
];

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
    const content = text.trim();
    if (!content || loading) return;
    const history = messages.map((item) => ({ role: item.role, content: item.content }));
    setMessages((current) => [...current, { role: "user", content }]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const data = await sendChat({ message: content, session_id: sessionId, history });
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

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="min-w-0">
        <p className="text-xs uppercase tracking-[0.18em] text-clay">Atendimento</p>
        <h1 className="mt-2 font-display text-4xl leading-tight sm:text-5xl">Diga o que você quer comer.</h1>
        <p className="mt-3 max-w-xl text-ink/70">
          O agente entende restrição, pressa e orçamento, busca no cardápio e devolve o pedido em JSON.
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

        {restaurants.length > 0 && messages.length === 0 && (
          <ul className="mt-5 flex gap-2 overflow-x-auto pb-1">
            {restaurants.map((restaurant) => (
              <li key={restaurant.id} className="shrink-0 rounded-full border border-line bg-card px-3 py-1.5 text-sm">
                <span className="font-medium">{restaurant.name}</span>
                <span className="text-ink/50"> · {restaurant.cuisine}</span>
              </li>
            ))}
          </ul>
        )}

        {messages.length === 0 && (
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => void send(suggestion)}
                className="rounded-2xl border border-line bg-card p-4 text-left text-sm leading-relaxed shadow-ticket hover:border-clay/40"
              >
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
                {message.recommendations && message.recommendations.length > 0 && (
                  <div className="mt-3 grid gap-2">
                    {message.recommendations.map((dish) => (
                      <button
                        key={dish.id}
                        type="button"
                        onClick={() => void send(`Monta o pedido com ${dish.name}`)}
                        className="rounded-2xl border border-line bg-paper px-3 py-2 text-left text-ink hover:border-clay/40"
                      >
                        <span className="flex items-baseline justify-between gap-3">
                          <span className="font-medium">{dish.name}</span>
                          <span className="shrink-0 text-sm">{brl(dish.price)}</span>
                        </span>
                        <span className="mt-1 block text-xs text-ink/60">
                          {dish.restaurant_name} · {dish.prep_minutes} min
                          {dish.badges.length ? ` · ${dish.badges.join(" · ")}` : ""}
                        </span>
                      </button>
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
          {loading && <p className="text-sm text-ink/50">Consultando o cardápio…</p>}
          <div ref={endRef} />
        </div>

        {error && <p className="mt-4 text-sm text-clay">{error}</p>}

        <form onSubmit={onSubmit} className="mt-4 flex gap-2">
          <label className="sr-only" htmlFor="pedido">
            Mensagem para o agente
          </label>
          <input
            id="pedido"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ex.: sem lactose, rápido, até R$ 40"
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
      </section>

      <aside className="h-fit rounded-[28px] border border-line bg-card p-5 shadow-ticket lg:sticky lg:top-24">
        <p className="text-xs uppercase tracking-[0.16em] text-ink/50">Pedido</p>
        {!order && (
          <p className="mt-3 text-sm leading-relaxed text-ink/70">
            O JSON estruturado aparece aqui quando o agente fechar uma sugestão.
          </p>
        )}
        {order && (
          <div className="mt-3">
            <h2 className="font-display text-2xl leading-tight">{order.restaurant_name}</h2>
            <p className="text-sm text-ink/60">
              {order.zone_label} · {order.prep_minutes} min · {order.status === "confirmed" ? "confirmado" : "rascunho"}
            </p>
            <ul className="mt-4 space-y-2 border-t border-dashed border-line pt-4 text-sm">
              {order.items.map((item) => (
                <li key={item.dish_id} className="flex justify-between gap-3">
                  <span>
                    {item.qty}× {item.name}
                  </span>
                  <span>{brl(item.unit_price * item.qty)}</span>
                </li>
              ))}
            </ul>
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
              <p className="mt-4 rounded-2xl bg-moss/10 px-3 py-2 text-sm text-moss">
                Registrado como {order.id}
              </p>
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
