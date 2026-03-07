import { useState, useEffect, useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { X } from "lucide-react";
import Card from "../components/Card";
import DetailRow from "../components/DetailRow";
import StatBox from "../components/StatBox";
import { fetchChampionStats } from "../api";
import { tooltipStyle, sectionTitle, tableStyles, inputStyle, POSITION_LABELS } from "../styles";
import type { ChampionStat, ChampionStatsResponse } from "../types";

type SortKey = "champion_name" | "games" | "winrate" | "pick_rate" | "ban_rate" | "avg_kills" | "avg_deaths" | "avg_assists" | "kda";
type SortDir = "asc" | "desc";

const ALL_TAGS = ["Fighter", "Mage", "Assassin", "Tank", "Marksman", "Support"];

function kda(c: ChampionStat) {
  return c.avg_deaths === 0 ? c.avg_kills + c.avg_assists : (c.avg_kills + c.avg_assists) / c.avg_deaths;
}

function wrColor(wr: number) {
  if (wr >= 0.52) return "var(--accent)";
  if (wr <= 0.48) return "var(--red)";
  return "var(--text-primary)";
}

function pct(v: number) {
  return (v * 100).toFixed(1) + "%";
}

export default function ChampionStats() {
  const [data, setData] = useState<ChampionStatsResponse | null>(null);
  const [patch, setPatch] = useState<string | undefined>();
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<string | undefined>();
  const [sortKey, setSortKey] = useState<SortKey>("games");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selected, setSelected] = useState<ChampionStat | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchChampionStats(patch, tierFilter)
      .then((d) => {
        setData(d);
        if (!patch && d.patch) setPatch(d.patch);
        setSelected((prev) => prev ? d.champions.find((c) => c.champion_id === prev.champion_id) ?? null : null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [patch, tierFilter]);

  const filtered = useMemo(() => {
    if (!data) return [];
    let list = data.champions;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((c) => c.champion_name.toLowerCase().includes(q));
    }
    if (tagFilter) {
      list = list.filter((c) => c.tags.includes(tagFilter));
    }
    const dir = sortDir === "asc" ? 1 : -1;
    return [...list].sort((a, b) => {
      const av = sortKey === "kda" ? kda(a) : sortKey === "champion_name" ? a.champion_name.toLowerCase() : (a[sortKey] as number);
      const bv = sortKey === "kda" ? kda(b) : sortKey === "champion_name" ? b.champion_name.toLowerCase() : (b[sortKey] as number);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }, [data, search, tagFilter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "champion_name" ? "asc" : "desc");
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " \u25B2" : " \u25BC";
  }

  const positionData = useMemo(() => {
    if (!selected) return [];
    return Object.entries(selected.positions)
      .map(([pos, count]) => ({ position: POSITION_LABELS[pos] || pos, games: count }))
      .sort((a, b) => b.games - a.games);
  }, [selected]);

  if (loading && !data) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "var(--text-secondary)" }}>
        Loading champion data...
      </div>
    );
  }

  if (error) {
    return (
      <Card style={{ borderColor: "var(--red)" }}>
        <div style={{ textAlign: "center", padding: 40, color: "var(--red)" }}>
          Failed to load champion data: {error}
        </div>
      </Card>
    );
  }

  if (!data || data.champions.length === 0) {
    return (
      <Card>
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
          No champion data available. Run the crawler and enrich pipeline first.
        </div>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <select
            value={patch || ""}
            onChange={(e) => {
              setPatch(e.target.value || undefined);
              setSelected(null);
            }}
            style={styles.select}
          >
            {data.available_patches.map((p) => (
              <option key={p} value={p}>Patch {p}</option>
            ))}
          </select>
        </div>
        <div style={{ display: "flex", gap: 24 }}>
          <StatBox label="Champions" value={data.champions.length} />
          <StatBox label="Matches" value={data.total_matches} />
        </div>
      </div>

      {data.available_tiers.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 600 }}>Rank</span>
          {data.available_tiers.map((t) => (
            <button
              key={t}
              onClick={() => {
                setTierFilter(tierFilter === t ? undefined : t);
                setSelected(null);
              }}
              style={{
                ...styles.chip,
                ...(tierFilter === t ? styles.chipActive : {}),
              }}
            >
              {t.charAt(0) + t.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <input
          type="text"
          placeholder="Search champions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ ...inputStyle, width: 200 }}
        />
        <div style={{ display: "flex", gap: 4 }}>
          {ALL_TAGS.map((tag) => (
            <button
              key={tag}
              onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
              style={{
                ...styles.chip,
                ...(tagFilter === tag ? styles.chipActive : {}),
              }}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "2fr 1fr" : "1fr", gap: 20 }}>
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table style={tableStyles.table}>
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th key={col.key} onClick={() => toggleSort(col.key)} style={{ ...tableStyles.th, cursor: "pointer", whiteSpace: "nowrap" }}>
                      {col.label}{sortIndicator(col.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr
                    key={c.champion_id}
                    onClick={() => setSelected(selected?.champion_id === c.champion_id ? null : c)}
                    style={{
                      ...tableStyles.tr,
                      background: selected?.champion_id === c.champion_id ? "var(--bg-card-hover)" : undefined,
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-card-hover)"; }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.background =
                        selected?.champion_id === c.champion_id ? "var(--bg-card-hover)" : "";
                    }}
                  >
                    <td style={tableStyles.td}>{c.champion_name}</td>
                    <td style={tableStyles.tdMono}>{c.games.toLocaleString()}</td>
                    <td style={{ ...tableStyles.tdMono, color: wrColor(c.winrate) }}>{pct(c.winrate)}</td>
                    <td style={tableStyles.tdMono}>{pct(c.pick_rate)}</td>
                    <td style={tableStyles.tdMono}>{pct(c.ban_rate)}</td>
                    <td style={tableStyles.tdMono}>{c.avg_kills.toFixed(1)}/{c.avg_deaths.toFixed(1)}/{c.avg_assists.toFixed(1)}</td>
                    <td style={tableStyles.tdMono}>{kda(c).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding: "8px 12px", fontSize: 11, color: "var(--text-muted)", borderTop: "1px solid var(--border)" }}>
            {filtered.length} champion{filtered.length !== 1 ? "s" : ""}
          </div>
        </Card>

        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <span style={{ ...sectionTitle, margin: 0 }}>{selected.champion_name}</span>
                <button onClick={() => setSelected(null)} style={tableStyles.closeBtn}>
                  <X size={14} />
                </button>
              </div>
              <div style={{ display: "flex", justifyContent: "space-around", flexWrap: "wrap", gap: 12 }}>
                <StatBox label="Win Rate" value={pct(selected.winrate)} color={wrColor(selected.winrate)} />
                <StatBox label="Pick Rate" value={pct(selected.pick_rate)} />
                <StatBox label="Ban Rate" value={pct(selected.ban_rate)} />
                <StatBox label="KDA" value={kda(selected).toFixed(2)} />
              </div>
            </Card>

            <Card>
              <div style={sectionTitle}>Performance</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12 }}>
                <DetailRow label="Avg Kills" value={selected.avg_kills.toFixed(1)} />
                <DetailRow label="Avg Deaths" value={selected.avg_deaths.toFixed(1)} />
                <DetailRow label="Avg Assists" value={selected.avg_assists.toFixed(1)} />
                <DetailRow label="Avg CS" value={selected.avg_cs.toLocaleString()} />
                <DetailRow label="Avg Gold" value={selected.avg_gold.toLocaleString()} />
                <DetailRow label="Avg Damage" value={selected.avg_damage.toLocaleString()} />
                <DetailRow label="Avg Vision" value={selected.avg_vision.toFixed(1)} />
                <DetailRow label="Range" value={String(selected.attack_range)} />
              </div>
              {selected.tags.length > 0 && (
                <div style={{ display: "flex", gap: 4, marginTop: 12 }}>
                  {selected.tags.map((t) => (
                    <span key={t} style={{ ...styles.chip, ...styles.chipActive, cursor: "default" }}>{t}</span>
                  ))}
                </div>
              )}
            </Card>

            {positionData.length > 0 && (
              <Card>
                <div style={sectionTitle}>Position Distribution</div>
                <div style={{ marginTop: 12, height: 160 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={positionData} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} />
                      <YAxis type="category" dataKey="position" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={60} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Bar dataKey="games" fill="var(--accent)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "champion_name", label: "Champion" },
  { key: "games", label: "Games" },
  { key: "winrate", label: "Win %" },
  { key: "pick_rate", label: "Pick %" },
  { key: "ban_rate", label: "Ban %" },
  { key: "avg_kills", label: "K/D/A" },
  { key: "kda", label: "KDA" },
];

const styles: Record<string, React.CSSProperties> = {
  select: {
    ...inputStyle,
    cursor: "pointer",
  },
  chip: {
    padding: "4px 10px",
    fontSize: 11,
    fontWeight: 600,
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: 12,
    color: "var(--text-secondary)",
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "all 0.15s",
  },
  chipActive: {
    background: "var(--accent)",
    color: "var(--bg-primary)",
    borderColor: "var(--accent)",
  },
};
