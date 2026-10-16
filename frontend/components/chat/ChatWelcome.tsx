import { Icon } from "./Icon";
import type { ReactNode } from "react";
const suggestions = [
  {
    icon: "table" as const,
    title: "Сравнить условия",
    description: "Комиссии, обслуживание и ограничения",
    question: "Покажи пример сравнения зарплатных проектов",
  },
  {
    icon: "file" as const,
    title: "Разобраться в тарифах",
    description: "Что проверить в документах банка",
    question: "Какие условия важны при выборе зарплатного проекта?",
  },
  {
    icon: "chat" as const,
    title: "Уточнить детали",
    description: "Неизвестные ставки и особые условия",
    question: "Как учитывать индивидуальные условия и пробелы в данных?",
  },
];
export function ChatWelcome({
  onSuggest,
  modern = false,
  composer,
}: {
  onSuggest: (question: string) => void;
  modern?: boolean;
  composer?: ReactNode;
}) {
  if (modern) return <section className="welcome live-welcome" aria-labelledby="welcome-title">
    <div className="welcome-kicker"><span />Ваш помощник в банковских вопросах</div>
    <h1 id="welcome-title">Чем могу помочь?</h1>
    {composer}
    <div className="live-suggestions">
      {["Сравнить зарплатные проекты банков", "Какие комиссии у ВТБ?", "Условия зарплатного проекта", "Какой банк выгоднее?"].map((question) =>
        <button key={question} onClick={() => onSuggest(question)}>{question}</button>)}
    </div>
  </section>;
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div className="welcome-symbol">
        <Icon name="spark" size={34} />
      </div>
      <p className="welcome-eyebrow">ВАШ ПОМОЩНИК В БАНКОВСКИХ УСЛОВИЯХ</p>
      <h1 id="welcome-title">
        Сложные условия.
        <br />
        <span>Понятный разговор.</span>
      </h1>
      <p className="welcome-description">
        Сравнивайте зарплатные проекты, задавайте вопросы
        <br />и находите важное в условиях банков.
      </p>
      <div className="suggestions">
        {suggestions.map((item) => (
          <button
            key={item.title}
            onClick={() => onSuggest(item.question)}
            className="suggestion"
          >
            <span className="suggestion-icon">
              <Icon name={item.icon} size={22} />
            </span>
            <strong>{item.title}</strong>
            <span>{item.description}</span>
            <Icon
              name="chevron"
              size={15}
              style={{ position: "absolute", right: 17, top: 22 }}
            />
          </button>
        ))}
      </div>
      <p className="welcome-demo">
        <span className="demo-tag">DEMO</span>Сейчас доступен учебный пример с
        вымышленными банками.
      </p>
    </section>
  );
}
