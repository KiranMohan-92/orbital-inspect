import { useRef, useState, useCallback, Suspense } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import * as THREE from "three";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DamageItem {
  id: number;
  type: string;
  severity: string;
  bounding_box: number[]; // [ymin, xmin, ymax, xmax] 0-1000
  label: string;
  confidence: number;
}

export interface SatelliteViewer3DProps {
  damages: DamageItem[];
  orbitalRegime?: string;
  className?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  SEVERE: "#f97316",
  MODERATE: "#eab308",
  MINOR: "#84cc16",
};

const SEVERITY_HEX: Record<string, number> = {
  CRITICAL: 0xef4444,
  SEVERE: 0xf97316,
  MODERATE: 0xeab308,
  MINOR: 0x84cc16,
};

function getSeverityKey(severity: string): string {
  const s = severity.toUpperCase();
  if (s in SEVERITY_HEX) return s;
  return "MINOR";
}

// ─── Star Field ───────────────────────────────────────────────────────────────

function StarField() {
  const ref = useRef<THREE.Points>(null);

  const { positions, sizes } = (() => {
    const count = 2000;
    const pos = new Float32Array(count * 3);
    const sz = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const r = 80 + Math.random() * 120;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
      sz[i] = 0.3 + Math.random() * 0.7;
    }
    return { positions: pos, sizes: sz };
  })();

  useFrame((_, delta) => {
    if (ref.current) {
      ref.current.rotation.y += delta * 0.005;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          array={positions}
          itemSize={3}
          count={positions.length / 3}
        />
        <bufferAttribute
          attach="attributes-size"
          array={sizes}
          itemSize={1}
          count={sizes.length}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#ffffff"
        size={0.15}
        sizeAttenuation
        transparent
        opacity={0.7}
        fog={false}
      />
    </points>
  );
}

// ─── Orbit Ring ───────────────────────────────────────────────────────────────

function OrbitRing() {
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[4.5, 0.015, 8, 120]} />
      <meshBasicMaterial
        color="#4d7cff"
        transparent
        opacity={0.12}
        depthWrite={false}
      />
    </mesh>
  );
}

// ─── Solar Panel Grid Lines ───────────────────────────────────────────────────

function SolarPanelLines({
  position,
  rotation,
}: {
  position: [number, number, number];
  rotation: [number, number, number];
}) {
  const linePositions: number[] = [];
  // Horizontal lines
  for (let i = -3; i <= 3; i++) {
    const y = (i / 3) * 0.72;
    linePositions.push(-1.48, y, 0.012, 1.48, y, 0.012);
  }
  // Vertical lines
  for (let i = -4; i <= 4; i++) {
    const x = (i / 4) * 1.48;
    linePositions.push(x, -0.72, 0.012, x, 0.72, 0.012);
  }

  const posArray = new Float32Array(linePositions);

  return (
    <group position={position} rotation={rotation}>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            array={posArray}
            itemSize={3}
            count={posArray.length / 3}
          />
        </bufferGeometry>
        <lineBasicMaterial color="#00d4ff" transparent opacity={0.25} />
      </lineSegments>
    </group>
  );
}

// ─── Satellite Body ───────────────────────────────────────────────────────────

function SatelliteBody() {
  return (
    <group>
      {/* Central bus */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[1.5, 1, 1]} />
        <meshStandardMaterial
          color="#1a1f35"
          metalness={0.85}
          roughness={0.25}
          envMapIntensity={1.2}
        />
      </mesh>

      {/* Bus surface detail stripes */}
      <mesh position={[0, 0, 0.502]}>
        <planeGeometry args={[1.4, 0.9]} />
        <meshStandardMaterial
          color="#0d1428"
          metalness={0.9}
          roughness={0.2}
          emissive="#4d7cff"
          emissiveIntensity={0.03}
        />
      </mesh>

      {/* Solar panels - left */}
      <mesh position={[-2.25, 0, 0]} castShadow>
        <boxGeometry args={[3, 1.45, 0.025]} />
        <meshStandardMaterial
          color="#0a1a3a"
          metalness={0.7}
          roughness={0.4}
          emissive="#001855"
          emissiveIntensity={0.15}
        />
      </mesh>
      <SolarPanelLines position={[-2.25, 0, 0]} rotation={[0, 0, 0]} />

      {/* Solar panels - right */}
      <mesh position={[2.25, 0, 0]} castShadow>
        <boxGeometry args={[3, 1.45, 0.025]} />
        <meshStandardMaterial
          color="#0a1a3a"
          metalness={0.7}
          roughness={0.4}
          emissive="#001855"
          emissiveIntensity={0.15}
        />
      </mesh>
      <SolarPanelLines position={[2.25, 0, 0]} rotation={[0, 0, 0]} />

      {/* Panel connectors / booms */}
      <mesh position={[-0.75, 0, 0]}>
        <boxGeometry args={[0.25, 0.08, 0.08]} />
        <meshStandardMaterial color="#2a2f45" metalness={0.9} roughness={0.2} />
      </mesh>
      <mesh position={[0.75, 0, 0]}>
        <boxGeometry args={[0.25, 0.08, 0.08]} />
        <meshStandardMaterial color="#2a2f45" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Antenna dish */}
      <mesh position={[0, 0.65, 0]} rotation={[0, 0, 0]}>
        <torusGeometry args={[0.22, 0.025, 12, 48]} />
        <meshStandardMaterial color="#c0c8d8" metalness={0.95} roughness={0.1} />
      </mesh>
      <mesh position={[0, 0.68, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <sphereGeometry args={[0.18, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial
          color="#8090b0"
          metalness={0.8}
          roughness={0.3}
          side={THREE.DoubleSide}
        />
      </mesh>
      {/* Antenna feed */}
      <mesh position={[0, 0.82, 0]}>
        <cylinderGeometry args={[0.015, 0.015, 0.28, 6]} />
        <meshStandardMaterial color="#a0aabf" metalness={0.95} roughness={0.1} />
      </mesh>

      {/* Thrusters */}
      {(
        [
          [0.6, -0.52, 0.4],
          [-0.6, -0.52, 0.4],
          [0.6, -0.52, -0.4],
          [-0.6, -0.52, -0.4],
        ] as [number, number, number][]
      ).map((pos, i) => (
        <mesh key={i} position={pos}>
          <cylinderGeometry args={[0.045, 0.06, 0.12, 8]} />
          <meshStandardMaterial
            color="#3a3f55"
            metalness={0.9}
            roughness={0.15}
          />
        </mesh>
      ))}
    </group>
  );
}

// ─── Damage Marker ────────────────────────────────────────────────────────────

function DamageMarker({
  damage,
  onHover,
  onUnhover,
}: {
  damage: DamageItem;
  onHover: (id: number) => void;
  onUnhover: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [ymin, xmin, ymax, xmax] = damage.bounding_box;

  const cx = (xmin + xmax) / 2 / 1000; // 0-1
  const cy = (ymin + ymax) / 2 / 1000; // 0-1
  const w = (xmax - xmin) / 1000;
  const h = (ymax - ymin) / 1000;
  const area = w * h;

  // Map onto satellite surfaces:
  // x 0-0.35 → left panel, 0.35-0.65 → bus face, 0.65-1 → right panel
  let px: number, py: number, pz: number;
  if (cx < 0.35) {
    // Left solar panel
    const t = cx / 0.35;
    px = -3.75 + t * 3; // -3.75 to -0.75
    py = (cy - 0.5) * 1.4;
    pz = 0.02;
  } else if (cx > 0.65) {
    // Right solar panel
    const t = (cx - 0.65) / 0.35;
    px = 0.75 + t * 3; // 0.75 to 3.75
    py = (cy - 0.5) * 1.4;
    pz = 0.02;
  } else {
    // Bus face
    const t = (cx - 0.35) / 0.3;
    px = (t - 0.5) * 1.4;
    py = (cy - 0.5) * 0.9;
    pz = 0.52;
  }

  const sevKey = getSeverityKey(damage.severity);
  const color = SEVERITY_HEX[sevKey];
  const isCritical =
    sevKey === "CRITICAL" || sevKey === "SEVERE";
  const radius = 0.04 + Math.sqrt(area) * 0.35;

  useFrame((_, delta) => {
    if (!meshRef.current) return;
    if (isCritical) {
      const t = Date.now() * 0.003;
      const scale = 1 + Math.sin(t) * 0.35;
      meshRef.current.scale.setScalar(scale);
    }
    void delta;
  });

  return (
    <mesh
      ref={meshRef}
      position={[px, py, pz]}
      onPointerEnter={() => onHover(damage.id)}
      onPointerLeave={() => onUnhover()}
    >
      <sphereGeometry args={[radius, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={isCritical ? 1.2 : 0.6}
        metalness={0.1}
        roughness={0.4}
        transparent
        opacity={0.92}
      />
    </mesh>
  );
}

// ─── Damage Labels ────────────────────────────────────────────────────────────

function DamageLabel({
  damage,
  visible,
}: {
  damage: DamageItem;
  visible: boolean;
}) {
  const [ymin, xmin, ymax, xmax] = damage.bounding_box;
  const cx = (xmin + xmax) / 2 / 1000;
  const cy = (ymin + ymax) / 2 / 1000;

  let px: number, py: number, pz: number;
  if (cx < 0.35) {
    const t = cx / 0.35;
    px = -3.75 + t * 3;
    py = (cy - 0.5) * 1.4 + 0.3;
    pz = 0.15;
  } else if (cx > 0.65) {
    const t = (cx - 0.65) / 0.35;
    px = 0.75 + t * 3;
    py = (cy - 0.5) * 1.4 + 0.3;
    pz = 0.15;
  } else {
    const t = (cx - 0.35) / 0.3;
    px = (t - 0.5) * 1.4;
    py = (cy - 0.5) * 0.9 + 0.3;
    pz = 0.8;
  }

  const sevKey = getSeverityKey(damage.severity);
  const color = SEVERITY_COLORS[sevKey];

  if (!visible) return null;

  return (
    <Html
      position={[px, py, pz]}
      center
      distanceFactor={6}
      style={{ pointerEvents: "none" }}
    >
      <div
        style={{
          background: "rgba(2,2,8,0.88)",
          border: `1px solid ${color}`,
          borderRadius: "4px",
          padding: "4px 8px",
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: "10px",
          color: color,
          whiteSpace: "nowrap",
          backdropFilter: "blur(8px)",
          boxShadow: `0 0 8px ${color}40`,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 1 }}>{damage.label}</div>
        <div style={{ opacity: 0.7, fontSize: "9px" }}>
          {(damage.confidence * 100).toFixed(0)}% conf
        </div>
      </div>
    </Html>
  );
}

// ─── Scene ────────────────────────────────────────────────────────────────────

function AutoRotateController({
  hasInteracted,
}: {
  hasInteracted: boolean;
}) {
  return (
    <OrbitControls
      autoRotate={!hasInteracted}
      autoRotateSpeed={0.5}
      minDistance={3}
      maxDistance={15}
      enablePan={false}
      enableZoom
      makeDefault
    />
  );
}

function Scene({
  damages,
}: {
  damages: DamageItem[];
}) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [hasInteracted, setHasInteracted] = useState(false);

  const handleHover = useCallback(
    (id: number) => setHoveredId(id),
    []
  );
  const handleUnhover = useCallback(() => setHoveredId(null), []);
  const handleInteract = useCallback(() => setHasInteracted(true), []);

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.35} color="#b0c0ff" />
      <directionalLight
        position={[5, 8, 5]}
        intensity={1.4}
        color="#ffffff"
        castShadow
      />
      <directionalLight
        position={[-8, -3, -5]}
        intensity={0.25}
        color="#4d7cff"
      />
      <pointLight position={[0, 0, 8]} intensity={0.3} color="#00d4ff" />

      {/* Camera controls */}
      <AutoRotateController hasInteracted={hasInteracted} />
      <group onPointerDown={handleInteract}>
        {/* Orbit ring */}
        <OrbitRing />

        {/* Satellite */}
        <SatelliteBody />

        {/* Damage markers */}
        {damages.map((d) => (
          <DamageMarker
            key={d.id}
            damage={d}
            onHover={handleHover}
            onUnhover={handleUnhover}
          />
        ))}

        {/* Labels for hovered damage */}
        {damages.map((d) => (
          <DamageLabel
            key={`label-${d.id}`}
            damage={d}
            visible={hoveredId === d.id}
          />
        ))}
      </group>

      {/* Star field */}
      <StarField />
    </>
  );
}

// ─── HUD Overlay ──────────────────────────────────────────────────────────────

function HudOverlay({
  orbitalRegime,
  damageCount,
}: {
  orbitalRegime?: string;
  damageCount: number;
}) {
  return (
    <div
      style={{
        position: "absolute",
        top: 12,
        left: 12,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: "10px",
        color: "rgba(77,124,255,0.85)",
        pointerEvents: "none",
        userSelect: "none",
      }}
    >
      <div
        style={{
          background: "rgba(8,10,20,0.72)",
          border: "1px solid rgba(77,124,255,0.25)",
          borderRadius: 6,
          padding: "6px 10px",
          backdropFilter: "blur(12px)",
          lineHeight: 1.7,
        }}
      >
        {orbitalRegime && (
          <div style={{ color: "#00d4ff", letterSpacing: "0.08em" }}>
            REGIME: {orbitalRegime}
          </div>
        )}
        <div>
          DAMAGE MARKERS:{" "}
          <span style={{ color: damageCount > 0 ? "#ef4444" : "#84cc16" }}>
            {damageCount}
          </span>
        </div>
        <div style={{ opacity: 0.5, marginTop: 2, fontSize: "9px" }}>
          DRAG TO ROTATE · SCROLL TO ZOOM
        </div>
      </div>
    </div>
  );
}

// ─── Main Export ──────────────────────────────────────────────────────────────

export default function SatelliteViewer3D({
  damages,
  orbitalRegime,
  className = "",
}: SatelliteViewer3DProps) {
  return (
    <div
      className={className}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: 360,
        background: "#020208",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      <Canvas
        shadows
        camera={{ position: [0, 2, 8], fov: 45, near: 0.1, far: 500 }}
        gl={{
          antialias: true,
          alpha: false,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.1,
        }}
        style={{ background: "#020208" }}
      >
        <Suspense fallback={null}>
          <Scene damages={damages} />
        </Suspense>
      </Canvas>

      <HudOverlay
        orbitalRegime={orbitalRegime}
        damageCount={damages.length}
      />
    </div>
  );
}
