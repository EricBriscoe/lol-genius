import { useState, useEffect } from "react";
import type { LiveGameUpdate, ModelInfo } from "../types";

export function useLiveGame() {
  const [connectionStatus, setConnectionStatus] = useState<string>("connecting");
  const [current, setCurrent] = useState<LiveGameUpdate | null>(null);
  const [history, setHistory] = useState<{ game_time: number; probability: number }[]>([]);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);

  useEffect(() => {
    window.lolGenius.getModelInfo().then(setModelInfo);

    const unsub1 = window.lolGenius.onPredictionUpdate((data) => {
      if (data.status === "model_missing" || data.status === "poll_error") {
        setConnectionStatus(data.status);
        return;
      }
      if (data.blue_win_probability == null) return;

      setConnectionStatus("ok");
      setCurrent(data);
      setHistory((prev) => {
        const base = data.game_reset ? [] : prev;
        const entry = {
          game_time: data.game_time,
          probability: Math.round((data.blue_win_probability ?? 0.5) * 1000) / 10,
        };
        if (base.length > 0 && base[base.length - 1].game_time === entry.game_time) return base;
        const next = [...base, entry];
        return next.length > 100 ? next.slice(-100) : next;
      });
    });

    const unsub2 = window.lolGenius.onConnectionStatus((status) => {
      setConnectionStatus(status);
    });

    return () => { unsub1(); unsub2(); };
  }, []);

  return { connectionStatus, current, history, modelInfo };
}
