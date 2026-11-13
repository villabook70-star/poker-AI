import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "PokerMind AI · Entrenador Twister 3-max",
  description: "Análisis matemático determinista y entrenamiento para Twister Poker (3-max Spin & Go).",
};
export const viewport: Viewport = { themeColor: "#07090d", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <Nav />
        <main className="mx-auto max-w-7xl px-4 py-5">{children}</main>
      </body>
    </html>
  );
}
