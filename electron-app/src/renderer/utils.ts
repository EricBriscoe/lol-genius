export function fmtTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function toBlueProb(raw: number | null | undefined): number {
  return raw != null ? Math.round(raw * 100) : 50;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function champIconUrl(championId: number): string {
  return `https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/${championId}.png`;
}

export function itemIconUrl(itemId: number, version: string): string {
  return `https://ddragon.leagueoflegends.com/cdn/${version}/img/item/${itemId}.png`;
}

export function winRateColor(winRate: number): string {
  if (winRate >= 55) return "var(--green)";
  if (winRate <= 45) return "var(--red)";
  return "var(--text-secondary)";
}

export function hideOnImgError(e: React.SyntheticEvent<HTMLImageElement>): void {
  (e.target as HTMLImageElement).style.display = "none";
}
