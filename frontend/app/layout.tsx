import type { Metadata } from "next";
import "./globals.css";
import "../styles/live-chat.css";

export const metadata: Metadata = {
  title: "Зарплатный AI — банковская аналитика",
  description:
    "Desktop-чат для доказательного сравнения условий зарплатных проектов по выбранному набору документов.",
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
