# training/ — collecting data and (re)training the engagement model

The model is a tiny MLP: **(yaw, pitch, distance) → P(looking)**. It is defined
once in `edge/agent/classifier.py` and reused here, so training and the live agent
can never drift apart.

## Honest note — why collect glasses / caps / distances if the model only sees 3 numbers?
The classifier never *sees* glasses or a cap. But those conditions change the
**distribution and noise** of the three numbers: glasses confuse the eye/cheekbone
landmarks, a cap shifts the forehead/top landmark, far faces are noisier all round.
So collecting them teaches the classifier the realistic spread it must be robust to,
and lets us **measure accuracy per condition** (not just on easy close-up faces).
This is the right next step; the bigger long-term lever (eye-gaze) is in `ROADMAP.md`.

## The workflow (who does what)

**Hector — collect (on the camera). No git, no GitHub.** Download the repo once and
run the collector. Record everyone in a SINGLE run; as different people walk up,
press **G** to mark glasses and **H** to mark a cap/hat — the on-screen label updates
and every captured row is tagged. Walk from near to far so all distances fill up:

```bash
python -m visionmetrics.training.collect --collector hector
# L = mark LOOKING (you decide)   A = mark AWAY   T = continuous capture on/off
# M = switch the continuous label  G = cycle gafas  H = cycle gorra  Q = quit + save
```

When he quits, the tool prints the **full path of the one file** it saved. Hector
just **sends that file to you by WhatsApp or email** — nothing else.

**You — merge + retrain (you own the code).** Drop the file(s) he sends into
`data/raw_sessions/`, then:

```bash
python -m visionmetrics.training.build_dataset   # merge sessions -> data/engagement_dataset.csv + coverage report
python -m visionmetrics.training.train           # retrain -> models/engagement_model.pth + metrics
```

`build_dataset` prints a **coverage report** (looking/away counts per distance tier
and per condition) and flags where you're thin — i.e. exactly what to collect next.
`train` prints overall accuracy **and a per-condition / per-distance breakdown**, and
writes `models/engagement_metrics.json` so you can compare runs over time. Commit the
new `models/engagement_model.pth` to ship it to the edge boxes.

## Tips for a strong dataset
- **Balance** looking vs away, and cover each distance tier (near / mid / far / very-far).
- **Tag as you go**: press G/H to set glasses/cap for whoever is in front right now.
- **Diversity** beats volume: several people, glasses/caps, lighting, angles — including
  the off-axis/corner camera position real stores use.
- Keep an **independent eval session** you never train on, to measure honest generalisation
  (`train --data <that file>` to score, or keep it out of `raw_sessions/`).
