import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Зарплатный AI — банковская аналитика",
  description:
    "Desktop-чат для сравнения условий зарплатных проектов. Демонстрационный режим с синтетическими данными.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
