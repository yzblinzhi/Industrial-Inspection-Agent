import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useAuthStore } from "../stores/auth";

export interface SseHandlers {
  onEvent: (event: string, data: any) => void;
  onError?: (msg: string) => void;
  onClose?: () => void;
}

/** POST 方式的 SSE 消费（原生 EventSource 不支持 POST/自定义头）。 */
export async function consumeSse(
  url: string,
  body: Record<string, unknown>,
  handlers: SseHandlers
): Promise<void> {
  const auth = useAuthStore();
  const ctrl = new AbortController();
  try {
    await fetchEventSource(url, {
      method: "POST",
      signal: ctrl.signal,
      openWhenHidden: true,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify(body),
      async onopen(resp) {
        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(text || `HTTP ${resp.status}`);
        }
      },
      onmessage(msg) {
        let data: any = msg.data;
        try {
          data = JSON.parse(msg.data);
        } catch {
          /* keep raw */
        }
        handlers.onEvent(msg.event || "message", data);
        if (msg.event === "done") ctrl.abort();
      },
      onerror(err) {
        handlers.onError?.(String(err?.message || err));
        throw err; // 停止重试
      },
    });
  } catch (e: any) {
    // ctrl.abort() 正常结束也会抛 AbortError，忽略之
    if (e?.name !== "AbortError") handlers.onError?.(String(e?.message || e));
  } finally {
    handlers.onClose?.();
  }
}
