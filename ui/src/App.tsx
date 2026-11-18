import { useCallback, useEffect, useRef, useState } from "react";
import { chat, chatStream, getHealth, search } from "./api";
import type { ChatResponse, Citation, Health } from "./types";

type Mode = "chat" | "search";

interface Message {
  id: number;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[]; // sources shown under the answer
  candidates?: boolean; // true while citations are only "retrieved so far" (streaming)
  meta?: ChatResponse;
  searchMs?: number;
  error?: string;
  pending?: boolean;
}

const EXAMPLES = [
  "Mức lương tối thiểu vùng I là bao nhiêu?",
  "Thời hiệu xử phạt vi phạm hành chính là bao lâu?",
  "Giảm 30% thuế thu nhập doanh nghiệp áp dụng cho ai?",
];

let nextId = 1;

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("chat");
  const [stream, setStream] = useState(true);
  const [topK, setTopK] = useState(5);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<(Health & { points?: number }) | null>(null);
  const [offline, setOffline] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshHealth = useCallback(() => {
    getHealth()
      .then((h) => {
        setHealth(h);
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, []);

  useEffect(refreshHealth, [refreshHealth]);
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const patch = (id: number, changes: Partial<Message>) =>
    setMessages((all) => all.map((m) => (m.id === id ? { ...m, ...changes } : m)));

  async function send(question: string) {
    const q = question.trim();
    if (q.length < 3 || busy) return;
    setInput("");
    setBusy(true);
    // Ids must be created OUTSIDE the state updater: React StrictMode runs updaters twice in dev.
    const userId = nextId++;
    const answerId = nextId++;
    setMessages((all) => [
      ...all,
      { id: userId, role: "user", text: q },
      { id: answerId, role: "assistant", text: "", pending: true },
    ]);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      if (mode === "search") {
        const res = await search(q, topK, controller.signal);
        patch(answerId, { text: `${res.results.length} đoạn liên quan nhất`, citations: res.results, searchMs: res.latency_ms, pending: false });
      } else if (stream) {
        let text = "";
        await chatStream(
          q,
          topK,
          {
            onSources: (sources) => patch(answerId, { citations: sources, candidates: true }),
            onToken: (t) => {
              text += t;
              patch(answerId, { text });
            },
            onDone: (final) => patch(answerId, { text: final.answer, citations: final.citations, candidates: false, meta: final, pending: false }),
          },
          controller.signal
        );
      } else {
        const res = await chat(q, topK, controller.signal);
        patch(answerId, { text: res.answer, citations: res.citations, meta: res, pending: false });
      }
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === "AbortError";
      patch(answerId, { error: aborted ? "Đã dừng." : (err as Error).message, pending: false });
      if (!aborted) refreshHealth();
    } finally {
      patch(answerId, { pending: false });
      setBusy(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="app">
      <header>
        <div>
          <h1>TrustRAG</h1>
          <p className="subtitle">Tra cứu văn bản pháp luật có trích dẫn nguồn</p>
        </div>
        <div className={`status ${offline ? "bad" : "ok"}`} title="Bấm để kiểm tra lại" onClick={refreshHealth}>
          <span className="dot" />
          {offline
            ? "API offline"
            : health
              ? `${health.llm_provider} · ${health.model}${health.points != null ? ` · ${health.points} chunks` : ""}`
              : "Đang kết nối…"}
        </div>
      </header>

      <main>
        {messages.length === 0 && (
          <div className="empty">
            <p>Hãy đặt một câu hỏi về các văn bản đã nạp. Ví dụ:</p>
            {EXAMPLES.map((ex) => (
              <button key={ex} className="example" onClick={() => send(ex)} disabled={busy}>
                {ex}
              </button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <MessageView key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </main>

      <footer>
        <div className="options">
          <div className="seg">
            <button className={mode === "chat" ? "on" : ""} onClick={() => setMode("chat")}>Hỏi đáp</button>
            <button className={mode === "search" ? "on" : ""} onClick={() => setMode("search")}>Chỉ tìm kiếm</button>
          </div>
          <label className={mode === "search" ? "disabled" : ""}>
            <input type="checkbox" checked={stream} disabled={mode === "search"} onChange={(e) => setStream(e.target.checked)} /> Streaming
          </label>
          <label>
            Top-k
            <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
              {[3, 5, 8, 10].map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          {messages.length > 0 && (
            <button className="link" onClick={() => setMessages([])} disabled={busy}>Xóa hội thoại</button>
          )}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <textarea
            value={input}
            rows={2}
            placeholder="Nhập câu hỏi… (Enter để gửi, Shift+Enter xuống dòng)"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
          />
          {busy ? (
            <button type="button" className="stop" onClick={() => abortRef.current?.abort()}>Dừng</button>
          ) : (
            <button type="submit" disabled={input.trim().length < 3}>Gửi</button>
          )}
        </form>
      </footer>
    </div>
  );
}

function MessageView({ message: m }: { message: Message }) {
  const [active, setActive] = useState<number | null>(null);

  if (m.role === "user") {
    return <div className="msg user">{m.text}</div>;
  }

  const cited = new Set((m.citations ?? []).map((c) => c.id));
  const parts = m.text.split(/(\[\d+\])/g);

  return (
    <div className="msg assistant">
      {m.error ? (
        <div className="error">⚠ {m.error}</div>
      ) : (
        <p className="answer">
          {parts.map((part, i) => {
            const match = part.match(/^\[(\d+)\]$/);
            const id = match ? Number(match[1]) : null;
            if (id != null && cited.has(id)) {
              return (
                <button key={i} className={`cite ${active === id ? "on" : ""}`} onClick={() => setActive(active === id ? null : id)}>
                  {id}
                </button>
              );
            }
            return <span key={i}>{part}</span>;
          })}
          {m.pending && <span className="caret" />}
        </p>
      )}

      {m.meta && (
        <div className="meta">
          <span className={`badge ${m.meta.grounded ? "good" : "warn"}`}>
            {m.meta.grounded ? "Có trích dẫn" : refusalText(m.meta.refusal_reason)}
          </span>
          <span title="Điểm truy xuất top-1, chỉ là heuristic">độ liên quan {m.meta.confidence.toFixed(2)}</span>
          <span>
            {Math.round(m.meta.latency_ms.total_ms)} ms (tìm {Math.round(m.meta.latency_ms.retrieval_ms)} · sinh {Math.round(m.meta.latency_ms.generation_ms)})
          </span>
          <span>{m.meta.model}</span>
        </div>
      )}
      {m.searchMs != null && <div className="meta"><span>{Math.round(m.searchMs)} ms</span></div>}

      {!!m.citations?.length && (
        <div className="sources">
          <h4>{m.candidates ? "Nguồn đã truy xuất (đang tạo câu trả lời…)" : m.meta ? "Nguồn được trích dẫn" : "Kết quả"}</h4>
          {m.citations.map((c) => (
            <SourceCard key={c.id} c={c} active={active === c.id} onClick={() => setActive(active === c.id ? null : c.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceCard({ c, active, onClick }: { c: Citation; active: boolean; onClick: () => void }) {
  return (
    <div className={`source ${active ? "active" : ""}`} onClick={onClick}>
      <div className="source-head">
        <span className="cite static">{c.id}</span>
        <strong>{c.doc_label}</strong> · Điều {c.article}
        {c.article_title ? `. ${c.article_title}` : ""}
        <span className="score">{c.score.toFixed(3)}</span>
      </div>
      {c.chapter && <div className="chapter">{c.chapter}</div>}
      {active && <pre className="snippet">{c.snippet}</pre>}
    </div>
  );
}

function refusalText(reason: string | null): string {
  switch (reason) {
    case "low_retrieval_score":
      return "Ngoài phạm vi tài liệu";
    case "model_declined":
      return "Không tìm thấy thông tin";
    case "no_citation":
      return "Chưa có trích dẫn, cần kiểm chứng";
    default:
      return "Không có trích dẫn";
  }
}
