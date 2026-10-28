"use client";

import { useEffect, useState } from "react";
import { brl, getAnalytics, type Analytics } from "@/lib/api";

export function DashboardPanel() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await getAnalytics());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não consegui carregar o painel.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const maxQty = data?.top_dishes[0]?.qty || 1;

  return (
    <main className="mx-auto max-w-6xl px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-moss">Restaurante</p>
          <h1 className="mt-2 font-display text-4xl">O que o agente está resolvendo</h1>
          <p className="mt-2 max-w-2xl text-ink/70">
            Pedidos confirmados, itens que mais saem e uma estimativa de tempo de atendimento.
          </p>
        </div>
        <button type="button" onClick={() => void load()} className="rounded-full border border-line bg-card px-4 py-2 text-sm">
          Atualizar
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-clay">{error}</p>}
      {loading && !data && <p className="mt-6 text-sm text-ink/60">Carregando o painel…</p>}

      {data && (
        <>
          <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Pedidos hoje" value={String(data.orders_today)} />
            <Kpi label="Receita hoje" value={brl(data.revenue_today)} />
            <Kpi label="Ticket médio" value={brl(data.avg_ticket)} />
            <Kpi label="Minutos economizados" value={data.minutes_saved.toLocaleString("pt-BR")} />
          </section>

          <section className="mt-4 rounded-[28px] border border-line bg-card p-5">
            <p className="text-sm leading-relaxed">
              Estimativa de eficiência: navegar o cardápio leva cerca de {data.browse_minutes.toLocaleString("pt-BR")} min.
              Com o agente, a decisão fica em {data.agent_minutes.toLocaleString("pt-BR")} min. Em{" "}
              {data.orders_today} pedidos de hoje, isso soma {data.minutes_saved.toLocaleString("pt-BR")} min.
            </p>
            <p className="mt-2 text-sm text-ink/60">
              {Math.round(data.restriction_rate * 100)}% dos pedidos de hoje citaram alguma restrição alimentar.
              {data.avg_latency_ms != null
                ? ` Latência média recente do agente: ${data.avg_latency_ms} ms.`
                : " A latência média aparece depois da primeira conversa desta sessão da API."}
            </p>
          </section>

          <section className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <div className="rounded-[28px] border border-line bg-card p-5">
              <h2 className="font-display text-2xl">Itens mais pedidos</h2>
              <p className="text-sm text-ink/50">Últimos 7 dias</p>
              <ul className="mt-4 space-y-3">
                {data.top_dishes.map((dish) => (
                  <li key={`${dish.restaurant_name}-${dish.name}`}>
                    <div className="flex justify-between text-sm">
                      <span>
                        {dish.name}
                        <span className="text-ink/50"> · {dish.restaurant_name}</span>
                      </span>
                      <span>{dish.qty}</span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-paper">
                      <div
                        className="h-2 rounded-full bg-clay"
                        style={{ width: `${Math.max(8, (dish.qty / maxQty) * 100)}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-[28px] border border-line bg-card p-5">
              <h2 className="font-display text-2xl">Pedidos recentes</h2>
              <ul className="mt-4 divide-y divide-line">
                {data.recent_orders.map((order) => (
                  <li key={order.id} className="flex items-start justify-between gap-3 py-3 text-sm">
                    <div>
                      <p className="font-medium">{order.item_summary}</p>
                      <p className="text-ink/55">
                        {order.restaurant_name} · {order.id}
                        {order.dietary_notes.length ? ` · ${order.dietary_notes.join(", ")}` : ""}
                      </p>
                    </div>
                    <div className="text-right">
                      <p>{brl(order.total)}</p>
                      <p className="text-xs text-ink/45">
                        {new Date(order.created_at).toLocaleString("pt-BR", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <p className="mt-4 text-sm text-ink/50">
            Índice semântico: {data.dishes_indexed} documentos · {data.dimensions} dimensões · {data.embedder.toUpperCase()} ·{" "}
            {data.restaurants_indexed} restaurantes
          </p>
        </>
      )}
    </main>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-[24px] border border-line bg-card p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-ink/45">{label}</p>
      <p className="mt-2 font-display text-3xl">{value}</p>
    </article>
  );
}
