import { useState, useEffect, useCallback, useRef } from "react";
import type { PlayerIdentity, MatchRow, RankedStatsRow, ChampionStatsAgg } from "../types";

const PAGE_SIZE = 20;

export function usePlayerInfo() {
  const [identity, setIdentity] = useState<PlayerIdentity | null>(null);
  const [matches, setMatches] = useState<MatchRow[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [championStats, setChampionStats] = useState<ChampionStatsAgg[]>([]);
  const [rankedStats, setRankedStats] = useState<RankedStatsRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [lcuConnected, setLcuConnected] = useState(false);
  const [championFilter, setChampionFilter] = useState<number | undefined>();
  const offsetRef = useRef(0);

  const fetchData = useCallback(async (reset = false) => {
    try {
      const id = await window.lolGenius.getPlayerIdentity();
      if (id) {
        setIdentity(id);
        setLcuConnected(true);
      }
    } catch { /* */ }

    setLoading(true);
    try {
      const offset = reset ? 0 : offsetRef.current;
      const result = await window.lolGenius.getMatchHistory({
        offset,
        limit: PAGE_SIZE,
        championId: championFilter,
      });

      if (reset) {
        setMatches(result.matches);
        offsetRef.current = result.matches.length;
      } else {
        setMatches((prev) => [...prev, ...result.matches]);
        offsetRef.current = offset + result.matches.length;
      }
      setTotalMatches(result.total);
      setLcuConnected(!result.lcuOffline);

      const [champs, ranked] = await Promise.all([
        window.lolGenius.getChampionStats(),
        window.lolGenius.getRankedStats(),
      ]);
      setChampionStats(champs);
      setRankedStats(ranked);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, [championFilter]);

  useEffect(() => {
    fetchData(true);

    const unsub1 = window.lolGenius.onPlayerIdentity((data: PlayerIdentity) => {
      setIdentity(data);
      setLcuConnected(true);
      fetchData(true);
    });

    const unsub2 = window.lolGenius.onPlayerDataUpdate(() => {
      fetchData(true);
    });

    return () => { unsub1(); unsub2(); };
  }, [fetchData]);

  const loadMore = useCallback(() => {
    if (loading || offsetRef.current >= totalMatches) return;
    fetchData(false);
  }, [loading, totalMatches, fetchData]);

  const filterByChampion = useCallback((id: number | undefined) => {
    setChampionFilter(id);
    offsetRef.current = 0;
    setMatches([]);
  }, []);

  const refresh = useCallback(async () => {
    try {
      await window.lolGenius.refreshPlayerData();
    } catch { /* */ }
  }, []);

  return {
    identity,
    matches,
    totalMatches,
    championStats,
    rankedStats,
    loading,
    lcuConnected,
    loadMore,
    filterByChampion,
    championFilter,
    refresh,
  };
}
