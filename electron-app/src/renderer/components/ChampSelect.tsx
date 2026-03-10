import { useState, useEffect, useRef } from "react";
import type { ChampSelectUpdate, ChampSelectPlayerInfo } from "../types";
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
    <div className="champ-select">
      <div className="champ-select__phase">
        {formatPhase(data.phase)}
        {displaySeconds > 0 && ` — ${displaySeconds}s`}
      </div>

      {data.blue_win_probability != null && (
        <Card>
          <h3 className="section-title">Win Probability</h3>
          <WinProbBar blueProb={blueProb} />
        </Card>
      )}

      <Card>
        <div className="champ-select__grid">
          <div className="champ-select__team">
            <div className="champ-select__team-label champ-select__team-label--blue">
              {data.is_blue_side ? "Your Team" : "Blue Side"}
            </div>
            {blueSorted.map((p, i) => (
              <PlayerRow key={i} player={p} side="blue" version={data.ddragon_version} />
            ))}
          </div>

          <div className="champ-select__positions">
            {POSITION_ORDER.map((pos) => (
              <div key={pos} className="champ-select__position-label">
                {POSITION_LABELS[pos]}
              </div>
            ))}
          </div>

          <div className="champ-select__team">
            <div className="champ-select__team-label champ-select__team-label--red">
              {!data.is_blue_side ? "Your Team" : "Red Side"}
            </div>
            {redSorted.map((p, i) => (
              <PlayerRow key={i} player={p} side="red" version={data.ddragon_version} />
            ))}
          </div>
        </div>
      </Card>

      {data.factor_analysis && data.factor_analysis.groups.length > 0 && (
        <Card>
          <h3 className="section-title">Key Factors</h3>
          <KeyFactors analysis={data.factor_analysis} />
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
  const isRight = side === "red";

  let iconCls = "player-icon";
  if (player.isLocalPlayer) iconCls += ` player-icon--local-${side}`;

  let nameCls = "player-name";
  if (player.isLocalPlayer) nameCls += " player-name--local";
  if (!hasChamp) nameCls += " player-name--empty";

  return (
    <div
      className="player-row"
      style={{
        flexDirection: isRight ? "row-reverse" : "row",
        opacity: hasChamp ? 1 : 0.4,
      }}
    >
      <div className={iconCls}>
        {hasChamp && version ? (
          <img
            src={champImageUrl(version, player.championKey)}
            alt={player.championName}
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
      <span className={nameCls}>
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
      <div className="ban-row">
        <div className="ban-group">
          <span className="ban-label ban-label--blue">Bans</span>
          {blueBans.map((_, i) => (
            <div key={i} className="ban-slot ban-slot--blue" />
          ))}
        </div>
        <div className="ban-group">
          {redBans.map((_, i) => (
            <div key={i} className="ban-slot ban-slot--red" />
          ))}
          <span className="ban-label ban-label--red">Bans</span>
        </div>
      </div>
    </Card>
  );
}
