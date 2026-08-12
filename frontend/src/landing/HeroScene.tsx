/**
 * Landing hero — procedural Earth with orbiting inspection satellite.
 * No texture downloads: graticule wireframe + custom rim-glow shader keeps
 * first paint instant and matches the mission-control aesthetic.
 */
import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const EARTH_RADIUS = 2.2;
const ORBIT_RADIUS = 3.4;
const ORBIT_TILT = 0.45;

// ─── Starfield ────────────────────────────────────────────────────────────────

function Stars() {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const count = 1600;
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 40 + Math.random() * 60;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
    }
    return pos;
  }, []);

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.004;
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
      </bufferGeometry>
      <pointsMaterial size={0.06} color="#aab4d4" transparent opacity={0.7} sizeAttenuation />
    </points>
  );
}

// ─── Earth ────────────────────────────────────────────────────────────────────

const ATMOSPHERE_VERTEX = /* glsl */ `
  varying vec3 vNormal;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const ATMOSPHERE_FRAGMENT = /* glsl */ `
  varying vec3 vNormal;
  void main() {
    float intensity = pow(0.62 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.4);
    gl_FragColor = vec4(0.30, 0.49, 1.0, 1.0) * intensity;
  }
`;

/** Pseudo-random surface beacons — reads as "tracked assets" without real data. */
function useBeacons(count: number, radius: number) {
  return useMemo(() => {
    const pos = new Float32Array(count * 3);
    let seed = 42;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return seed / 2147483647;
    };
    for (let i = 0; i < count; i++) {
      // Bias toward northern mid-latitudes, where ground stations cluster
      const lat = (rand() * 110 - 40) * (Math.PI / 180);
      const lon = rand() * Math.PI * 2;
      pos[i * 3] = radius * Math.cos(lat) * Math.cos(lon);
      pos[i * 3 + 1] = radius * Math.sin(lat);
      pos[i * 3 + 2] = radius * Math.cos(lat) * Math.sin(lon);
    }
    return pos;
  }, [count, radius]);
}

function Earth() {
  const group = useRef<THREE.Group>(null);
  const beacons = useBeacons(140, EARTH_RADIUS * 1.002);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.03;
  });

  return (
    <group>
      {/* Dark body so the limb occludes stars */}
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS * 0.985, 48, 32]} />
        <meshBasicMaterial color="#04050d" />
      </mesh>

      <group ref={group}>
        {/* Graticule — the lat/long grid IS the planet */}
        <mesh>
          <sphereGeometry args={[EARTH_RADIUS, 36, 24]} />
          <meshBasicMaterial color="#4d7cff" wireframe transparent opacity={0.10} />
        </mesh>

        {/* Tracked-asset beacons */}
        <points>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              array={beacons}
              itemSize={3}
              count={beacons.length / 3}
            />
          </bufferGeometry>
          <pointsMaterial size={0.045} color="#00d4ff" transparent opacity={0.85} sizeAttenuation />
        </points>
      </group>

      {/* Atmosphere rim glow */}
      <mesh scale={1.18}>
        <sphereGeometry args={[EARTH_RADIUS, 48, 32]} />
        <shaderMaterial
          vertexShader={ATMOSPHERE_VERTEX}
          fragmentShader={ATMOSPHERE_FRAGMENT}
          blending={THREE.AdditiveBlending}
          side={THREE.BackSide}
          transparent
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

// ─── Inspection satellite ─────────────────────────────────────────────────────

function OrbitPath() {
  const points = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 128; i++) {
      const a = (i / 128) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * ORBIT_RADIUS, 0, Math.sin(a) * ORBIT_RADIUS));
    }
    return pts;
  }, []);
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  return (
    <primitive
      object={
        new THREE.Line(
          geometry,
          new THREE.LineBasicMaterial({ color: "#4d7cff", transparent: true, opacity: 0.28 })
        )
      }
    />
  );
}

function Satellite() {
  const orbit = useRef<THREE.Group>(null);
  const craft = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() * 0.22;
    if (orbit.current) orbit.current.rotation.y = -t;
    if (craft.current) {
      // Keep the scan cone aimed at the planet center
      craft.current.lookAt(0, 0, 0);
    }
  });

  return (
    <group rotation={[ORBIT_TILT, 0, 0.18]}>
      <OrbitPath />
      <group ref={orbit}>
        <group ref={craft} position={[ORBIT_RADIUS, 0, 0]}>
          {/* Bus */}
          <mesh>
            <boxGeometry args={[0.14, 0.14, 0.2]} />
            <meshStandardMaterial color="#c8d2f0" metalness={0.8} roughness={0.3} />
          </mesh>
          {/* Solar panels */}
          <mesh position={[0.32, 0, 0]}>
            <boxGeometry args={[0.42, 0.015, 0.16]} />
            <meshStandardMaterial color="#1a2c6b" metalness={0.6} roughness={0.4} />
          </mesh>
          <mesh position={[-0.32, 0, 0]}>
            <boxGeometry args={[0.42, 0.015, 0.16]} />
            <meshStandardMaterial color="#1a2c6b" metalness={0.6} roughness={0.4} />
          </mesh>
          {/* Scan cone — apex at craft, base toward Earth (+z after lookAt) */}
          <mesh position={[0, 0, (ORBIT_RADIUS - EARTH_RADIUS) * 0.5]} rotation={[-Math.PI / 2, 0, 0]}>
            <coneGeometry args={[0.55, ORBIT_RADIUS - EARTH_RADIUS, 24, 1, true]} />
            <meshBasicMaterial
              color="#00d4ff"
              transparent
              opacity={0.10}
              side={THREE.DoubleSide}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
          {/* Nav strobe */}
          <pointLight color="#00d4ff" intensity={0.6} distance={1.4} />
        </group>
      </group>
    </group>
  );
}

// ─── Parallax rig ─────────────────────────────────────────────────────────────

function ParallaxRig({ children }: { children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const { pointer } = useThree();

  useFrame(() => {
    if (!ref.current) return;
    ref.current.rotation.y = THREE.MathUtils.lerp(ref.current.rotation.y, pointer.x * 0.12, 0.04);
    ref.current.rotation.x = THREE.MathUtils.lerp(ref.current.rotation.x, -pointer.y * 0.08, 0.04);
  });

  return <group ref={ref}>{children}</group>;
}

// ─── Scene ────────────────────────────────────────────────────────────────────

export default function HeroScene() {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 0.6, 7.2], fov: 42 }}
      gl={{ antialias: true, alpha: true }}
      style={{ pointerEvents: "none" }}
      aria-hidden
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[6, 3, 4]} intensity={1.1} color="#9db4ff" />
      <ParallaxRig>
        <Stars />
        <group position={[1.15, -0.25, 0]}>
          <Earth />
          <Satellite />
        </group>
      </ParallaxRig>
    </Canvas>
  );
}
