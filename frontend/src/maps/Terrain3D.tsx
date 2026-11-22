import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

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
}
export type PathPoint = [number, number, number]; // lon, lat, elevación
export type Layer = "elevation" | "slope";

// Paletas compartidas con la leyenda del panel.
export const HYPSO_STOPS: [number, string][] = [
  [0, "#2e7d32"], [0.25, "#9ccc65"], [0.5, "#e6d27a"], [0.75, "#9a6b45"], [1, "#f5f5f5"],
];
export const SLOPE_CLASSES: { max: number; color: string; label: string }[] = [
  { max: 15, color: "#43a047", label: "0-15°" },
  { max: 25, color: "#fdd835", label: "15-25°" },
  { max: 35, color: "#fb8c00", label: "25-35°" },
  { max: 91, color: "#d32f2f", label: ">35°" },
];

const SIZE = 100;  // unidades de escena del lado mayor

function hypso(t: number, out: THREE.Color) {
  const x = Math.min(1, Math.max(0, t));
  for (let i = 1; i < HYPSO_STOPS.length; i++) {
    if (x <= HYPSO_STOPS[i][0]) {
      const [t0, c0] = HYPSO_STOPS[i - 1];
      const [t1, c1] = HYPSO_STOPS[i];
      return out.set(c0).lerp(new THREE.Color(c1), (x - t0) / (t1 - t0));
    }
  }
  return out.set(HYPSO_STOPS[HYPSO_STOPS.length - 1][1]);
}

interface Props {
  mesh: MeshData;
  exaggeration: number;
  layer: Layer;
  path?: PathPoint[] | null;
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

export default function Terrain3D({ mesh, exaggeration, layer, path }: Props) {
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
    let queued = false;
    const render = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; renderer.render(scene, camera); });
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
    const c = new THREE.Color();
    for (let i = 0; i < mesh.heights.length; i++) {
      pos.setY(i, (mesh.heights[i] - mesh.min) * vs);
      if (layer === "elevation") hypso((mesh.heights[i] - mesh.min) / range, c);
      else c.set((SLOPE_CLASSES.find((q) => mesh.slopes[i] < q.max) ?? SLOPE_CLASSES[3]).color);
      col.setXYZ(i, c.r, c.g, c.b);
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
  }, [mesh, exaggeration, layer, path]);

  if (error) return <div className="notice notice-danger" role="alert">{error}</div>;
  return <div ref={host} style={{ width: "100%", height: 460, borderRadius: 8, overflow: "hidden", touchAction: "none" }}
              aria-label="Visor 3D del terreno: arrastre para rotar, rueda para acercar" />;
}
