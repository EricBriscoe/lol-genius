import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { MatchRow } from "../types";
import { champIconUrl, itemIconUrl, hideOnImgError } from "../utils";

interface ParticipantSummary {
  puuid: string;
  gameName: string;
  tagLine: string;
  championId: number;
  teamId: number;
  kills: number;
  deaths: number;
  assists: number;
  cs: number;
  goldEarned: number;
  totalDamage: number;
  win: boolean;
  position: string;
}

const QUEUE_NAMES: Record<number, string> = {
  420: "Ranked Solo",
  440: "Ranked Flex",
  400: "Normal Draft",
  430: "Normal Blind",
  450: "ARAM",
  1700: "Arena",
  900: "URF",
  1900: "URF",
};

function timeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function MatchCard({ match, ddragonVersion }: { match: MatchRow; ddragonVersion: string }) {
  const [expanded, setExpanded] = useState(false);
  const isWin = match.win === 1;
  const items = [match.item0, match.item1, match.item2, match.item3, match.item4, match.item5, match.item6];
  const csPerMin = match.cs != null && match.game_duration
    ? (match.cs / (match.game_duration / 60)).toFixed(1)
    : null;

  let participants: ParticipantSummary[] = [];
  if (expanded && match.participants_json) {
    try { participants = JSON.parse(match.participants_json); } catch { /* */ }
  }

  const team1 = participants.filter((p) => p.teamId === 100);
  const team2 = participants.filter((p) => p.teamId === 200);

  return (
    <div className={`match-card ${isWin ? "match-card--win" : "match-card--loss"}`}>
      <div className="match-card__main" onClick={() => setExpanded(!expanded)}>
        <div className="match-card__result">
          <span className={`match-card__result-text ${isWin ? "match-card__result-text--win" : "match-card__result-text--loss"}`}>
            {isWin ? "W" : "L"}
          </span>
        </div>

        <div className="match-card__champ">
          {match.champion_id && (
            <img
              className="match-card__champ-icon"
              src={champIconUrl(match.champion_id)}
              alt=""
              onError={hideOnImgError}
            />
          )}
        </div>

        <div className="match-card__info">
          <div className="match-card__kda">
            <span>{match.kills ?? 0}</span>
            <span className="match-card__kda-sep">/</span>
            <span className="match-card__deaths">{match.deaths ?? 0}</span>
            <span className="match-card__kda-sep">/</span>
            <span>{match.assists ?? 0}</span>
          </div>
          <div className="match-card__cs">
            {match.cs ?? 0} CS{csPerMin && ` (${csPerMin}/m)`}
          </div>
        </div>

        <div className="match-card__items">
          {items.map((id, i) => (
            <div key={i} className="match-card__item-slot">
              {id != null && id > 0 && (
                <img src={itemIconUrl(id, ddragonVersion)} alt="" onError={hideOnImgError} />
              )}
            </div>
          ))}
        </div>

        <div className="match-card__meta">
          <div className="match-card__queue">
            {match.queue_id != null ? QUEUE_NAMES[match.queue_id] ?? "Game" : "Game"}
          </div>
          <div className="match-card__time">
            {formatDuration(match.game_duration)} · {timeAgo(match.game_creation)}
          </div>
        </div>

        <div className="match-card__expand">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>

      {expanded && participants.length > 0 && (
        <div className="match-card__details">
          <ParticipantTable team={team1} label="Blue Team" side="blue" />
          <ParticipantTable team={team2} label="Red Team" side="red" />
        </div>
      )}
    </div>
  );
}

function ParticipantTable({ team, label, side }: {
  team: ParticipantSummary[];
  label: string;
  side: "blue" | "red";
}) {
  return (
    <div className="match-card__team-table">
      <div className={`match-card__team-header match-card__team-header--${side}`}>{label}</div>
      {team.map((p, i) => (
        <div key={i} className="match-card__participant-row">
          <img
            className="match-card__participant-icon"
            src={champIconUrl(p.championId)}
            alt=""
            onError={hideOnImgError}
          />
          <span className="match-card__participant-name">{p.gameName}</span>
          <span className="match-card__participant-kda">
            {p.kills}/{p.deaths}/{p.assists}
          </span>
          <span className="match-card__participant-cs">{p.cs} CS</span>
          <span className="match-card__participant-dmg">
            {(p.totalDamage / 1000).toFixed(1)}k dmg
          </span>
        </div>
      ))}
    </div>
  );
}
