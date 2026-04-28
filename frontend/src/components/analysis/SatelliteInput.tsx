import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import type { UseAnalysisReturn } from "../../hooks/useAnalysisState";
import DemoSelector from "./DemoSelector";

interface SatelliteInputProps {
  analysis: UseAnalysisReturn;
  onAnalyze: () => void;
  onDemo?: (demoId: string) => void;
}

export default function SatelliteInput({ analysis, onAnalyze, onDemo }: SatelliteInputProps) {
  const {
    state,
    setImage,
    setNoradId,
    setAssetName,
    setExternalAssetId,
    setAssetType,
    setInspectionEpoch,
    setTargetSubsystem,
    setAssessmentMode,
    setAdditionalContext,
    reset,
  } = analysis;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const hasImage = !!state.image;
  const isAnalyzing = state.analysisStatus === "analyzing";

  const handleFile = (file: File) => {
    if (!file.type.startsWith("image/")) return;
    setImage(file);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--bg-panel-border)" }}>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent-orbital)" }} />
          <p className="label-mono">TARGET ACQUISITION</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto dark-scrollbar px-4 py-4 space-y-5">
        {/* Upload Zone */}
        {!hasImage ? (
          <button
            type="button"
            data-testid="upload-zone"
            className={`w-full rounded-lg p-8 flex flex-col items-center gap-4 cursor-pointer transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-transparent ${
              isDragOver ? "scale-[1.01]" : ""
            }`}
            style={{
              border: `1.5px dashed ${isDragOver ? "var(--accent-orbital)" : "var(--bg-panel-border)"}`,
              background: isDragOver ? "var(--accent-orbital-dim)" : "transparent",
              color: "inherit",
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            disabled={isAnalyzing}
            aria-label="Upload satellite imagery"
          >
            {/* Crosshair icon */}
            <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"
              style={{ color: isDragOver ? "var(--accent-orbital)" : "var(--text-tertiary)" }}>
              <circle cx="12" cy="12" r="3" strokeWidth={1} />
              <path strokeLinecap="round" strokeWidth={1} d="M12 2v4M12 18v4M2 12h4M18 12h4" />
            </svg>
            <div className="text-center">
              <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>
                Drop satellite imagery
              </p>
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                NASA, ESA, HEO Inspect, or operator photos
              </p>
            </div>
            <input ref={fileInputRef} data-testid="upload-input" type="file" accept="image/*" onChange={handleFileInput} className="sr-only" aria-label="Satellite imagery file" />
          </button>
        ) : (
          <div className="rounded-lg overflow-hidden relative" style={{ border: "1px solid var(--bg-panel-border)" }}>
            <img src={state.imagePreviewUrl!} alt="Satellite" className="w-full h-36 object-cover" />
            <div className="absolute inset-0" style={{
              background: "linear-gradient(transparent 50%, rgba(2,2,8,0.9) 100%)",
            }} />
            <div className="absolute bottom-0 left-0 right-0 px-3 py-2 flex items-center justify-between">
              <p className="text-xs truncate font-mono-data" style={{ color: "var(--text-data)" }}>
                {state.image!.name}
              </p>
              <button onClick={reset} disabled={isAnalyzing} data-testid="clear-image-button"
                className="text-xs px-2 py-0.5 rounded transition-colors"
                style={{ color: "var(--text-tertiary)", background: "rgba(255,255,255,0.06)" }}>
                CLR
              </button>
            </div>
          </div>
        )}

        {/* NORAD Catalog ID */}
        <div>
          <label className="label-mono block mb-2">ASSESSMENT MODE</label>
          <select
            data-testid="assessment-mode-select"
            value={state.assessmentMode}
            onChange={(e) => setAssessmentMode(e.target.value as typeof state.assessmentMode)}
            className="orbital-input w-full font-mono-data"
            disabled={isAnalyzing}
          >
            <option value="PUBLIC_SCREEN">Public Risk Screen</option>
            <option value="ENHANCED_TECHNICAL">Enhanced Technical</option>
            <option value="UNDERWRITING_GRADE">Underwriting Grade</option>
          </select>
          <p className="text-xs mt-1.5" style={{ color: "var(--text-tertiary)" }}>
            Public mode is screening only. Underwriting grade requires operator telemetry, calibrated imagery, geometry, covariance, and actuarial priors.
          </p>
        </div>

        <div>
          <label className="label-mono block mb-2">ASSET TYPE</label>
          <select
            data-testid="asset-type-select"
            value={state.assetType}
            onChange={(e) => setAssetType(e.target.value as typeof state.assetType)}
            className="orbital-input w-full font-mono-data"
            disabled={isAnalyzing}
          >
            <option value="satellite">Satellite</option>
            <option value="servicer">Servicer</option>
            <option value="station_module">Station Module</option>
            <option value="solar_array">Solar Array</option>
            <option value="radiator">Radiator</option>
            <option value="power_node">Power Node</option>
            <option value="compute_platform">Compute Platform</option>
            <option value="other">Other Orbital Asset</option>
          </select>
          <p className="text-xs mt-1.5" style={{ color: "var(--text-tertiary)" }}>
            Keeps the data model ready for orbital infrastructure and in-space builds.
          </p>
        </div>

        <div>
          <label className="label-mono block mb-2">CANONICAL ASSET LABEL</label>
          <input
            data-testid="asset-name-input"
            type="text"
            value={state.assetName}
            onChange={(e) => setAssetName(e.target.value)}
            placeholder="e.g. Haven-1 Power Bus Alpha"
            className="orbital-input w-full font-mono-data"
            disabled={isAnalyzing}
          />
          <p className="text-xs mt-1.5" style={{ color: "var(--text-tertiary)" }}>
            Used as the org-scoped canonical label when NORAD is absent or subsystem work is more specific than the object catalog.
          </p>
        </div>

        <div>
          <label className="label-mono block mb-2">OPERATOR ASSET ID</label>
          <input
            data-testid="external-asset-id-input"
            type="text"
            value={state.externalAssetId}
            onChange={(e) => setExternalAssetId(e.target.value)}
            placeholder="e.g. axiom-h1-pwr-a"
            className="orbital-input w-full font-mono-data"
            disabled={isAnalyzing}
          />
          <p className="text-xs mt-1.5" style={{ color: "var(--text-tertiary)" }}>
            Strongest non-NORAD identity key for servicers, station modules, arrays, radiators, and compute platforms.
          </p>
        </div>

        <div>
          <label className="label-mono block mb-2">NORAD CATALOG ID</label>
          <input
            data-testid="norad-input"
            type="text"
            value={state.noradId}
            onChange={(e) => setNoradId(e.target.value)}
            placeholder="e.g. 25544 (ISS)"
            className="orbital-input w-full font-mono-data"
            disabled={isAnalyzing}
          />
          <p className="text-xs mt-1.5" style={{ color: "var(--text-tertiary)" }}>
            Optional — enriches analysis with orbital parameters from CelesTrak
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-mono block mb-2">INSPECTION EPOCH</label>
            <input
              data-testid="inspection-epoch-input"
              type="text"
              value={state.inspectionEpoch}
              onChange={(e) => setInspectionEpoch(e.target.value)}
              placeholder="e.g. 2026-04-02T12:00Z"
              className="orbital-input w-full font-mono-data"
              disabled={isAnalyzing}
            />
          </div>
          <div>
            <label className="label-mono block mb-2">TARGET SUBSYSTEM</label>
            <input
              data-testid="target-subsystem-input"
              type="text"
              value={state.targetSubsystem}
              onChange={(e) => setTargetSubsystem(e.target.value)}
              placeholder="solar_array / radiator / bus"
              className="orbital-input w-full font-mono-data"
              disabled={isAnalyzing}
            />
          </div>
        </div>

        <div>
          <label className="label-mono block mb-2">OPERATOR CONTEXT</label>
          <textarea
            data-testid="context-input"
            value={state.additionalContext}
            onChange={(e) => setAdditionalContext(e.target.value)}
            placeholder="Inspection epoch, observed anomaly, subsystem notes, deployment phase, or operator context"
            className="orbital-input w-full font-mono-data min-h-[92px] resize-none"
            disabled={isAnalyzing}
          />
        </div>

        {/* Divider */}
        <hr className="orbital-divider" />

        {/* Quick Reference Targets */}
        <div>
          <p className="label-mono mb-2">REFERENCE TARGETS</p>
          <div className="space-y-1.5">
            {[
              { id: "25544", label: "ISS", detail: "LEO 408km · 51.6°" },
              { id: "20580", label: "HUBBLE", detail: "LEO 547km · 28.5°" },
              { id: "36585", label: "SDO", detail: "GEO · Solar Dynamics" },
            ].map((sat) => (
              <button
                key={sat.id}
                onClick={() => setNoradId(sat.id)}
                disabled={isAnalyzing}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-all glass-panel-hover"
                style={{ border: "1px solid var(--bg-panel-border)" }}
              >
                <span className="font-mono-data text-xs flex-shrink-0" style={{ minWidth: 44 }}>
                  #{sat.id}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="font-mono-display text-xs tracking-wider block" style={{ color: "var(--text-primary)" }}>
                    {sat.label}
                  </span>
                  <span className="text-xs block truncate" style={{ color: "var(--text-tertiary)" }}>
                    {sat.detail}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Divider */}
        <hr className="orbital-divider" />

        {/* Demo Cases */}
        {onDemo && (
          <DemoSelector onSelectDemo={onDemo} disabled={isAnalyzing} />
        )}
      </div>

      {/* Analyze Button */}
      <div className="px-4 py-3 flex-shrink-0" style={{ borderTop: "1px solid var(--bg-panel-border)" }}>
        <button
          onClick={onAnalyze}
          data-testid="analyze-button"
          disabled={!hasImage || isAnalyzing}
          className="w-full py-3 rounded-md font-mono-display text-sm tracking-[0.2em] transition-all"
          style={{
            background: hasImage && !isAnalyzing
              ? "linear-gradient(135deg, var(--accent-orbital), #6366f1)"
              : "rgba(255,255,255,0.03)",
            color: hasImage && !isAnalyzing ? "#ffffff" : "var(--text-tertiary)",
            opacity: !hasImage ? 0.3 : 1,
            cursor: !hasImage || isAnalyzing ? "not-allowed" : "pointer",
            boxShadow: hasImage && !isAnalyzing ? "0 0 20px rgba(77,124,255,0.2)" : "none",
          }}
        >
          {isAnalyzing ? "INSPECTING..." : "INSPECT ASSET"}
        </button>
      </div>
    </div>
  );
}
