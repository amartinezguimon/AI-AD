# VisionMetrics AI — System Design (the whole product surface)

> The blueprint for *who sees what*. The edge agent (Phases 1–2) is built; this
> doc defines the multi-tenant backend + dashboards (Phases 3–4) so the database
> schema is designed correctly **on day 1**. Decisions here drive the schema.
> Status: design only, nothing built yet.

## The 4 actors

1. **Platform staff (you + partners)** — the SaaS provider. Cross-tenant "god
   view": all client orgs, all stores, all devices. Fleet health, device
   provisioning (issue `device_id` + `api_key`), support/debug, billing (later).
2. **Client** — the company that pays (a shop or a chain). Sees **only its own
   org**, never another client's data. Has an **owner-admin** user who can
   **create additional users** (username/password) and grant them access — to
   the whole org or to a single store. Pure analytics consumer.
3. **Store-level user** — an additional user the owner created, scoped to one
   store (a sub-case of #2, not a separate system). Optional; exists only if the
   owner makes one.
4. **Edge device** — not a human. Authenticates with `device_id` + `api_key` and
   **pushes metrics only** (the Phase-2 uplink). Video never leaves the store.

## Multi-tenant data hierarchy

```
PLATFORM (staff)
  └── Org "Joyería Pérez"            ← the tenant boundary
        ├── User(owner, role=admin)
        ├── User(role=viewer, store_scope="Centro")   ← owner-created
        ├── Store "Centro"
        │     └── Device → Camera → metric buckets
        └── Store "Gran Vía"
              └── Device → Camera → metric buckets
  └── Org "Otra empresa"             ← can NEVER see Pérez's data
```

**Golden rule:** every query carries `org_id`. Tenant isolation is enforced at
the data layer, not just the UI.

### Tables (first cut — Phase 3 will refine)
- `orgs` (id, name, created_at, [reseller_id nullable — see Deferred])
- `users` (id, org_id, email, password_hash, role, store_id nullable, created_at)
  - `role` ∈ {`admin`, `viewer`}; `store_id` null = whole org, set = that store only.
- `stores` (id, org_id, name, address, timezone)
- `devices` (id=device_id, org_id, store_id, api_key_hash, agent_version, last_seen_at, status)
- `cameras` (id, device_id, fov_h_deg, ... per-camera calibration)
- `metric_buckets` (org_id, store_id, device_id, window_start, window_end,
  passersby, engaged, engagement_rate, total_attention_s,
  PRIMARY KEY(device_id, window_start))  ← matches `shared/schema.py`
- `heartbeats` (device_id, sent_at, fps, camera_ok, ...) — latest-wins liveness
- `platform_staff` (id, email, password_hash) — the cross-tenant admins (you)

## Roles & permissions
| Role | Scope | Can |
|---|---|---|
| Platform staff | All orgs | Everything; provision devices; impersonate for support |
| Org admin (owner) | One org | See all org stores; **create/manage users**; rename stores |
| Viewer | One org *or* one store | See metrics only, no user management |
| Device | One device | POST metrics + heartbeat (no read) |

## Screen inventory

### Platform back-office (you + partners) — Phase 4 minimal, grows later
- Clients list + drill into any org
- **Fleet health**: devices online/offline, fps, last-metric age, alert on stale
- **Provision device**: create org/store/device, generate + show api_key once
- (Later) billing/plans

### Client dashboard (the product you sell) — Phase 4
- Login → store selector + date range
- KPIs in business language: passersby, % engaged, avg attention, peak hours
- Trends: today / week / compare weeks / compare stores
- Chain view: all my stores at a glance + ranking
- **User management** (owner only): create user, set role + store scope

### Store (no separate app)
- A store is just a filter on the client dashboard. The physical store only runs
  the headless edge device. (A live "TV" view could come later if a client asks.)

## Phasing — what gets built when
| Piece | Phase | Note |
|---|---|---|
| Multi-tenant schema (orgs/stores/devices/users/roles) | **3** | Lock it down now |
| Device provisioning (device_id + api_key) | **3** | Needed for the 1st real store |
| Ingest API receiving Phase-2 buckets | **3** | The cloud side of `uplink.py` |
| Client dashboard (owner login, metrics, user mgmt) | **4** | The sellable surface |
| Platform back-office (minimal) | **4** | Can start as CLI/manual provisioning |
| Fleet-health panel | **4** | Devices online, fps, last metric |

## Deferred (door left open, not built)
- **Resellers/partners** managing multiple orgs — undecided (user: "ni idea aún").
  Kept addable via a nullable `reseller_id` on `orgs`; no reseller logic now.
- Billing/Stripe, self-service signup, OTA updates, fine-grained custom roles.

## Decisions on record
- Client access: owner-admin logs in; **owner can create extra users** (user/pass)
  scoped to the whole org or one store. (2026-06-09)
- Resellers: **not now**, but schema must not preclude them. (2026-06-09)
