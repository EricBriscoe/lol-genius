import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import Card from "../components/Card";
import StatBox from "../components/StatBox";
import { fetchStatus, fetchDistributions } from "../api";
import { tooltipStyle, sectionTitle, sectionLabel } from "../styles";
import type { CrawlerSSE, StatusData, DistributionData } from "../types";

const RANK_COLORS: Record<string, string> = {
  IRON: "#6b6b6b",
  BRONZE: "#a0522d",
  SILVER: "#a0aab4",
  GOLD: "#f0b232",
  PLATINUM: "#26d9b4",
  EMERALD: "#0acf83",
  DIAMOND: "#5b8def",
  MASTER: "#9b59b6",
  GRANDMASTER: "#c0392b",
  CHALLENGER: "#f1c40f",
};

const TIER_ORDER = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"];

interface Props {
  live: CrawlerSSE | null;
}

export default function CrawlerStatus({ live }: Props) {
  const [initial, setInitial] = useState<StatusData | null>(null);
  const [dist, setDist] = useState<DistributionData | null>(null);

  useEffect(() => {
    fetchStatus().then(setInitial).catch(() => {});
    fetchDistributions().then(setDist).catch(() => {});
  }, []);

  const matchCount = live?.match_count ?? initial?.match_count ?? 0;
  const queueStats = live?.queue_stats ?? initial?.queue_stats ?? {};
  const enrichment = live?.enrichment ?? initial?.enrichment ?? { enriched: 0, total: 0 };
  const queueDepth = live?.queue_depth ?? initial?.queue_depth ?? 0;

  const enrichPct = enrichment.total > 0 ? (enrichment.enriched / enrichment.total) * 100 : 0;
  const TARGET = 100000;
  const progressPct = Math.min((matchCount / TARGET) * 100, 100);

  const rankData = dist?.rank_distribution
    ? TIER_ORDER.filter((t) => dist.rank_distribution[t]).map((t) => ({
        tier: t,
        count: dist.rank_distribution[t],
      }))
    : [];

  const patchData = dist?.patch_distribution
    ? Object.entries(dist.patch_distribution).map(([patch, count]) => ({ patch, count }))
    : [];

  const tierSeedData = dist?.tier_seed_stats
    ? TIER_ORDER.filter((t) => dist.tier_seed_stats[t]).map((t) => {
        const stats = dist.tier_seed_stats[t];
        return {
          tier: t,
          pending: stats.pending || 0,
          processing: stats.processing || 0,
          done: stats.done || 0,
        };
      })
    : [];

  const ageRange = dist?.match_age_range;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Card glow>
        <div style={{ display: "flex", justifyContent: "space-around", flexWrap: "wrap", gap: 20 }}>
          <StatBox label="Total Matches" value={matchCount} color="var(--accent)" />
          <StatBox label="Queue Depth" value={queueDepth} />
          <StatBox
            label="Enrichment"
            value={`${enrichPct.toFixed(1)}%`}
            sub={`${enrichment.enriched.toLocaleString()} / ${enrichment.total.toLocaleString()}`}
          />
          <StatBox
            label="Queue Done"
            value={(queueStats.done || 0).toLocaleString()}
            sub={`${(queueStats.pending || 0).toLocaleString()} pending`}
          />
        </div>

        <div style={{ marginTop: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>
              Progress to {TARGET.toLocaleString()}
            </span>
            <span className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              {progressPct.toFixed(1)}%
            </span>
          </div>
          <div style={{ height: 8, background: "var(--bg-primary)", borderRadius: 4, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${progressPct}%`,
                background: "linear-gradient(90deg, var(--accent), var(--gold))",
                borderRadius: 4,
                transition: "width 0.5s ease",
              }}
            />
          </div>
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card>
          <h3 style={{ ...sectionTitle, marginBottom: 12 }}>Rank Distribution</h3>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rankData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="tier" tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{ color: "var(--text-primary)" }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {rankData.map((d) => (
                    <Cell key={d.tier} fill={RANK_COLORS[d.tier] || "var(--accent)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h3 style={{ ...sectionTitle, marginBottom: 12 }}>Patch Distribution</h3>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={patchData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="patch" tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{ color: "var(--text-primary)" }}
                />
                <Bar dataKey="count" fill="var(--blue)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <Card>
          <h3 style={{ ...sectionTitle, marginBottom: 12 }}>Seed Queue by Tier</h3>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tierSeedData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="tier" tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{ color: "var(--text-primary)" }}
                />
                <Bar dataKey="done" stackId="a" fill="var(--accent)" name="Done" />
                <Bar dataKey="processing" stackId="a" fill="var(--gold)" name="Processing" />
                <Bar dataKey="pending" stackId="a" fill="var(--text-muted)" name="Pending" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <h3 style={{ ...sectionTitle, marginBottom: 12 }}>Data Freshness</h3>
          {ageRange ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 12 }}>
              <div>
                <div style={{ ...sectionLabel, marginBottom: 2 }}>Oldest Match</div>
                <div className="mono" style={{ fontSize: 15, color: "var(--text-primary)" }}>
                  {new Date(ageRange.oldest).toLocaleDateString()}
                </div>
              </div>
              <div>
                <div style={{ ...sectionLabel, marginBottom: 2 }}>Newest Match</div>
                <div className="mono" style={{ fontSize: 15, color: "var(--text-primary)" }}>
                  {new Date(ageRange.newest).toLocaleDateString()}
                </div>
              </div>
              <div>
                <div style={{ ...sectionLabel, marginBottom: 2 }}>Time Span</div>
                <div className="mono" style={{ fontSize: 15, color: "var(--text-primary)" }}>
                  {Math.round(
                    (new Date(ageRange.newest).getTime() - new Date(ageRange.oldest).getTime()) /
                      (1000 * 60 * 60 * 24)
                  )}{" "}
                  days
                </div>
              </div>
              <div style={{ marginTop: 8 }}>
                <div style={{ ...sectionLabel, marginBottom: 2 }}>Queue Stats</div>
                {Object.entries(queueStats).map(([status, count]) => (
                  <div key={status} style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                    <span style={{ fontSize: 12, color: "var(--text-secondary)", textTransform: "capitalize" }}>{status}</span>
                    <span className="mono" style={{ fontSize: 12, color: "var(--text-primary)" }}>{count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 16 }}>No data available</div>
          )}
        </Card>
      </div>
    </div>
  );
}

