import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { FLOOD_LUT, HYPSO_LUT, NO_DATA_COLOR, SLOPE_LUT, SUSC_RGB, hexToRgb } from "./terrainPalette";

/** Visor 3D del terreno. Render SOLO bajo demanda (el equipo dibuja por software): nada de bucle continuo. */
export interface MeshData {
  width: number;
  height: number;
  bbox: number[];            // [minLon, minLat, maxLon, maxLat]
  min: number;
  max: number;
  heights: number[];         // m, fila a fila (norte → sur)
  slopes: number[];          // grados enteros
  extent_m: [number, number];
  valid?: number[];           // 1 = dato real, 0 = sin dato (se dibuja en gris)
  valid_pct?: number;
}
export type PathPoint = [number, number, number]; // lon, lat, elevación
export type Layer = "elevation" | "slope" | "scenario";
/** Capa de escenario (SIMULACIÓN) alineada celda a celda con la malla 3D. */
export interface ScenarioGrid {
  kind: string;               // "susceptibilidad" | "inundacion_demostrativa"
  width: number;
  height: number;
  values: number[];           // susceptibilidad: 0 sin dato, 1-3 clases; inundación: -1 sin dato, 0 seco, >0 profundidad (m)
  max_depth_m?: number | null;
}

const SIZE = 100;  // unidades de escena del lado mayor
const NO_DATA = hexToRgb(NO_DATA_COLOR);

interface Props {
  mesh: MeshData;
  exaggeration: number;
  layer: Layer;
  path?: PathPoint[] | null;
  scenario?: ScenarioGrid | null;
}

interface Scene3D {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  render: () => void;
  terrain?: THREE.Mesh;
  overlay?: THREE.Group;
}

function disposeObject(o: THREE.Object3D | undefined) {
  o?.traverse((n) => {
    const m = n as THREE.Mesh;
    m.geometry?.dispose();
    const mat = m.material as THREE.Material | THREE.Material[] | undefined;
    (Array.isArray(mat) ? mat : mat ? [mat] : []).forEach((x) => x.dispose());
  });
  o?.parent?.remove(o);
}

export default function Terrain3D({ mesh, exaggeration, layer, path, scenario }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const s = useRef<Scene3D | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Escena: se crea una vez; se destruye por completo al desmontar.
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: "low-power" });
    } catch {
      setError("Este navegador no pudo iniciar WebGL; el visor 3D no está disponible.");
      return;
    }
    renderer.setPixelRatio(1);
    renderer.setClearColor(0xdfe7ee);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.5, 1000);
    camera.position.set(0, 85, 115);
    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(-60, 100, 40);
    scene.add(sun);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;      // el amortiguado exigiría un bucle continuo
    controls.maxPolarAngle = Math.PI / 2 - 0.02;
    controls.minDistance = 20;
    controls.maxDistance = 400;
    let frame = 0;
    const render = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => { frame = 0; renderer.render(scene, camera); });
    };
    controls.addEventListener("change", render);
    el.appendChild(renderer.domElement);
    renderer.domElement.style.display = "block";
    const resize = () => {
      const w = Math.max(200, el.clientWidth), h = Math.max(240, el.clientHeight);
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      render();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();
    s.current = { renderer, scene, camera, controls, render };
    return () => {
      if (frame) cancelAnimationFrame(frame);  // evita render() después de dispose()
      ro.disconnect();
      controls.removeEventListener("change", render);
      controls.dispose();
      disposeObject(s.current?.terrain);
      disposeObject(s.current?.overlay);
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      s.current = null;
    };
  }, []);

  // Geometría: solo cuando cambia la malla.
  useEffect(() => {
    const st = s.current;
    if (!st) return;
    disposeObject(st.terrain);
    const [ex, ez] = mesh.extent_m;
    const k = SIZE / Math.max(ex, ez);
    const geo = new THREE.PlaneGeometry(ex * k, ez * k, mesh.width - 1, mesh.height - 1);
    geo.rotateX(-Math.PI / 2);
    geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(mesh.width * mesh.height * 3), 3));
    const mat = new THREE.MeshLambertMaterial({ vertexColors: true });
    st.terrain = new THREE.Mesh(geo, mat);
    st.scene.add(st.terrain);
    st.controls.target.set(0, 0, 0);
    st.controls.update();
  }, [mesh]);

  // Alturas, colores y trayectoria: al cambiar exageración, capa, malla o trayectoria.
  useEffect(() => {
    const st = s.current;
    const terrain = st?.terrain;
    if (!st || !terrain) return;
    const [ex, ez] = mesh.extent_m;
    const k = SIZE / Math.max(ex, ez);
    const vs = k * exaggeration;
    const geo = terrain.geometry as THREE.PlaneGeometry;
    const pos = geo.getAttribute("position") as THREE.BufferAttribute;
    const col = geo.getAttribute("color") as THREE.BufferAttribute;
    const range = Math.max(1, mesh.max - mesh.min);
    // Solo se pinta la capa si coincide exactamente con la malla (misma forma); si no, se ignora.
    const sc = scenario && scenario.width === mesh.width && scenario.height === mesh.height ? scenario : null;
    for (let i = 0; i < mesh.heights.length; i++) {
      pos.setY(i, (mesh.heights[i] - mesh.min) * vs);
      if (mesh.valid && !mesh.valid[i]) {
        col.setXYZ(i, NO_DATA[0], NO_DATA[1], NO_DATA[2]);
        continue;
      }
      if (layer === "scenario" && sc) {
        const v = sc.values[i];
        if (sc.kind === "susceptibilidad") {
          const c = SUSC_RGB[v] ?? NO_DATA;
          col.setXYZ(i, c[0], c[1], c[2]);
          continue;
        }
        if (v < 0) { col.setXYZ(i, NO_DATA[0], NO_DATA[1], NO_DATA[2]); continue; }
        if (v > 0) {
          const k = Math.round(Math.min(1, v / Math.max(0.1, sc.max_depth_m ?? 1)) * 255) * 3;
          col.setXYZ(i, FLOOD_LUT[k], FLOOD_LUT[k + 1], FLOOD_LUT[k + 2]);
          continue;
        }
      }
      const j = layer !== "slope"
        ? Math.round(Math.min(1, Math.max(0, (mesh.heights[i] - mesh.min) / range)) * 255) * 3
        : Math.min(90, Math.max(0, mesh.slopes[i])) * 3;
      const lut = layer === "slope" ? SLOPE_LUT : HYPSO_LUT;
      col.setXYZ(i, lut[j], lut[j + 1], lut[j + 2]);
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    geo.computeVertexNormals();
    geo.computeBoundingSphere();

    disposeObject(st.overlay);
    st.overlay = undefined;
    if (path && path.length > 1) {
      const [minx, miny, maxx, maxy] = mesh.bbox;
      const pts = path.map(([lon, lat, z]) => new THREE.Vector3(
        ((lon - minx) / (maxx - minx) - 0.5) * ex * k,
        (z - mesh.min) * vs + 0.6,
        ((maxy - lat) / (maxy - miny) - 0.5) * ez * k));
      const g = new THREE.Group();
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xd50000 })));
      const ball = (p: THREE.Vector3, color: number) => {
        const m = new THREE.Mesh(new THREE.SphereGeometry(0.9, 8, 6), new THREE.MeshBasicMaterial({ color }));
        m.position.copy(p);
        g.add(m);
      };
      ball(pts[0], 0xffffff);
      ball(pts[pts.length - 1], 0x1565c0);
      st.scene.add(g);
      st.overlay = g;
    }
    st.render();
  }, [mesh, exaggeration, layer, path, scenario]);

  if (error) return <div className="notice notice-danger" role="alert">{error}</div>;
  return <div ref={host} style={{ width: "100%", height: 460, borderRadius: 8, overflow: "hidden", touchAction: "none" }}
              aria-label="Visor 3D del terreno: arrastre para rotar, rueda para acercar" />;
}
