"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { firstName } from "@/lib/profile";
import { useProfile } from "@/lib/useProfile";

const links = [
  { href: "/", label: "Conversar" },
  { href: "/dashboard", label: "Painel" },
];

export function Nav() {
  const pathname = usePathname();
  const { profile } = useProfile();
  const who = firstName(profile);
  return (
    <header className="sticky top-0 z-30 border-b border-line/80 bg-paper/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-clay text-sm font-semibold text-white">
            M
          </span>
          <span>
            <span className="block font-display text-lg leading-none">MenuMatch AI</span>
            <span className="text-xs text-ink/60">Pedido certo, em uma frase</span>
          </span>
        </Link>
        <div className="flex items-center gap-3">
          {who && <p className="hidden text-sm text-ink/70 sm:block">Olá, {who}</p>}
          <nav className="flex gap-1 rounded-full bg-white/70 p-1">
          {links.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-4 py-1.5 text-sm ${
                  active ? "bg-ink text-paper" : "text-ink/70 hover:text-ink"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
          </nav>
        </div>
      </div>
    </header>
  );
}
