export default function Home() {
  return (
    <main className="page-shell">
      <section className="welcome-card" aria-labelledby="page-title">
        <p className="eyebrow">Banking Salary Intelligence Platform</p>
        <h1 id="page-title">Аналитика зарплатных проектов</h1>
        <p className="description">
          Стартовый экран платформы. Сравнение станет доступно после подключения и проверки
          официальных источников банков.
        </p>
        <p className="status" role="status">
          Каркас приложения готовится
        </p>
      </section>
    </main>
  );
}
