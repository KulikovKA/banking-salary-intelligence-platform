import { ChatShell } from "@/components/chat/ChatShell";
import { BackendChat } from "@/components/chat/BackendChat";
export default async function Home({ searchParams }: { searchParams: Promise<{ demo?: string }> }) {
  const query = await searchParams;
  return process.env.CHAT_DEMO_MODE === "true" && ["test", "local", "development"].includes(process.env.APP_ENV ?? "") && query.demo === "1"
    ? <ChatShell /> : <BackendChat />;
}
