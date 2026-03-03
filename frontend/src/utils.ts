export function formatFeatureName(name: string): string {
  return name
    .replace(/^(blue|red)_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
