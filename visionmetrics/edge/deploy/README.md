# Running the edge agent as a service

The agent (`visionmetrics.edge.agent.service`) is designed to run unattended and
restart on failure. Pick the path for your edge box's OS.

## Prerequisites (both OSes)
1. Repo deployed on the box, a Python venv created, `pip install -r requirements.txt`.
2. A real `device.yaml`: copy `visionmetrics/edge/config/device.example.yaml` to
   `visionmetrics/edge/config/device.yaml` and edit `device_id`, `store_id`,
   `camera.source`, and `camera.fov_h_deg` for this camera.
3. Models present (`yolov8n.pt`, `models/*.task`, `models/engagement_model.pth`).

---

## Linux (recommended for production — systemd)
The edge box is typically a small Linux mini-PC. Install with:

```bash
sudo bash visionmetrics/edge/deploy/install_linux.sh /opt/visionmetrics
```

This creates an unprivileged `visionmetrics` user, renders the unit file with
your paths, and enables it. Manage it with:

```bash
systemctl status visionmetrics-agent
systemctl restart visionmetrics-agent
journalctl -u visionmetrics-agent -f      # live logs
```

`Restart=always` brings the agent back after a crash or power cut; the start
limiter (5 failures / 60s) avoids a crash-loop on permanent errors.

---

## Windows (for a Windows mini-PC pilot — NSSM)
The simplest reliable way to run a Python script as a Windows service is
[NSSM](https://nssm.cc/). After installing NSSM:

```powershell
nssm install VisionMetricsAgent "C:\visionmetrics\venv\Scripts\python.exe" `
  "-m visionmetrics.edge.agent.service --config C:\visionmetrics\visionmetrics\edge\config\device.yaml"
nssm set VisionMetricsAgent AppDirectory "C:\visionmetrics"
nssm set VisionMetricsAgent AppStdout "C:\visionmetrics\data\agent.log"
nssm set VisionMetricsAgent AppStderr "C:\visionmetrics\data\agent.log"
nssm set VisionMetricsAgent Start SERVICE_AUTO_START
nssm start VisionMetricsAgent
```

NSSM restarts the process automatically if it exits. Manage it with
`nssm restart VisionMetricsAgent` / `nssm stop VisionMetricsAgent`, or
`services.msc`.

> No-install alternative: Task Scheduler → "At startup" → run the same
> `python -m ...` command. Less robust (no crash-restart), fine for a quick demo.

---

## Verifying before installing as a service
Always confirm it runs in the foreground first (with a clip or a real camera):

```bash
python -m visionmetrics.edge.agent.service --config <device.yaml> --debug
```

`--debug` opens a preview window. Drop it for the headless production run.
