export function clearTimer(timer: ReturnType<typeof setInterval> | null): null {
  if (timer) clearInterval(timer);
  return null;
}
