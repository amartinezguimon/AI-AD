"""Edge agent entry point — the unattended run loop that replaces main.py.

Runs headless by default: NO input() prompt, NO imshow window, no keyboard
controls. It loads device.yaml, builds the pipeline, opens the configured video
source (USB / RTSP / file), and processes frames until stopped. Designed to be
launched by an OS service manager (systemd / Windows service) and restarted on
failure.

Usage:
    python -m visionmetrics.edge.agent.service --config path/to/device.yaml
    python -m visionmetrics.edge.agent.service --config dev.yaml --debug   # on-site

The --debug flag opens an OpenCV preview window for installers; it is never used
in production.
"""

from __future__ import annotations

import argparse
import signal
import time

from .build import build_pipeline
from .capture import VideoSource
from .config import DeviceConfig

_PERF_INTERVAL_S = 5.0


def run(config_path: str, debug: bool = False) -> int:
    config = DeviceConfig.load(config_path)
    print(f"[agent] device={config.device.device_id} store='{config.device.store_name}'")

    print("[agent] loading models and building pipeline...")
    pipeline = build_pipeline(config)

    source = VideoSource.from_config(config.camera)
    if not source.open():
        print(f"[agent] ERROR: cannot open camera source {config.camera.source!r}")
        return 1
    print(f"[agent] camera open: {source.width}x{source.height} @ {source.fps:.0f}fps "
          f"(realtime={source.realtime})")

    stopping = {"flag": False}

    def _stop(*_):
        stopping["flag"] = True
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if debug:
        import cv2
        from . import viewer

    frame_idx = 0
    t0 = time.time()
    frames_since = 0
    print("[agent] running. Ctrl-C / SIGTERM to stop.")
    try:
        while not stopping["flag"]:
            ok, frame = source.read()
            if not ok or frame is None:
                if not source.realtime:      # file ended
                    break
                time.sleep(0.01)
                continue

            now = time.time()
            result = pipeline.process_frame(frame, frame_idx, now)
            frame_idx += 1
            frames_since += 1

            if debug:
                annotated = viewer.draw(frame, result, store_name=config.device.store_name,
                                        tracker=pipeline.tracker)
                cv2.imshow("VisionMetrics agent [debug]", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            elapsed = now - t0
            if elapsed >= _PERF_INTERVAL_S:
                print(f"[agent] {frames_since / elapsed:.1f} fps | "
                      f"passersby={pipeline.tracker.total_passersby} "
                      f"engaged={pipeline.tracker.total_engaged}")
                t0, frames_since = now, 0
    finally:
        source.release()
        if debug:
            import cv2
            cv2.destroyAllWindows()

    t = pipeline.tracker
    print(f"[agent] stopped. passersby={t.total_passersby} engaged={t.total_engaged} "
          f"attention={t.total_attention_s():.0f}s qr_triggers={t.qr_trigger_count}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="VisionMetrics edge agent")
    ap.add_argument("--config", required=True, help="path to device.yaml")
    ap.add_argument("--debug", action="store_true", help="show an OpenCV preview window")
    args = ap.parse_args()
    return run(args.config, debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
