import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { Play, X, Loader2 } from "lucide-react";
import Card from "../components/Card";
import { fetchModelRuns, triggerTraining } from "../api";
import { tooltipStyle, sectionTitle, primaryButton } from "../styles";
import type { ModelRun, TrainingStatus } from "../types";

interface Props {
  trainingStatus: TrainingStatus | null;
}

export default function ModelTraining({ trainingStatus }: Props) {
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [selected, setSelected] = useState<ModelRun | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    loadRuns();
  }, []);

  useEffect(() => {
    if (trainingStatus?.stage === "completed") loadRuns();
  }, [trainingStatus?.stage]);

  function loadRuns() {
    fetchModelRuns().then(setRuns).catch(() => {});
  }

  async function handleTrain() {
    await triggerTraining(notes);
    setShowModal(false);
    setNotes("");
  }

  const aucTrend = [...runs]
    .reverse()
    .filter((r) => r.auc_roc != null)
    .map((r, i) => ({ idx: i + 1, auc: r.auc_roc!, run: r.run_id.slice(0, 8) }));

  const isTraining = trainingStatus && !["completed", "error"].includes(trainingStatus.stage);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {trainingStatus && isTraining && (
        <Card glow>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Loader2 size={18} style={{ color: "var(--accent)", animation: "spin 1s linear infinite" }} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Training in progress</div>
              <div className="mono" style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
                Stage: {trainingStatus.stage}
                {trainingStatus.matches && ` | ${trainingStatus.matches.toLocaleString()} matches`}
                {trainingStatus.features && ` | ${trainingStatus.features} features`}
              </div>
            </div>
          </div>
          <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        </Card>
      )}

      {trainingStatus?.stage === "error" && (
        <Card style={{ borderColor: "var(--red)" }}>
          <div style={{ color: "var(--red)", fontSize: 13 }}>
            Training failed: {trainingStatus.error}
          </div>
        </Card>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: 16, fontWeight: 600 }}>Training Runs</h2>
        <button onClick={() => setShowModal(true)} disabled={!!isTraining} style={primaryButton}>
          <Play size={14} />
          New Training Run
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1fr 1fr" : "1fr", gap: 20 }}>
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <table style={styles.table}>
            <thead>
              <tr>
                {["Run ID", "Matches", "Features", "Accuracy", "AUC", "LogLoss", "Time"].map((h) => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.run_id}
                  onClick={() => setSelected(selected?.run_id === r.run_id ? null : r)}
                  style={{
                    ...styles.tr,
                    background: selected?.run_id === r.run_id ? "var(--bg-card-hover)" : undefined,
                  }}
                >
                  <td style={styles.td}>
                    <span className="mono" style={{ fontSize: 11 }}>{r.run_id}</span>
                    {r.notes && <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: 6 }}>{r.notes.slice(0, 15)}</span>}
                  </td>
                  <td style={styles.tdMono}>{r.total_matches.toLocaleString()}</td>
                  <td style={styles.tdMono}>{r.feature_count}</td>
                  <td style={styles.tdMono}>{r.accuracy != null ? r.accuracy.toFixed(4) : "-"}</td>
                  <td style={{ ...styles.tdMono, color: "var(--accent)" }}>{r.auc_roc != null ? r.auc_roc.toFixed(4) : "-"}</td>
                  <td style={styles.tdMono}>{r.log_loss != null ? r.log_loss.toFixed(4) : "-"}</td>
                  <td style={styles.tdMono}>{r.training_seconds != null ? `${r.training_seconds.toFixed(0)}s` : "-"}</td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ ...styles.td, textAlign: "center", color: "var(--text-muted)" }}>
                    No training runs yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>

        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3 style={sectionTitle}>Run Detail</h3>
                <button onClick={() => setSelected(null)} style={styles.closeBtn}><X size={14} /></button>
              </div>
              <div className="mono" style={{ fontSize: 12, color: "var(--accent)", marginBottom: 12 }}>{selected.run_id}</div>
              <div style={styles.detailGrid}>
                <DetailRow label="Created" value={selected.created_at ? new Date(selected.created_at).toLocaleString() : "-"} />
                <DetailRow label="Matches" value={`${selected.total_matches.toLocaleString()} (${selected.train_count.toLocaleString()} / ${selected.test_count.toLocaleString()})`} />
                <DetailRow label="Features" value={selected.feature_count.toString()} />
                <DetailRow label="Patches" value={`${selected.patch_min} - ${selected.patch_max}`} />
                <DetailRow label="Target Mean" value={selected.target_mean?.toFixed(4) || "-"} />
                <DetailRow label="Best Iteration" value={selected.best_iteration?.toString() || "-"} />
                {selected.notes && <DetailRow label="Notes" value={selected.notes} />}
              </div>
            </Card>

            {selected.accuracy != null && (
              <Card>
                <h3 style={sectionTitle}>Confusion Matrix</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, maxWidth: 240, margin: "12px auto 0" }}>
                  <CMCell label="TN" value={selected.tn!} color="var(--accent)" />
                  <CMCell label="FP" value={selected.fp!} color="var(--red)" />
                  <CMCell label="FN" value={selected.fn!} color="var(--red)" />
                  <CMCell label="TP" value={selected.tp!} color="var(--accent)" />
                </div>
              </Card>
            )}

            {selected.top_features && selected.top_features.length > 0 && (
              <Card>
                <h3 style={sectionTitle}>Top SHAP Features</h3>
                <div style={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={selected.top_features.slice(0, 10).reverse()}
                      layout="vertical"
                      margin={{ top: 5, right: 10, bottom: 5, left: 120 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis type="number" tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
                        width={115}
                      />
                      <Tooltip
                        contentStyle={tooltipStyle}
                      />
                      <Bar dataKey="importance" fill="var(--gold)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            {selected.hyperparameters && (
              <Card>
                <h3 style={sectionTitle}>Hyperparameters</h3>
                <div style={styles.detailGrid}>
                  {Object.entries(selected.hyperparameters).map(([k, v]) => (
                    <DetailRow key={k} label={k} value={String(v)} />
                  ))}
                </div>
              </Card>
            )}
          </div>
        )}
      </div>

      {aucTrend.length > 1 && (
        <Card>
          <h3 style={sectionTitle}>AUC Trend Across Runs</h3>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={aucTrend} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="run" tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <YAxis domain={["auto", "auto"]} tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 }}
                />
                <Line type="monotone" dataKey="auc" stroke="var(--accent)" strokeWidth={2} dot={{ fill: "var(--accent)", r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {showModal && (
        <div style={styles.overlay} onClick={() => setShowModal(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>New Training Run</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>
                Notes (optional)
              </label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. testing new features..."
                style={styles.input}
              />
            </div>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16 }}>
              This will build features, train, evaluate, and run SHAP analysis.
            </p>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setShowModal(false)} style={styles.cancelBtn}>Cancel</button>
              <button onClick={handleTrain} style={primaryButton}>
                <Play size={14} /> Start Training
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 12, color: "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

function CMCell({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      background: "var(--bg-primary)",
      border: "1px solid var(--border)",
      borderRadius: 6,
      padding: 12,
      textAlign: "center",
    }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>{label}</div>
      <div className="mono" style={{ fontSize: 20, fontWeight: 700, color }}>{value.toLocaleString()}</div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
  },
  th: {
    textAlign: "left",
    padding: "10px 12px",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--text-muted)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    borderBottom: "1px solid var(--border)",
    background: "var(--bg-secondary)",
  },
  tr: {
    cursor: "pointer",
    transition: "background 0.1s",
    borderBottom: "1px solid var(--border)",
  },
  td: {
    padding: "10px 12px",
    fontSize: 12,
  },
  tdMono: {
    padding: "10px 12px",
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
  },
  detailGrid: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 2,
    marginTop: 8,
  },
  closeBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 28,
    height: 28,
    background: "var(--bg-primary)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    color: "var(--text-secondary)",
    cursor: "pointer",
  },
  overlay: {
    position: "fixed" as const,
    inset: 0,
    background: "rgba(0,0,0,0.6)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 100,
  },
  modal: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: 24,
    width: 420,
    maxWidth: "90vw",
  },
  input: {
    width: "100%",
    padding: "8px 12px",
    fontSize: 13,
    background: "var(--bg-input)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    color: "var(--text-primary)",
    outline: "none",
    fontFamily: "inherit",
  },
  cancelBtn: {
    padding: "8px 16px",
    fontSize: 13,
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: 6,
    color: "var(--text-secondary)",
    cursor: "pointer",
    fontFamily: "inherit",
  },
};
