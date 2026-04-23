import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from "remotion";

const DARK_BG = "#0a0e1a";
const BLUE = "#1f4e79";
const LIGHT_BLUE = "#4a9eda";
const ACCENT = "#00d4ff";
const GREEN = "#2ecc71";
const WHITE = "#f0f4ff";
const CARD_BG = "#111827";

function easeOut(t) {
  return 1 - Math.pow(1 - t, 3);
}

function fadeIn(frame, start, duration) {
  return interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
}

function slideUp(frame, start, duration) {
  const p = interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const eased = easeOut(p);
  return interpolate(eased, [0, 1], [40, 0]);
}

// ── Scene 1: Title (0-4s, frames 0-119) ─────────────────────────
function TitleScene({ frame }) {
  const logoOpacity = fadeIn(frame, 0, 25);
  const titleOpacity = fadeIn(frame, 20, 25);
  const subtitleOpacity = fadeIn(frame, 40, 25);
  const tagOpacity = fadeIn(frame, 60, 25);
  const titleY = slideUp(frame, 20, 30);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 40%, #0d1f3c 0%, ${DARK_BG} 70%)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Animated background grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `linear-gradient(rgba(0,212,255,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,212,255,0.04) 1px, transparent 1px)`,
          backgroundSize: "80px 80px",
          opacity: logoOpacity,
        }}
      />

      {/* Eye / camera icon */}
      <div
        style={{
          opacity: logoOpacity,
          marginBottom: 32,
          width: 90,
          height: 90,
          borderRadius: "50%",
          border: `3px solid ${ACCENT}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 0 40px ${ACCENT}44`,
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: "50%",
            background: ACCENT,
            boxShadow: `0 0 20px ${ACCENT}`,
          }}
        />
      </div>

      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 88,
          fontWeight: 800,
          color: WHITE,
          letterSpacing: "-2px",
          textAlign: "center",
        }}
      >
        Vision<span style={{ color: ACCENT }}>Metrics</span>{" "}
        <span style={{ color: LIGHT_BLUE }}>AI</span>
      </div>

      <div
        style={{
          opacity: subtitleOpacity,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 32,
          color: "#8899bb",
          marginTop: 16,
          letterSpacing: "1px",
          textAlign: "center",
        }}
      >
        Retail Engagement Analytics
      </div>

      <div
        style={{
          opacity: tagOpacity,
          marginTop: 40,
          padding: "10px 28px",
          border: `1px solid ${ACCENT}66`,
          borderRadius: 999,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 22,
          color: ACCENT,
          letterSpacing: "2px",
        }}
      >
        PRIVACY-PRESERVING · ON-DEVICE · REAL-TIME
      </div>
    </AbsoluteFill>
  );
}

// ── Scene 2: The Problem (frames 120-299, 4-10s) ─────────────────
function ProblemScene({ frame }) {
  const local = frame - 120;
  const headingO = fadeIn(local, 0, 20);
  const headingY = slideUp(local, 0, 25);
  const card1O = fadeIn(local, 20, 20);
  const card2O = fadeIn(local, 45, 20);
  const card3O = fadeIn(local, 70, 20);
  const arrowO = fadeIn(local, 100, 20);

  const cards = [
    { icon: "📺", title: "€58B spent", sub: "on physical retail ads in EU yearly" },
    { icon: "❓", title: "Zero data", sub: "no impressions, no CTR, no dwell time" },
    { icon: "👁", title: "Blind spots", sub: "stores can't tell who even looked" },
  ];

  return (
    <AbsoluteFill
      style={{
        background: DARK_BG,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 120px",
      }}
    >
      <div
        style={{
          opacity: headingO,
          transform: `translateY(${headingY}px)`,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 52,
          fontWeight: 700,
          color: WHITE,
          textAlign: "center",
          marginBottom: 16,
        }}
      >
        Physical advertising is{" "}
        <span style={{ color: "#e74c3c" }}>flying blind</span>
      </div>

      <div
        style={{
          opacity: headingO,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 26,
          color: "#667",
          marginBottom: 64,
          textAlign: "center",
        }}
      >
        Digital ads have clicks and conversions. In-store ads have nothing.
      </div>

      <div style={{ display: "flex", gap: 36 }}>
        {cards.map((c, i) => {
          const ops = [card1O, card2O, card3O];
          return (
            <div
              key={i}
              style={{
                opacity: ops[i],
                background: CARD_BG,
                border: `1px solid #1f2d45`,
                borderRadius: 20,
                padding: "44px 48px",
                flex: 1,
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 52, marginBottom: 20 }}>{c.icon}</div>
              <div
                style={{
                  fontFamily: "'Segoe UI', system-ui, sans-serif",
                  fontSize: 34,
                  fontWeight: 700,
                  color: WHITE,
                  marginBottom: 12,
                }}
              >
                {c.title}
              </div>
              <div
                style={{
                  fontFamily: "'Segoe UI', system-ui, sans-serif",
                  fontSize: 22,
                  color: "#556",
                }}
              >
                {c.sub}
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          opacity: arrowO,
          marginTop: 52,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 28,
          color: ACCENT,
          fontWeight: 600,
        }}
      >
        VisionMetrics closes the loop. ↓
      </div>
    </AbsoluteFill>
  );
}

// ── Scene 3: Pipeline (frames 300-539, 10-18s) ───────────────────
const PIPELINE_STAGES = [
  { label: "Camera", detail: "USB / phone\ncamera feed", color: "#e67e22" },
  { label: "YOLOv8n", detail: "Person detection\n& tracking by ID", color: LIGHT_BLUE },
  { label: "Head Crop\n4× Upscale", detail: "Enables detection\nat 4m+", color: LIGHT_BLUE },
  { label: "MediaPipe\nFace", detail: "Yaw · Pitch\n468 landmarks", color: LIGHT_BLUE },
  { label: "PyTorch\nMLP", detail: "3→16→8→1\nEngaged / Away", color: "#9b59b6" },
  { label: "Zone\nFilter", detail: "Continuous\nconfidence score", color: LIGHT_BLUE },
  { label: "Frame\nBuffer", detail: "3-frame temporal\nsmoothing", color: GREEN },
];

function PipelineScene({ frame }) {
  const local = frame - 300;
  const totalFrames = 240;
  const perStage = totalFrames / PIPELINE_STAGES.length;

  const headingO = fadeIn(local, 0, 20);

  return (
    <AbsoluteFill
      style={{
        background: DARK_BG,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 60px",
      }}
    >
      <div
        style={{
          opacity: headingO,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 44,
          fontWeight: 700,
          color: WHITE,
          marginBottom: 56,
          textAlign: "center",
        }}
      >
        7-Layer AI Pipeline
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 0,
          width: "100%",
          justifyContent: "center",
        }}
      >
        {PIPELINE_STAGES.map((stage, i) => {
          const appearFrame = i * perStage + 20;
          const stageO = fadeIn(local, appearFrame, 18);
          const stageY = slideUp(local, appearFrame, 20);
          const arrowO = i < PIPELINE_STAGES.length - 1
            ? fadeIn(local, appearFrame + 15, 15)
            : 0;

          return (
            <div
              key={i}
              style={{ display: "flex", alignItems: "center" }}
            >
              <div
                style={{
                  opacity: stageO,
                  transform: `translateY(${stageY}px)`,
                  background: CARD_BG,
                  border: `2px solid ${stage.color}`,
                  borderRadius: 14,
                  padding: "18px 16px",
                  width: 185,
                  textAlign: "center",
                  boxShadow: `0 0 18px ${stage.color}33`,
                }}
              >
                <div
                  style={{
                    fontFamily: "'Segoe UI', system-ui, sans-serif",
                    fontSize: 18,
                    fontWeight: 700,
                    color: stage.color,
                    whiteSpace: "pre-line",
                    lineHeight: 1.3,
                    marginBottom: 10,
                  }}
                >
                  {stage.label}
                </div>
                <div
                  style={{
                    fontFamily: "'Segoe UI', system-ui, sans-serif",
                    fontSize: 13,
                    color: "#778",
                    whiteSpace: "pre-line",
                    lineHeight: 1.4,
                  }}
                >
                  {stage.detail}
                </div>
              </div>

              {i < PIPELINE_STAGES.length - 1 && (
                <div
                  style={{
                    opacity: arrowO,
                    color: ACCENT,
                    fontSize: 28,
                    margin: "0 4px",
                    lineHeight: 1,
                  }}
                >
                  →
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom output row */}
      {(() => {
        const outputO = fadeIn(local, 200, 25);
        return (
          <div
            style={{
              opacity: outputO,
              display: "flex",
              gap: 32,
              marginTop: 48,
            }}
          >
            {[
              { label: "Operator HUD", color: GREEN },
              { label: "Customer Ad Screen", color: ACCENT },
              { label: "Manager Dashboard", color: "#f39c12" },
            ].map((out, i) => (
              <div
                key={i}
                style={{
                  padding: "12px 28px",
                  background: CARD_BG,
                  border: `1px solid ${out.color}88`,
                  borderRadius: 999,
                  fontFamily: "'Segoe UI', system-ui, sans-serif",
                  fontSize: 20,
                  color: out.color,
                  fontWeight: 600,
                }}
              >
                {out.label}
              </div>
            ))}
          </div>
        );
      })()}
    </AbsoluteFill>
  );
}

// ── Scene 4: Results (frames 540-749, 18-25s) ────────────────────
function ResultsScene({ frame }) {
  const local = frame - 540;

  const headingO = fadeIn(local, 0, 20);

  const metrics = [
    { value: "99.6%", label: "Test Accuracy", color: GREEN },
    { value: "0.999", label: "ROC-AUC", color: ACCENT },
    { value: "1,127", label: "Labelled Rows", color: LIGHT_BLUE },
    { value: "< 3ms", label: "Inference Time", color: "#f39c12" },
  ];

  const badges = [
    "No face recognition",
    "No images saved",
    "EU AI Act compliant",
    "Runs on CPU only",
  ];

  return (
    <AbsoluteFill
      style={{
        background: DARK_BG,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 120px",
      }}
    >
      <div
        style={{
          opacity: headingO,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 50,
          fontWeight: 700,
          color: WHITE,
          textAlign: "center",
          marginBottom: 60,
        }}
      >
        Performance Results
      </div>

      <div style={{ display: "flex", gap: 40, marginBottom: 56 }}>
        {metrics.map((m, i) => {
          const o = fadeIn(local, 20 + i * 20, 20);
          const y = slideUp(local, 20 + i * 20, 22);
          return (
            <div
              key={i}
              style={{
                opacity: o,
                transform: `translateY(${y}px)`,
                background: CARD_BG,
                border: `2px solid ${m.color}55`,
                borderRadius: 20,
                padding: "36px 48px",
                textAlign: "center",
                minWidth: 200,
                boxShadow: `0 0 24px ${m.color}22`,
              }}
            >
              <div
                style={{
                  fontFamily: "'Segoe UI', system-ui, sans-serif",
                  fontSize: 56,
                  fontWeight: 800,
                  color: m.color,
                  lineHeight: 1,
                }}
              >
                {m.value}
              </div>
              <div
                style={{
                  fontFamily: "'Segoe UI', system-ui, sans-serif",
                  fontSize: 20,
                  color: "#667",
                  marginTop: 12,
                }}
              >
                {m.label}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", justifyContent: "center" }}>
        {badges.map((b, i) => {
          const o = fadeIn(local, 100 + i * 15, 20);
          return (
            <div
              key={i}
              style={{
                opacity: o,
                padding: "10px 24px",
                background: "#0d1f10",
                border: `1px solid ${GREEN}44`,
                borderRadius: 999,
                fontFamily: "'Segoe UI', system-ui, sans-serif",
                fontSize: 20,
                color: GREEN,
              }}
            >
              ✓ {b}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

// ── Scene 5: Closing (frames 750-899, 25-30s) ────────────────────
function ClosingScene({ frame }) {
  const local = frame - 750;

  const bgO = fadeIn(local, 0, 30);
  const logoO = fadeIn(local, 15, 25);
  const tagO = fadeIn(local, 40, 25);
  const ctaO = fadeIn(local, 65, 25);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 50%, #0d1f3c 0%, ${DARK_BG} 70%)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity: bgO,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `linear-gradient(rgba(0,212,255,0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,212,255,0.05) 1px, transparent 1px)`,
          backgroundSize: "80px 80px",
        }}
      />

      <div
        style={{
          opacity: logoO,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 96,
          fontWeight: 800,
          color: WHITE,
          letterSpacing: "-2px",
          textAlign: "center",
        }}
      >
        Vision<span style={{ color: ACCENT }}>Metrics</span>{" "}
        <span style={{ color: LIGHT_BLUE }}>AI</span>
      </div>

      <div
        style={{
          opacity: tagO,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          fontSize: 30,
          color: "#8899bb",
          marginTop: 20,
          textAlign: "center",
        }}
      >
        Turning store windows into measurable media.
      </div>

      <div
        style={{
          opacity: ctaO,
          marginTop: 48,
          display: "flex",
          gap: 32,
        }}
      >
        {["YOLOv8n", "MediaPipe", "PyTorch", "OpenCV"].map((tech, i) => (
          <div
            key={i}
            style={{
              padding: "10px 26px",
              border: `1px solid ${ACCENT}44`,
              borderRadius: 999,
              fontFamily: "'Segoe UI', system-ui, sans-serif",
              fontSize: 22,
              color: ACCENT,
            }}
          >
            {tech}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
}

// ── Root composition ─────────────────────────────────────────────
export function VisionMetricsVideo() {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: DARK_BG }}>
      {frame < 120 && <TitleScene frame={frame} />}
      {frame >= 120 && frame < 300 && <ProblemScene frame={frame} />}
      {frame >= 300 && frame < 540 && <PipelineScene frame={frame} />}
      {frame >= 540 && frame < 750 && <ResultsScene frame={frame} />}
      {frame >= 750 && <ClosingScene frame={frame} />}
    </AbsoluteFill>
  );
}
