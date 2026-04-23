# Demo-Ready Upgrades — VisionMetrics AI

## Context
The project works end-to-end but the live demo lacks visual "wow" moments that land with a professor watching for 5–10 minutes. Key finding: `REWARD_THRESHOLD_S = 5.0` is tracked in state but **never drawn on screen** — the doc promises a "discount overlay after 5 seconds" that does not exist. Similarly, yaw/pitch are extracted every frame but never visualised — we are measuring gaze direction but not showing it.

Goal: add high-impact visual features in the CPU-friendly range (no new AI models, no GPU) so the live window feels interactive and cinematic, not just analytical.

Deadline: 2026-04-28. Performance budget: must not add meaningful load (current pipeline is already CPU-bound at ~3-5fps analysis).

---

## Files to Modify
- `src/inference/main.py` — all changes live here (drawing happens per-frame in the display section, lines ~700–740)
- Optionally `dashboard.html` — engagement tier KPI cards (only if time)

---

## Changes (ordered by impact per hour)

### 1. Visual Reward Overlay — ❌ DROPPED (operator screen not part of real product; dashboard + ad screen cover this)
The system already flips `state["counted_as_engaged"] = True` when someone crosses 5s. We just never draw anything.

**Location:** Inside the per-person loop in `main.py`, right after `cv2.putText` for the label (~line 690).

**Behavior:**
- When `state["counted_as_engaged"]` is True AND `now - state["reward_shown_at"] < 2.5s`, draw a banner.
- Banner: semi-transparent green rectangle above the person's bounding box with "REWARD UNLOCKED — 20% OFF".
- Use `cv2.addWeighted` for transparency (same pattern as HUD panel at line ~714).
- Fade-in via a simple scale factor: `scale = min(1.0, (now - reward_shown_at) / 0.3)`.
- Store `reward_shown_at` in the state dict at the moment we flip `counted_as_engaged`.

**Wow:** Person looks → ring fills → BANNER + reward. Instant, visceral proof the system reacts.

### 2. Engagement Duration Ring around each person (1 h)
Concentric arc around the person's head that fills up to 360° as they approach the 5-second threshold.

**Location:** Same drawing block as #1.

**Behavior:**
- Center: midpoint of top of bounding box, `cx = (x1+x2)//2`, `cy = y1`.
- Radius: `max(30, (x2-x1)//4)`.
- Draw `cv2.ellipse(frame, center, (r,r), 0, 0, progress_deg, color, 3)` where `progress_deg = min(360, state["total_engage_s"] / REWARD_THRESHOLD_S * 360)`.
- Color: green when engaged, gray when not. Full 360° + gold color once reward unlocked.

**Wow:** Real-time progress visible before the banner fires — creates anticipation.

### 3. Gaze Direction Arrow (1 h)
Yaw is already extracted every face-detect cycle (cached in `_face_cache`). Pitch too. Just draw an arrow.

**Location:** Inside the face-detection success branch in main.py (~line 604 where nose is drawn).

**Behavior:**
- Start point: the already-computed nose pixel `(nx, ny)`.
- End point: `(nx + int(-yaw * 120), ny + int(pitch * 120))` — scale factor chosen so yaw=0.5 gives a ~60px arrow.
- Use `cv2.arrowedLine(frame, start, end, (0, 255, 255), 2, tipLength=0.3)`.
- Only draw when face was freshly detected (not cached), so the arrow doesn't freeze on stale data — or always draw from cached values, simpler.

**Wow:** Instantly visible that the algorithm knows where each person is looking — proves the pipeline works on sight.

### 4. Engagement Tier Label (High / Medium / Low) ✅ COMPLETE
Binary "ENGAGED / AWAY" is less academic than tiers. The PyTorch probability is already computed.

**Location:** Label composition at ~line 685 where the existing label string is built.

**Behavior:**
- `tier = "HIGH" if engage_prob >= 0.80 else "MED" if engage_prob >= 0.50 else "LOW"`.
- Colour map: HIGH = bright green, MED = yellow, LOW = gray.
- Replace the current binary colour decision for `box_color` with the tier colour.
- HUD addition (bottom-left panel, ~line 720): add three rolling counters `High: X  Med: Y  Low: Z` summed over current `person_engagement`.

**Wow:** Shows the system does nuanced classification, not a binary cut-off. Easy talking point in the demo.

### 5. Sound Cue on Reward (30 min)
When `counted_as_engaged` flips True, play a short beep.

**Location:** Same place we set `reward_shown_at` in change #1.

**Behavior:**
- Use `winsound.Beep(880, 150)` on Windows (non-blocking if wrapped in a thread, but 150ms is fine to run inline).
- Import at top of file: `import winsound` (Windows only — guard with `try/except`).

**Wow:** Audible confirmation the system just converted a viewer into a counted-engaged customer. Great for live demo.

---

### 6. Customer-Facing Ad Screen — `ad_screen.html` ✅ COMPLETE
A fullscreen HTML page shown on a second screen that the *customer* actually sees — no tracking boxes, no debug numbers. Just a clean advertisement that reacts when someone engages.

**How it works:**
- main.py writes `qr_active_until` (Unix timestamp 10s in the future) into `data/live_stats.json` the moment a new person crosses the 5s threshold — but ONLY if `now > qr_active_until` (prevents re-triggering while QR is already shown).
- `ad_screen.html` polls every second. If `qr_active_until > now`, fades in the QR. Once expired, fades out.
- QR code: static invented PNG generated once (`data/qr_discount.png`) encoding a fake URL.

**main.py changes:**
- Add `_qr_active_until = 0.0` near state init.
- When `counted_as_engaged` flips True: `if now > _qr_active_until: _qr_active_until = now + 10.0` (one QR at a time, requires a fresh trigger).
- Add `"qr_active_until": _qr_active_until` to `write_live_stats` payload.

**ad_screen.html:**
- Fullscreen dark ad (CSS only, no image file needed for placeholder).
- QR overlay bottom-right, hidden by default, CSS fade-in on trigger.
- Live countdown label: "Scan for 20% OFF — Xs remaining".
- Run via same `python -m http.server 8080`.

**Demo flow:** Screen 1 = main.py (operator view), Screen 2 = ad_screen.html (customer view), Screen 3 = dashboard.html (manager view). Someone looks 5s → QR fades in on Screen 2 → ticks down → fades out.

**Wow:** This IS the product. A working retail AI ad system, not a prototype.

**Demo note:** To re-trigger the QR in the demo, step fully out of frame (new track ID), wait for the 10s cooldown to expire, then walk back in and look for 5s again.

---

## Optional / Stretch (skip if time is tight)

### 6. Engagement Heatmap (2 h)
Accumulate (yaw, pitch) samples into a 20x20 grid. At session end (or on key press 'H'), render as a JET colormap overlay and save to `data/heatmap.png`. Good for the report, less essential for live demo.

### 7. PDF Session Report (2 h)
At session end, generate a one-page PDF via `reportlab` with KPIs and a pie chart. Useful for the report's appendix.

---

## Out of Scope
- Demographic (age/gender) estimation — heuristics are flimsy, real ML models add CPU load. Skip.
- Threading rewrite — separate concern from demo polish; the user decided against it.
- Dashboard tier cards — nice but the dashboard is already rich; focus on the live window which is what the professor will watch.

---

## Verification
1. Run `python src/inference/main.py`.
2. Walk up, face the camera for 5+ seconds.
3. Expect to see: (a) ring around head fills green, (b) at 5s a banner pops up above you, (c) a beep plays, (d) box colour shifts to gold, (e) tier label shows HIGH.
4. Turn head away — yellow/gray tier, ring stops filling.
5. Walk off, walk back — new track ID, new ring, new reward possible.

## Estimated total effort
- Core (changes 1–5): **~5 hours**, all in `main.py`.
- Stretch (6–7): +4 hours if wanted for the report.
