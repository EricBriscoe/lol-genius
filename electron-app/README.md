# lol-genius Desktop App

Real-time League of Legends win probability predictions during live games.

## How It Works

The app polls the [League Client API](https://developer.riotgames.com/docs/lol#game-client-api) every 15 seconds to read live game state (kills, towers, dragons, CS, etc.), runs inference through an ONNX model, and displays SHAP-based feature explanations showing which factors are driving the prediction.

## Prerequisites

- **Node.js 20+**
- **Python 3.11+** (for building the SHAP sidecar binary)
- A trained live model (see [Model Files](#model-files))

## Development

```bash
npm install
npm run dev
```

## Model Files

The app expects model files in the `models/` directory:

| File | Description |
|------|-------------|
| `model.onnx` | ONNX-exported XGBoost model |
| `model.json` | XGBoost model in JSON format (used by SHAP sidecar) |
| `feature_names.json` | Ordered feature name list |
| `feature_importance.json` | Feature importance scores |
| `calibrator.json` | Isotonic calibration thresholds (optional) |

### Populating model files

**Option A — Train via pipeline:**

```bash
# From the project root
lol-genius train --live
lol-genius export-model --format onnx --type live
# Copy outputs from data/models/live/ to electron-app/models/
```

**Option B — Download from GitHub release:**

Model files are published as GitHub releases with `model-v*` tags. The app auto-downloads the latest model on startup.

## Testing

```bash
npm test            # Single run
npm run test:watch  # Watch mode
```

## Building

```bash
# Build the SHAP sidecar
pip install pyinstaller xgboost shap numpy pandas
pyinstaller --onefile --collect-binaries xgboost --distpath sidecar/dist --name shap_predict sidecar/shap_predict.py

# Build the Electron app
npx electron-builder --win   # Windows
npx electron-builder --mac   # macOS
```

Output artifacts are written to `dist-electron/`.

## Architecture

```
src/
├── main/                  # Main process
│   ├── main.ts            # App lifecycle, IPC handlers
│   ├── updater.ts         # App + model auto-update from GitHub releases
│   ├── log.ts             # electron-log configuration
│   ├── model/
│   │   ├── inference.ts   # ONNX model loading + prediction
│   │   ├── features.ts    # Live Client data → feature vector
│   │   ├── calibrator.ts  # Isotonic calibration
│   │   └── constants.ts   # Feature names, snapshot intervals
│   ├── live-client/
│   │   ├── api.ts         # HTTPS polling of League Client API
│   │   └── poller.ts      # Poll loop, momentum tracking, IPC sends
│   └── shap/
│       └── sidecar.ts     # Spawns Python SHAP binary for explanations
├── preload/               # Context bridge (main ↔ renderer)
└── renderer/              # React UI (win probability, charts, factors)
```

## Auto-Update

On startup the app checks GitHub releases for:
- **App updates** — via `electron-updater` (requires signed builds)
- **Model updates** — downloads `model-v*` release assets to `userData/models/`, verified with SHA-256 checksums

## macOS Gatekeeper

Unsigned DMGs will be blocked by Gatekeeper. To run:

```bash
xattr -cr /Applications/lol-genius.app
```
