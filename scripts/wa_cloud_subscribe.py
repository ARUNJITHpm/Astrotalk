"""Check (and optionally fix) whether the app is subscribed to a WhatsApp
Business Account's webhooks — the step that makes INBOUND messages actually get
delivered to your ``/whatsapp/cloud-webhook`` endpoint.

Configuring the callback URL + verify token in the dashboard is NOT enough on its
own: the app must also be subscribed to the WABA (the ``subscribed_apps`` edge).
If that link is missing, Meta verifies your URL but never POSTs inbound messages
— exactly the "webhook verified but no messages arrive" symptom.

Reads the token from ``META_ACCESS_TOKEN`` (same as wa_cloud_send.py).

Usage (PowerShell):
  $env:META_ACCESS_TOKEN = "EAAT..."
  python scripts/wa_cloud_subscribe.py --waba-id 1543031797176918            # check only
  python scripts/wa_cloud_subscribe.py --waba-id 1543031797176918 --subscribe # check + subscribe
"""

import argparse
import asyncio
import os
import sys

import httpx


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--waba-id", required=True)
    ap.add_argument("--token", default=os.environ.get("META_ACCESS_TOKEN", ""))
    ap.add_argument("--api-version", default=os.environ.get("META_API_VERSION", "v21.0"))
    ap.add_argument("--subscribe", action="store_true",
                    help="POST to subscribe the app to this WABA if not already")
    args = ap.parse_args()

    if not args.token:
        print("ERROR: set META_ACCESS_TOKEN or pass --token.", file=sys.stderr)
        return 2

    version = args.api_version.strip("/")
    edge = f"https://graph.facebook.com/{version}/{args.waba_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {args.token}"}

    async with httpx.AsyncClient(timeout=15) as client:
        # 1. What apps are currently subscribed?
        resp = await client.get(edge, headers=headers)
        print(f"GET subscribed_apps -> HTTP {resp.status_code}")
        print(f"  {resp.text[:500]}")
        subscribed = []
        if resp.status_code == 200:
            subscribed = resp.json().get("data", [])
        if subscribed:
            print(f"  => {len(subscribed)} app(s) already subscribed to this WABA.")
        else:
            print("  => NO app subscribed to this WABA — inbound webhooks will NOT be delivered.")

        # 2. Subscribe if asked.
        if args.subscribe:
            print("POST subscribed_apps (subscribing this app)...")
            resp = await client.post(edge, headers=headers)
            print(f"  -> HTTP {resp.status_code}: {resp.text[:500]}")
            if resp.status_code == 200 and resp.json().get("success"):
                print("  ✅ subscribed. Inbound messages should now be delivered.")
            else:
                print("  ❌ subscribe failed — see body above.")
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
