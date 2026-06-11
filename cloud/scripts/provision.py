"""CLI to provision a tenant + device and print the device API key once.

Until the platform back-office UI exists (Phase 4), this is how we onboard a
store. Run against the configured database (VM_DATABASE_URL).

Examples:
    # full setup in one go
    python -m cloud.scripts.provision setup \
        --org "Joyeria Perez" --store "Centro" --device dev-centro-01

    # add pieces individually
    python -m cloud.scripts.provision org   --name "Joyeria Perez"
    python -m cloud.scripts.provision store --org-id <id> --name "Gran Via"
    python -m cloud.scripts.provision device --org-id <id> --store-id <id> --device-id dev-02
    python -m cloud.scripts.provision user  --org-id <id> --email a@b.com --password ***
"""

from __future__ import annotations

import argparse

from cloud.app.db import Base, SessionLocal, engine
from cloud.app import provisioning as prov


def _print_key(pd: prov.ProvisionedDevice) -> None:
    print("\n  Device provisioned. Put these in the store's device.yaml:")
    print(f"    device.device_id : {pd.device.id}")
    print(f"    uplink.api_key   : {pd.api_key}")
    print("  ^ The API key is shown ONCE and only its hash is stored. Save it now.\n")


def main() -> int:
    Base.metadata.create_all(bind=engine)
    ap = argparse.ArgumentParser(description="VisionMetrics provisioning")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="create org + store + device at once")
    s.add_argument("--org", required=True)
    s.add_argument("--store", required=True)
    s.add_argument("--device", required=True)

    o = sub.add_parser("org"); o.add_argument("--name", required=True)
    st = sub.add_parser("store")
    st.add_argument("--org-id", required=True); st.add_argument("--name", required=True)
    d = sub.add_parser("device")
    d.add_argument("--org-id", required=True); d.add_argument("--store-id", required=True)
    d.add_argument("--device-id", required=True)
    u = sub.add_parser("user")
    u.add_argument("--org-id", required=True); u.add_argument("--email", required=True)
    u.add_argument("--password", required=True)
    u.add_argument("--role", default="admin"); u.add_argument("--store-id", default=None)

    args = ap.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "setup":
            org = prov.create_org(db, args.org)
            store = prov.create_store(db, org.id, args.store)
            pd = prov.create_device(db, org.id, store.id, args.device)
            print(f"org_id={org.id}  store_id={store.id}")
            _print_key(pd)
        elif args.cmd == "org":
            print("org_id=" + prov.create_org(db, args.name).id)
        elif args.cmd == "store":
            print("store_id=" + prov.create_store(db, args.org_id, args.name).id)
        elif args.cmd == "device":
            _print_key(prov.create_device(db, args.org_id, args.store_id, args.device_id))
        elif args.cmd == "user":
            uid = prov.create_user(db, args.org_id, args.email, args.password,
                                   role=args.role, store_id=args.store_id).id
            print("user_id=" + uid)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
