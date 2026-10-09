import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Банковская аналитика зарплатных проектов",
  description: "Рабочее пространство для сопоставления подтверждённых банковских условий.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
