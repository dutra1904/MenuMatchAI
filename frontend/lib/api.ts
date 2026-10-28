export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Dish = {
  id: string;
  restaurant_id: string;
  restaurant_name: string;
  cuisine: string;
  name: string;
  description: string;
  price: number;
  prep_minutes: number;
  kind: string;
  category: string;
  badges: string[];
};

export type Restaurant = {
  id: string;
  name: string;
  cuisine: string;
  rating: number;
  zones: string[];
};

export type OrderItem = {
  dish_id: string;
  name: string;
  qty: number;
  unit_price: number;
};

export type Order = {
  id: string | null;
  schema_version: string;
  status: "draft" | "confirmed";
  restaurant_id: string;
  restaurant_name: string;
  zone: string;
  zone_label: string;
  items: OrderItem[];
  subtotal: number;
  delivery_fee: number;
  total: number;
  prep_minutes: number;
  dietary_notes: string[];
  customer_query: string;
};

export type ChatResponse = {
  session_id: string;
  reply: string;
  recommendations: Dish[];
  order: Order | null;
  tools_used: string[];
  latency_ms: number;
  provider: string;
};

export type Health = {
  status: string;
  dishes: number;
  restaurants: number;
  embedder: string;
  dimensions: number;
  llm: string;
};

export type Analytics = {
  orders_today: number;
  revenue_today: number;
  avg_ticket: number;
  minutes_saved: number;
  restriction_rate: number;
  browse_minutes: number;
  agent_minutes: number;
  avg_latency_ms: number | null;
  top_dishes: { name: string; restaurant_name: string; qty: number }[];
  recent_orders: {
    id: string;
    restaurant_name: string;
    total: number;
    item_summary: string;
    dietary_notes: string[];
    created_at: string;
    status: string;
  }[];
  dishes_indexed: number;
  restaurants_indexed: number;
  embedder: string;
  dimensions: number;
};

export function brl(value: number) {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = "A API recusou o pedido.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      detail = "Não consegui falar com a API na porta 8000.";
    }
    throw new Error(detail);
  }
  return response.json();
}

export function getHealth() {
  return request<Health>("/api/health");
}

export function getRestaurants() {
  return request<Restaurant[]>("/api/restaurants");
}

export function sendChat(payload: {
  message: string;
  session_id: string | null;
  history: { role: "user" | "assistant"; content: string }[];
}) {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createOrder(payload: {
  restaurant_id: string;
  zone: string;
  items: { dish_id: string; qty: number }[];
  dietary_notes: string[];
  customer_query: string;
}) {
  return request<Order>("/api/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAnalytics() {
  return request<Analytics>("/api/analytics");
}
