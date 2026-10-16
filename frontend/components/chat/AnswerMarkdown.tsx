import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { answerText } from "@/lib/chat/presentation";

export function AnswerMarkdown({ text }: { text: string }) {
  return <div className="message-text markdown-answer"><Markdown
    remarkPlugins={[remarkGfm]} skipHtml unwrapDisallowed
    allowedElements={["p", "strong", "em", "del", "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "pre", "code", "hr", "br", "table", "thead", "tbody", "tr", "th", "td"]}
  >{answerText(text)}</Markdown></div>;
}
