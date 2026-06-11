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

from visionmetrics.shared.schema import SCHEMA_VERSION, Heartbeat

from .build import build_pipeline
from .capture import VideoSource
from .config import DeviceConfig
from .emitter import MetricEmitter, SessionCounters
from .uplink import Uplink

_PERF_INTERVAL_S = 5.0
AGENT_VERSION = "0.2.0"


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

    # Cloud uplink: emit per-window metric buckets, ship them on a background
    # thread with an offline SQLite buffer. Disabled (None) for local tests.
    emitter = MetricEmitter(config.device.device_id, config.device.store_id,
                            window_s=config.uplink.window_s)
    uplink = Uplink(config.uplink) if config.uplink.enabled else None
    if uplink is not None:
        uplink.start()
        print(f"[agent] uplink -> {config.uplink.base_url} "
              f"(buffer={config.uplink.buffer_path}, window={config.uplink.window_s:.0f}s)")

    def _counters() -> SessionCounters:
        t = pipeline.tracker
        return SessionCounters(
            passersby=t.total_passersby,
            engaged=t.total_engaged,
            total_attention_s=t.total_attention_s(),
            qr_triggers=t.qr_trigger_count,
        )

    def _dispatch(bucket) -> None:
        """Send a closed-window bucket to the cloud, or print it when uplink is off."""
        if uplink is not None:
            uplink.enqueue(bucket)
        else:
            print(f"[agent] bucket {bucket.window_start} pax={bucket.passersby} "
                  f"engaged={bucket.engaged} rate={bucket.engagement_rate}% "
                  f"attention={bucket.total_attention_s}s qr={bucket.qr_triggers}")

    last_now = 0.0
    last_heartbeat = 0.0

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
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 30   # bail (let the OS service restart) if truly stuck
    # For a recorded file we measure engagement in VIDEO time (frame / fps), not
    # wall-clock, so attention seconds are accurate regardless of processing speed.
    # A live camera uses the real clock.
    file_fps = source.fps or 30.0
    print("[agent] running. Ctrl-C / SIGTERM to stop.")
    try:
        while not stopping["flag"]:
            ok, frame = source.read()
            if not ok or frame is None:
                if not source.realtime:      # file ended
                    break
                time.sleep(0.01)
                continue

            now = time.time() if source.realtime else (frame_idx / file_fps)
            last_now = now
            # One bad frame (a MediaPipe hiccup, a corrupt image) must never take
            # down an unattended store device. Skip it and keep the session alive;
            # only give up if failures are relentless, so the OS service restarts.
            try:
                result = pipeline.process_frame(frame, frame_idx, now)
                consecutive_errors = 0
            except Exception as e:                       # noqa: BLE001 - last-resort guard
                consecutive_errors += 1
                print(f"[agent] frame {frame_idx} failed ({consecutive_errors}): {e}")
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print("[agent] too many consecutive frame errors; exiting for restart.")
                    return 1
                frame_idx += 1
                continue
            frame_idx += 1
            frames_since += 1

            # Close out any metric window that ended on this frame.
            for bucket in emitter.sample(_counters(), now):
                _dispatch(bucket)

            if debug:
                annotated = viewer.draw(frame, result, store_name=config.device.store_name,
                                        tracker=pipeline.tracker)
                cv2.imshow("VisionMetrics agent [debug]", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            elapsed = time.time() - t0           # wall-clock, for the processing-fps readout
            if elapsed >= _PERF_INTERVAL_S:
                fps = frames_since / elapsed
                print(f"[agent] {fps:.1f} fps | "
                      f"passersby={pipeline.tracker.total_passersby} "
                      f"engaged={pipeline.tracker.total_engaged}")
                # Liveness ping (best-effort, not buffered).
                if uplink is not None and (now - last_heartbeat) >= config.uplink.heartbeat_interval_s:
                    uplink.send_heartbeat(Heartbeat(
                        schema_version=SCHEMA_VERSION,
                        device_id=config.device.device_id,
                        store_id=config.device.store_id,
                        sent_at=time.time(),
                        agent_version=AGENT_VERSION,
                        camera_ok=True,
                        fps_display=round(fps, 1),
                        fps_analysis=round(fps, 1),
                        people_tracked=len(result.active_ids),
                    ))
                    last_heartbeat = now
                t0, frames_since = time.time(), 0
    finally:
        # Ship the final partial window, then stop the sender thread cleanly.
        final = emitter.flush(_counters(), last_now)
        if final is not None:
            _dispatch(final)
        if uplink is not None:
            remaining = uplink.buffer.count()
            uplink.stop()
            print(f"[agent] uplink stopped. {remaining} buckets still buffered.")
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
