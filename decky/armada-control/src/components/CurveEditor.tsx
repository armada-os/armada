import { DialogBody, DialogButton, Focusable, GamepadButton, ModalRoot, showModal } from "@decky/ui";
import { useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

type Pt = { t: number; pwm: number };

const WALL_T = 92, WALL_PWM = 255;      // owner: full 100% at the 92C wall
const STEP_T = 1, STEP_PWM = 3;         // 1C, ~1% per D-pad press
const VBW = 520, VBH = 300, L = 46, R = 508, TOP = 12, BOT = 262;
const PW = R - L, PH = BOT - TOP;

const clampN = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
const pctOf = (pwm: number) => Math.round((pwm / 255) * 100);

function parseCurve(s: string): Pt[] {
  const out = (s || "").split(",").map((x) => x.trim()).filter(Boolean)
    .map((seg) => { const [a, b] = seg.split(":"); return { t: Math.round(Number(a)), pwm: Math.round(Number(b)) }; })
    .filter((p) => Number.isFinite(p.t) && Number.isFinite(p.pwm))
    .sort((a, b) => a.t - b.t);
  return out.length >= 2 ? out : [{ t: 0, pwm: 0 }, { t: 92, pwm: 255 }];
}
const serialize = (pts: Pt[]) => pts.map((p) => `${p.t}:${p.pwm}`).join(",");

function pwmAt(pts: Pt[], temp: number): number {
  if (temp <= pts[0].t) return pts[0].pwm;
  if (temp >= pts[pts.length - 1].t) return pts[pts.length - 1].pwm;
  for (let i = 1; i < pts.length; i += 1) {
    if (temp <= pts[i].t) { const a = pts[i - 1], b = pts[i]; return a.pwm + (b.pwm - a.pwm) * ((temp - a.t) / (b.t - a.t)); }
  }
  return pts[pts.length - 1].pwm;
}
function validate(pts: Pt[]): string | null {
  if (pts.length < 2) return "need at least 2 points";
  for (let i = 0; i < pts.length; i += 1) {
    if (pts[i].t < 0 || pts[i].t > 100) return `temp ${pts[i].t} out of range`;
    if (pts[i].pwm < 0 || pts[i].pwm > 255) return `fan ${pctOf(pts[i].pwm)}% out of range`;
    if (i > 0 && pts[i].t <= pts[i - 1].t) return `temps not ascending at ${pts[i].t} C`;
    if (i > 0 && pts[i].pwm < pts[i - 1].pwm) return `fan drops at ${pts[i].t} C`;
  }
  if (pwmAt(pts, WALL_T) < WALL_PWM) return `must reach 100% by ${WALL_T} C`;
  return null;
}
function moved(pts: Pt[], i: number, t: number, pwm: number): Pt[] {
  const loT = i > 0 ? pts[i - 1].t + 1 : 0;
  const hiT = i < pts.length - 1 ? pts[i + 1].t - 1 : 100;
  const loP = i > 0 ? pts[i - 1].pwm : 0;
  const hiP = i < pts.length - 1 ? pts[i + 1].pwm : 255;
  const next = pts.slice();
  next[i] = { t: clampN(Math.round(t), loT, hiT), pwm: clampN(Math.round(pwm), loP, hiP) };
  return next;
}

const focusCss = `
  .armada-fan-col .DialogButton { min-width: 0 !important; width: 100% !important; min-height: 0 !important; height: auto !important; padding: 0 6px !important; }
  .armada-fan-col .DialogButton.gpfocus,
  .armada-fan-col .DialogButton:focus,
  .armada-fan-col .DialogButton:hover {
    background-color: rgba(255,255,255,0.14) !important;
    color: #ffffff !important; box-shadow: none !important; transform: none !important; filter: none !important;
  }
`;

// Canonical 10-point curves. The "Default" button restores the profile's curve to these.
const DEFAULT_CURVES: Record<string, string> = {
  fc_cabinboy: "0:0,64:8,68:16,71:34,74:56,78:92,82:132,85:162,88:192,92:255",
  fc_sailor: "0:0,64:16,68:32,71:56,74:80,78:116,82:152,85:176,88:200,92:255",
  fc_bosun: "0:0,57:8,61:16,66:46,70:72,74:104,79:144,83:176,88:208,92:255",
  fc_quartermaster: "0:0,53:8,58:22,63:52,68:82,72:112,77:152,82:182,87:211,92:255",
  fc_firstmate: "0:8,51:16,56:30,61:60,66:90,72:128,77:164,82:194,87:216,92:255",
  fc_captain: "0:24,51:32,56:52,61:76,66:106,72:150,77:180,82:204,87:216,92:255",
  fc_admiral: "0:32,51:48,56:68,61:92,66:128,72:166,77:192,82:212,87:224,92:255",
};

function CurveEditorModal({ profileLabel, initial, defaultCurve, onCommit, closeModal }: {
  profileLabel: string; initial: string; defaultCurve: string; onCommit: (curve: string) => void; closeModal?: () => void;
}) {
  const [points, setPoints] = useState<Pt[]>(() => parseCurve(initial));
  const [focus, setFocus] = useState(0);
  const [grabbed, setGrabbed] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragging = useRef(false);
  // Axis fixed on open, fitted to the data so EVERY point (incl. the t=0 floor) is on-screen.
  const axis = useRef<{ lo: number; hi: number } | null>(null);
  if (!axis.current) {
    const init = parseCurve(initial);
    axis.current = { lo: init[0].t, hi: Math.max(init[init.length - 1].t, init[0].t + 10) };
  }
  const T_LO = axis.current.lo, T_HI = axis.current.hi;
  // refs so Focusable button handlers never read stale state
  const focusRef = useRef(focus); focusRef.current = focus;
  const grabbedRef = useRef(grabbed); grabbedRef.current = grabbed;

  const X = (t: number) => L + ((t - T_LO) / (T_HI - T_LO)) * PW;
  const Y = (pwm: number) => TOP + (1 - pwm / 255) * PH;
  const f = Math.min(focus, points.length - 1);
  const err = validate(points);

  const toData = (clientX: number, clientY: number) => {
    const r = svgRef.current!.getBoundingClientRect();
    const sx = ((clientX - r.left) / r.width) * VBW;
    const sy = ((clientY - r.top) / r.height) * VBH;
    return {
      t: clampN(Math.round(T_LO + ((sx - L) / PW) * (T_HI - T_LO)), 0, 100),
      pwm: clampN(Math.round((1 - (sy - TOP) / PH) * 255), 0, 255),
      sx, sy,
    };
  };
  const nearest = (sx: number, sy: number) => {
    let best = -1, bd = 24;
    points.forEach((p, i) => { const d = Math.hypot(X(p.t) - sx, Y(p.pwm) - sy); if (d < bd) { bd = d; best = i; } });
    return best;
  };
  const onPointerDown = (e: ReactPointerEvent<SVGSVGElement>) => {
    e.preventDefault();
    const { sx, sy } = toData(e.clientX, e.clientY);
    const n = nearest(sx, sy);
    if (n >= 0) { setFocus(n); dragging.current = true; (e.currentTarget as Element).setPointerCapture?.(e.pointerId); }
  };
  const onPointerMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (!dragging.current) return;
    const { t, pwm } = toData(e.clientX, e.clientY);
    setPoints((pts) => moved(pts, Math.min(focusRef.current, pts.length - 1), t, pwm));
  };
  const onPointerUp = () => { dragging.current = false; };

  // Interactive per-point overlays: also drag by touch/cursor (setPointerCapture), so touch works
  // whether the finger lands on the SVG or on an overlay, and the overlays are real focusables.
  const odrag = useRef(-1);
  const overlayDown = (i: number) => (e: ReactPointerEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setFocus(i); odrag.current = i;
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  };
  const overlayMove = (i: number) => (e: ReactPointerEvent<HTMLDivElement>) => {
    if (odrag.current !== i) return;
    const { t, pwm } = toData(e.clientX, e.clientY);
    setPoints((pts) => moved(pts, Math.min(i, pts.length - 1), t, pwm));
  };
  const overlayUp = () => { odrag.current = -1; };

  const applyMove = (i: number, dt: number, dp: number) =>
    setPoints((pts) => { const j = Math.min(i, pts.length - 1); return moved(pts, j, pts[j].t + dt, pts[j].pwm + dp); });
  const selPrev = () => setFocus((v) => Math.max(0, v - 1));
  const selNext = () => setFocus((v) => Math.min(points.length - 1, v + 1));
  const addPoint = () => {
    const i = f < points.length - 1 ? f : f - 1;
    const a = points[i], b = points[i + 1];
    const nt = Math.round((a.t + b.t) / 2);
    setPoints((pts) => { const n = pts.slice(); n.splice(i + 1, 0, { t: nt, pwm: Math.round(pwmAt(pts, nt)) }); return n; });
    setFocus(i + 1); setGrabbed(false);
  };
  const removePoint = () => {
    if (points.length <= 2) return;
    setPoints((pts) => { const n = pts.slice(); n.splice(f, 1); return n; });
    setFocus((v) => Math.min(v, points.length - 2)); setGrabbed(false);
  };
  const save = () => { if (!err) { onCommit(serialize(points)); closeModal?.(); } };

  // Gamepad on a point-overlay Focusable: A grabs/releases; while grabbed the D-pad moves it.
  const onPointButton = (i: number) => (evt: any) => {
    const b = evt?.detail?.button;
    if (b === GamepadButton.OK) { evt?.preventDefault?.(); setFocus(i); setGrabbed((g) => !g); return; }
    if (!grabbedRef.current || focusRef.current !== i) return;
    if (b === GamepadButton.DIR_UP) { evt?.preventDefault?.(); applyMove(i, 0, STEP_PWM); }
    else if (b === GamepadButton.DIR_DOWN) { evt?.preventDefault?.(); applyMove(i, 0, -STEP_PWM); }
    else if (b === GamepadButton.DIR_LEFT) { evt?.preventDefault?.(); applyMove(i, -STEP_T, 0); }
    else if (b === GamepadButton.DIR_RIGHT) { evt?.preventDefault?.(); applyMove(i, STEP_T, 0); }
  };

  const xticks: number[] = [];
  for (let t = Math.ceil(T_LO / 20) * 20; t <= T_HI; t += 20) xticks.push(t);
  const gy = [0, 25, 50, 75, 100];
  const path = points.map((p, i) => `${i ? "L" : "M"}${X(p.t)} ${Y(p.pwm)}`).join(" ");
  const sel = points[f], topPct = Math.round(pwmAt(points, WALL_T) / 255 * 100);
  const grid = "rgba(255,255,255,0.12)", axc = "rgba(255,255,255,0.5)", line = err ? "#e24b4a" : "#3b8ade";
  const btn = { flex: "1 1 0", fontSize: "14px", width: "100%" };

  return (
    <ModalRoot onCancel={() => closeModal?.()}>
      <style>{focusCss}</style>
      <DialogBody>
        <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "12px" }}>
          <span style={{ fontSize: "18px", fontWeight: 600 }}>Fan curve</span>
          <span style={{ fontSize: "15px", opacity: 0.7 }}>{profileLabel}</span>
        </div>
        <div style={{ display: "flex", gap: "18px", alignItems: "stretch", width: "min(880px, 86vw)", maxWidth: "100%" }}>
          <div style={{ width: "116px", flexShrink: 0, display: "flex" }}>
            <Focusable className="armada-fan-col" style={{ display: "flex", flexDirection: "column", gap: "8px", flex: 1 }}>
              <DialogButton style={btn} onClick={selPrev}>Prev</DialogButton>
              <DialogButton style={btn} onClick={selNext}>Next</DialogButton>
              <DialogButton style={btn} onClick={() => applyMove(f, 0, STEP_PWM)}>+</DialogButton>
              <DialogButton style={btn} onClick={() => applyMove(f, 0, -STEP_PWM)}>&#8722;</DialogButton>
              <DialogButton style={btn} onClick={addPoint}>Add</DialogButton>
              <DialogButton style={btn} onClick={removePoint} disabled={points.length <= 2}>Remove</DialogButton>
              <DialogButton style={btn} onClick={() => { setPoints(parseCurve(defaultCurve)); setFocus(0); setGrabbed(false); }}>Default</DialogButton>
              <DialogButton style={btn} onClick={save} disabled={!!err}>Save</DialogButton>
            </Focusable>
          </div>
          <div style={{ flex: "1 1 auto", minWidth: 0 }}>
            <div style={{ position: "relative" }}>
              <svg
                ref={svgRef}
                viewBox={`0 0 ${VBW} ${VBH}`}
                style={{ width: "100%", height: "auto", display: "block", touchAction: "none", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.2)", borderRadius: "8px" }}
                onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
              >
                {xticks.map((t) => <line key={`gx${t}`} x1={X(t)} y1={TOP} x2={X(t)} y2={BOT} stroke={grid} strokeDasharray="2 4" />)}
                {xticks.map((t) => <text key={`tx${t}`} x={X(t)} y={BOT + 18} fill={axc} fontSize="12" textAnchor="middle">{t}</text>)}
                {gy.map((v) => <line key={`gy${v}`} x1={L} y1={TOP + (1 - v / 100) * PH} x2={R} y2={TOP + (1 - v / 100) * PH} stroke={grid} strokeDasharray="2 4" />)}
                {gy.map((v) => <text key={`ty${v}`} x={L - 8} y={TOP + (1 - v / 100) * PH + 4} fill={axc} fontSize="12" textAnchor="end">{v}%</text>)}
                <text x={R} y={BOT + 18} fill={axc} fontSize="12" textAnchor="end">C</text>
                <path d={path} fill="none" stroke={line} strokeWidth={2.5} strokeLinejoin="round" />
                {points.map((p, i) => {
                  if (i === f && grabbed) return <circle key={i} cx={X(p.t)} cy={Y(p.pwm)} r={12} fill="#2677d8" stroke="#fff" strokeWidth={3} />;
                  if (i === f) return (
                    <g key={i}>
                      <circle cx={X(p.t)} cy={Y(p.pwm)} r={12} fill="none" stroke="#7fb0ea" strokeWidth={2} />
                      <circle cx={X(p.t)} cy={Y(p.pwm)} r={7} fill="#16181d" stroke="#3b8ade" strokeWidth={1.5} />
                    </g>
                  );
                  return <circle key={i} cx={X(p.t)} cy={Y(p.pwm)} r={6} fill="#16181d" stroke="#3b8ade" strokeWidth={1.5} />;
                })}
              </svg>
              {/* invisible gamepad focus targets over each point; pointer-events off so touch-drag still hits the SVG */}
              {points.map((p, i) => (
                <Focusable
                  key={`fp${i}`}
                  style={{ position: "absolute", left: `${(X(p.t) / VBW) * 100}%`, top: `${(Y(p.pwm) / VBH) * 100}%`, width: "34px", height: "34px", transform: "translate(-50%, -50%)", borderRadius: "50%" }}
                  onGamepadFocus={() => setFocus(i)}
                  onButtonDown={onPointButton(i)}
                >
                  <div
                    style={{ width: "100%", height: "100%" }}
                    onPointerDown={overlayDown(i)}
                    onPointerMove={overlayMove(i)}
                    onPointerUp={overlayUp}
                    onPointerCancel={overlayUp}
                  />
                </Focusable>
              ))}
            </div>
          </div>
        </div>
        <div style={{ fontSize: "14px", opacity: 0.75, marginTop: "10px" }}>
          Point {f + 1} of {points.length} : {sel.t} C : {pctOf(sel.pwm)}% {grabbed ? "- grabbed" : "- highlighted"}
        </div>
        <div style={{ fontSize: "13px", minHeight: "18px", color: "#e0a030" }}>
          {err ? err : (topPct < 100 ? `reaches ${topPct}% at 92 C` : "")}
        </div>
      </DialogBody>
    </ModalRoot>
  );
}

export function openCurveEditor(opts: { profileLabel: string; curveName: string; initial: string; onCommit: (curve: string) => void; }) {
  if (!opts.curveName) return;
  const defaultCurve = DEFAULT_CURVES[opts.curveName] || opts.initial;
  showModal(<CurveEditorModal profileLabel={opts.profileLabel} initial={opts.initial} defaultCurve={defaultCurve} onCommit={opts.onCommit} />);
}
