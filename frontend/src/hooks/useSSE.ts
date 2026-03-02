import { useEffect, useRef, useState } from "react";

type SSEHandler = (data: unknown) => void;

const MAX_RETRIES = 15;

export function useSSE(handlers: Record<string, SSEHandler>) {
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout>;
    let retryCount = 0;

    function connect() {
      if (retryCount >= MAX_RETRIES) return;

      es = new EventSource("/api/v1/events");

      es.onopen = () => {
        setConnected(true);
        retryCount = 0;
      };

      es.onerror = () => {
        setConnected(false);
        es?.close();
        const delay = Math.min(1000 * 2 ** retryCount, 30_000);
        retryCount++;
        retryTimer = setTimeout(connect, delay);
      };

      for (const eventType of Object.keys(handlersRef.current)) {
        es.addEventListener(eventType, (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data);
            handlersRef.current[eventType]?.(data);
          } catch (err) {
            console.warn("SSE parse error:", err);
          }
        });
      }
    }

    connect();

    return () => {
      clearTimeout(retryTimer);
      es?.close();
    };
  }, []);

  return connected;
}
