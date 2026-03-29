import { useRef, useState, type DragEvent, type ChangeEvent } from "react";
import type { UseAnalysisReturn } from "../../hooks/useAnalysisState";

interface SatelliteInputProps {
  analysis: UseAnalysisReturn;
  onAnalyze: () => void;
}

export default function SatelliteInput({ analysis, onAnalyze }: SatelliteInputProps) {
  const { state, setImage, setNoradId, reset } = analysis;
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
          <div
            className={`rounded-lg p-8 flex flex-col items-center gap-4 cursor-pointer transition-all ${
              isDragOver ? "scale-[1.01]" : ""
            }`}
            style={{
              border: `1.5px dashed ${isDragOver ? "var(--accent-orbital)" : "var(--bg-panel-border)"}`,
              background: isDragOver ? "var(--accent-orbital-dim)" : "transparent",
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
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
            <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileInput} className="hidden" />
          </div>
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
              <button onClick={reset} disabled={isAnalyzing}
                className="text-xs px-2 py-0.5 rounded transition-colors"
                style={{ color: "var(--text-tertiary)", background: "rgba(255,255,255,0.06)" }}>
                CLR
              </button>
            </div>
          </div>
        )}

        {/* NORAD Catalog ID */}
        <div>
          <label className="label-mono block mb-2">NORAD CATALOG ID</label>
          <input
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
      </div>

      {/* Analyze Button */}
      <div className="px-4 py-3 flex-shrink-0" style={{ borderTop: "1px solid var(--bg-panel-border)" }}>
        <button
          onClick={onAnalyze}
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
          {isAnalyzing ? "INSPECTING..." : "INSPECT SATELLITE"}
        </button>
      </div>
    </div>
  );
}
