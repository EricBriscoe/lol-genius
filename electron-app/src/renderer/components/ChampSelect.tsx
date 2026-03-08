import { useState, useEffect, useRef } from "react";
import type { ChampSelectUpdate, ChampSelectPlayerInfo } from "../types";
import { sectionTitle } from "../styles";
import { titleCase, toBlueProb } from "../utils";
import Card from "./Card";
import WinProbBar from "./WinProbBar";
import KeyFactors from "./KeyFactors";

const PHASE_LABELS: Record<string, string> = {
  BAN_PICK: "Banning",
  PLANNING: "Banning",
  FINALIZATION: "Finalization",
  GAME_STARTING: "Game Starting",
};

function formatPhase(phase: string): string {
  return PHASE_LABELS[phase] ?? titleCase(phase);
}

const POSITION_LABELS: Record<string, string> = {
  top: "TOP",
  jungle: "JNG",
  middle: "MID",
  bottom: "BOT",
  utility: "SUP",
};

const POSITION_ORDER = ["top", "jungle", "middle", "bottom", "utility"];

interface Props {
  data: ChampSelectUpdate;
}

function champImageUrl(version: string, championKey: string): string {
  return `https://ddragon.leagueoflegends.com/cdn/${version}/img/champion/${championKey}.png`;
}

function sortByPosition(players: ChampSelectPlayerInfo[]): ChampSelectPlayerInfo[] {
  return [...players].sort((a, b) => {
    const ai = POSITION_ORDER.indexOf(a.position?.toLowerCase());
    const bi = POSITION_ORDER.indexOf(b.position?.toLowerCase());
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
}

export default function ChampSelect({ data }: Props) {
  const blueProb = toBlueProb(data.blue_win_probability);
  const serverSeconds = Math.ceil(data.timer_remaining / 1000);

  const [displaySeconds, setDisplaySeconds] = useState(serverSeconds);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setDisplaySeconds(serverSeconds);
  }, [serverSeconds]);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (displaySeconds <= 0) return;
    intervalRef.current = setInterval(() => setDisplaySeconds((s) => Math.max(0, s - 1)), 1000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [serverSeconds]);

  const blueSorted = sortByPosition(data.blue_team.players);
  const redSorted = sortByPosition(data.red_team.players);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ textAlign: "center", fontSize: 12, color: "var(--text-muted)" }}>
        {formatPhase(data.phase)}
        {displaySeconds > 0 && ` — ${displaySeconds}s`}
      </div>

      {data.blue_win_probability != null && (
        <Card>
          <h3 style={sectionTitle}>Win Probability</h3>
          <WinProbBar blueProb={blueProb} />
        </Card>
      )}

      <Card>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--accent)", marginBottom: 4, textAlign: "center" }}>
              {data.is_blue_side ? "Your Team" : "Blue Side"}
            </div>
            {blueSorted.map((p, i) => (
              <PlayerRow key={i} player={p} side="blue" version={data.ddragon_version} />
            ))}
          </div>

          <div style={{
            display: "flex", flexDirection: "column", justifyContent: "center",
            gap: 4, padding: "0 12px", alignItems: "center",
          }}>
            {POSITION_ORDER.map((pos) => (
              <div key={pos} style={{
                fontSize: 10, fontWeight: 600, color: "var(--text-muted)",
                height: 32, display: "flex", alignItems: "center",
              }}>
                {POSITION_LABELS[pos]}
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--red)", marginBottom: 4, textAlign: "center" }}>
              {!data.is_blue_side ? "Your Team" : "Red Side"}
            </div>
            {redSorted.map((p, i) => (
              <PlayerRow key={i} player={p} side="red" version={data.ddragon_version} />
            ))}
          </div>
        </div>
      </Card>

      {data.top_factors && data.top_factors.length > 0 && (
        <Card>
          <h3 style={sectionTitle}>Key Factors</h3>
          <KeyFactors factors={data.top_factors} />
        </Card>
      )}

      <BanRow bans={data.bans} />
    </div>
  );
}

function PlayerRow({ player, side, version }: {
  player: ChampSelectPlayerInfo;
  side: "blue" | "red";
  version: string;
}) {
  const hasChamp = player.championId > 0 && player.championKey;
  const color = side === "blue" ? "var(--accent)" : "var(--red)";
  const isRight = side === "red";

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, height: 32,
      flexDirection: isRight ? "row-reverse" : "row",
      opacity: hasChamp ? 1 : 0.4,
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 4, overflow: "hidden",
        background: "var(--bg-primary)", flexShrink: 0,
        border: player.isLocalPlayer ? `2px solid ${color}` : "1px solid var(--border)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {hasChamp && version ? (
          <img
            src={champImageUrl(version, player.championKey)}
            alt={player.championName}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={(e) => {
              const img = e.target as HTMLImageElement;
              const fallback = document.createElement("span");
              fallback.textContent = player.championName[0] ?? "?";
              Object.assign(fallback.style, {
                fontSize: "12px", fontWeight: "700",
                color: "var(--text-muted)",
              });
              img.replaceWith(fallback);
            }}
          />
        ) : null}
      </div>
      <span style={{
        fontSize: 12, color: hasChamp ? "var(--text-primary)" : "var(--text-muted)",
        fontWeight: player.isLocalPlayer ? 600 : 400,
      }}>
        {hasChamp ? player.championName : "Picking..."}
      </span>
    </div>
  );
}

function BanRow({ bans }: { bans: { blue: number[]; red: number[] } }) {
  const blueBans = bans.blue.filter((b) => b > 0);
  const redBans = bans.red.filter((b) => b > 0);

  if (blueBans.length === 0 && redBans.length === 0) return null;

  return (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 4 }}>
          <span style={{ fontSize: 11, color: "var(--accent)", marginRight: 4 }}>Bans</span>
          {blueBans.map((_, i) => (
            <div key={i} style={{
              width: 20, height: 20, borderRadius: 3, background: "var(--bg-primary)",
              border: "1px solid var(--accent)", opacity: 0.6,
            }} />
          ))}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {redBans.map((_, i) => (
            <div key={i} style={{
              width: 20, height: 20, borderRadius: 3, background: "var(--bg-primary)",
              border: "1px solid var(--red)", opacity: 0.6,
            }} />
          ))}
          <span style={{ fontSize: 11, color: "var(--red)", marginLeft: 4 }}>Bans</span>
        </div>
      </div>
    </Card>
  );
}
