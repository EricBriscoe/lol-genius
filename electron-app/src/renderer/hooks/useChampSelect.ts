import { useState, useEffect } from "react";
import type { ChampSelectUpdate, GamePhaseChange } from "../types";

export function useChampSelect() {
  const [champSelectData, setChampSelectData] = useState<ChampSelectUpdate | null>(null);
  const [gamePhase, setGamePhase] = useState<string>("none");

  useEffect(() => {
    const unsub1 = window.lolGenius.onChampSelectUpdate((data) => {
      setChampSelectData(data);
    });

    const unsub2 = window.lolGenius.onGamePhaseChange((data: GamePhaseChange) => {
      setGamePhase(data.phase);
      if (data.phase !== "champ_select") {
        setChampSelectData(null);
      }
    });

    return () => { unsub1(); unsub2(); };
  }, []);

  return {
    champSelectData,
    gamePhase,
    isInChampSelect: gamePhase === "champ_select" && champSelectData !== null,
  };
}
