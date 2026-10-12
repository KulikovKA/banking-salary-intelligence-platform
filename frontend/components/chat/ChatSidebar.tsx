import type { Conversation } from "@/lib/chat/models";
import { Icon } from "./Icon";
export function ChatSidebar({
  conversations,
  activeId,
  collapsed,
  onToggle,
  onNew,
  onSelect,
  onDelete,
}: {
  conversations: Conversation[];
  activeId: string;
  collapsed: boolean;
  onToggle: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const saved = conversations.filter(
    (c) => c.messages.length > 0 || c.draft.trim().length > 0,
  );
  return (
    <aside
      className={`sidebar ${collapsed ? "sidebar-collapsed" : ""}`}
      aria-label="Диалоги"
    >
      <div className="sidebar-brand">
        <span className="brand-mark">
          <Icon name="spark" size={21} />
        </span>
        {!collapsed && (
          <div>
            <strong>Зарплатный AI</strong>
            <span>Банковская аналитика</span>
          </div>
        )}
        <button
          className="icon-button panel-toggle"
          onClick={onToggle}
          aria-label={collapsed ? "Развернуть панель" : "Свернуть панель"}
          title={collapsed ? "Развернуть панель" : "Свернуть панель"}
        >
          <Icon name="panel" size={18} />
        </button>
      </div>
      <button
        className="new-chat"
        onClick={onNew}
        title="Новый чат"
        aria-label="Новый чат"
      >
        <Icon name="plus" size={19} />
        {!collapsed && "Новый чат"}
      </button>
      {!collapsed && (
        <>
          <div className="history-label">
            Диалоги
            <span>
              {saved.length ? String(saved.length).padStart(2, "0") : ""}
            </span>
          </div>
          <nav className="conversation-list" aria-label="История диалогов">
            {!saved.length && (
              <div className="empty-history">
                <Icon name="chat" size={22} />
                <p>
                  Здесь появятся
                  <br />
                  ваши диалоги
                </p>
              </div>
            )}
            {saved.map((conversation) => (
              <div
                key={conversation.id}
                className={`conversation-item ${activeId === conversation.id ? "active" : ""}`}
              >
                <button
                  className="conversation-select"
                  onClick={() => onSelect(conversation.id)}
                  aria-current={
                    activeId === conversation.id ? "page" : undefined
                  }
                  title={conversation.title}
                >
                  <Icon name="chat" size={16} />
                  <span>{conversation.title}</span>
                  {conversation.messages.some(
                    (m) => m.status === "streaming",
                  ) && (
                    <span
                      className="conversation-generating"
                      aria-label="Генерация продолжается"
                    />
                  )}
                </button>
                <button
                  className="conversation-delete icon-button"
                  onClick={() => onDelete(conversation.id)}
                  aria-label={`Удалить диалог: ${conversation.title}`}
                  title="Удалить диалог"
                >
                  <Icon name="trash" size={15} />
                </button>
              </div>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="session-note">
              <span className="session-dot" />
              <span>История в этой вкладке</span>
            </div>
            <p>Диалоги сохраняются до перезагрузки страницы.</p>
            <div className="workspace-label">
              <span className="workspace-avatar">AI</span>
              <div>
                <strong>Рабочее пространство</strong>
                <span>Зарплатные проекты</span>
              </div>
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
