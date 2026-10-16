import { ChatShell } from "@/components/chat/ChatShell";
import { BackendChat } from "@/components/chat/BackendChat";
import { LiveChat } from "@/components/chat/LiveChat";
export default async function Home({ searchParams }: { searchParams: Promise<{ demo?: string }> }) {
  const query = await searchParams;
  if (process.env.NODE_ENV === "development" && process.env.LIVE_DEMO_ENABLED === "true" && process.env.APP_ENV === "poc")
    return <LiveChat />;
  return process.env.CHAT_DEMO_MODE === "true" && ["test", "local", "development"].includes(process.env.APP_ENV ?? "") && query.demo === "1"
    ? <ChatShell /> : <BackendChat />;
}
