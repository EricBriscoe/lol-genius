import { useState, useEffect, useCallback, useRef } from "react";
import type { LiveGameUpdate, ModelInfo, DevLogEntry, AppUpdateEvent, GamePhaseChange } from "../types";

const MAX_LOGS = 200;

export function useLiveGame() {
  const [connectionStatus, setConnectionStatus] = useState<string>("connecting");
  const [current, setCurrent] = useState<LiveGameUpdate | null>(null);
  const [history, setHistory] = useState<{ game_time: number; probability: number }[]>([]);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [devMode, setDevModeState] = useState(false);
  const [devLogs, setDevLogs] = useState<DevLogEntry[]>([]);
  const [appUpdateStatus, setAppUpdateStatus] = useState<AppUpdateEvent | null>(null);
  const devLogUnsub = useRef<(() => void) | null>(null);

  const toggleDevMode = useCallback(async () => {
    const next = !devMode;
    await window.lolGenius.setDevMode(next);
    setDevModeState(next);
  }, [devMode]);

  const clearDevLogs = useCallback(() => setDevLogs([]), []);

  useEffect(() => {
    window.lolGenius.getModelInfo().then(setModelInfo);
    window.lolGenius.getDevMode().then(setDevModeState);

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

    const unsub3 = window.lolGenius.onAppUpdateStatus((data) => {
      setAppUpdateStatus(data);
    });

    const unsub4 = window.lolGenius.onGamePhaseChange((data: GamePhaseChange) => {
      if (data.phase === "in_game" && data.pregameProb != null) {
        setCurrent({
          game_time: 0, blue_win_probability: data.pregameProb,
          kill_diff: 0, dragon_diff: 0, tower_diff: 0, baron_diff: 0,
          cs_diff: 0, inhibitor_diff: 0, elder_diff: 0,
        });
        setHistory([{ game_time: 0, probability: Math.round(data.pregameProb * 1000) / 10 }]);
      } else if (data.phase === "none") {
        setCurrent(null);
        setHistory([]);
      }
    });

    return () => { unsub1(); unsub2(); unsub3(); unsub4(); };
  }, []);

  useEffect(() => {
    if (devMode) {
      devLogUnsub.current = window.lolGenius.onDevLog((entry) => {
        setDevLogs((prev) => {
          const next = [...prev, entry];
          return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
        });
      });
    } else {
      devLogUnsub.current?.();
      devLogUnsub.current = null;
    }
    return () => { devLogUnsub.current?.(); };
  }, [devMode]);

  return { connectionStatus, current, history, modelInfo, devMode, toggleDevMode, devLogs, clearDevLogs, appUpdateStatus };
}
