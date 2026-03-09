export default function WinProbBar({ blueProb }: { blueProb: number }) {
  const redProb = 100 - blueProb;
  const blueWinning = blueProb >= 50;

  return (
    <div className="win-prob">
      <div className="win-prob__labels">
        <span className="win-prob__label--blue">Blue {blueProb}%</span>
        <span className="win-prob__label--red">Red {redProb}%</span>
      </div>
      <div className="win-prob__track">
        <div
          className={`win-prob__fill win-prob__fill--blue${blueWinning ? " win-prob__fill--winning" : ""}`}
          style={{ width: `${blueProb}%` }}
        >
          {blueProb > 20 && `${blueProb}%`}
        </div>
        <div className={`win-prob__fill win-prob__fill--red${!blueWinning ? " win-prob__fill--winning" : ""}`}>
          {redProb > 20 && `${redProb}%`}
        </div>
        <div className="win-prob__edge" style={{ left: `${blueProb}%` }} />
      </div>
    </div>
  );
}
