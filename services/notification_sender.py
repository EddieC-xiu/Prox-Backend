# services/notification_sender.py
#
# Phase 4 — OneSignal Push Notification Sender
#
# Sends push notifications via OneSignal REST API.
# Respects per-user opt-in flags from notification_devices table.
#
# Required env vars:
#   ONESIGNAL_APP_ID       — OneSignal App ID (from dashboard)
#   ONESIGNAL_API_KEY      — OneSignal REST API key
#
# Payload structure matches what the Prox mobile app expects:
#   headings.en  — notification title
#   contents.en  — notification body (deal_reason)
#   data.deep_link — routes user to correct screen in app

import os
import logging
import requests
from config.supabase import get_supabase_client

logger = logging.getLogger(__name__)
sb     = get_supabase_client()

ONESIGNAL_APP_ID  = os.environ.get("ONESIGNAL_APP_ID", "")
ONESIGNAL_API_KEY = os.environ.get("ONESIGNAL_API_KEY", "")
ONESIGNAL_API_URL = "https://api.onesignal.com/notifications"


# ---------------------------------------------------------------------------
# Device lookup — batch preload for efficiency
# ---------------------------------------------------------------------------

def preload_notification_devices(user_ids: list[str]) -> dict[str, dict]:
    """
    Batch load all active notification devices for given users.
    Returns dict keyed by user_id -> device row.
    Only includes users with:
      - active = true
      - new_deals_alerts_enabled = true
      - provider_subscription_id not null
    """
    if not user_ids:
        return {}
    try:
        res = (
            sb.table("notification_devices")
            .select("user_id, provider_subscription_id, platform, time_zone, new_deals_alerts_enabled")
            .in_("user_id", user_ids)
            .eq("active", True)
            .eq("new_deals_alerts_enabled", True)
            .not_.is_("provider_subscription_id", "null")
            .execute()
        )
        devices = {}
        for row in (res.data or []):
            devices[str(row["user_id"])] = row
        logger.info(f"Loaded {len(devices)} active notification devices for {len(user_ids)} users")
        return devices
    except Exception as e:
        logger.error(f"Failed to preload notification devices: {e}")
        return {}


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_notification_payload(
    subscription_id: str,
    product:         str,
    retailer:        str,
    best_price:      float,
    savings_pct:     float,
    deal_reason:     str,
    trigger_type:    str = "drop",
) -> dict:
    """
    Build OneSignal API payload matching the Prox mobile app's expected format.

    Title format:  "Price drop at {Retailer}!" or "Great deal at {Retailer}!"
    Body format:   deal_reason (already formatted by build_deal_reason())
    Deep link:     /deals?source=new-deals-alert
    """
    # Title — matches Tom's notification style from screenshots
    retailer_display = retailer.title()
    if trigger_type == "drop":
        title = f"Price drop at {retailer_display}!"
    elif savings_pct >= 50:
        title = f"Big savings at {retailer_display}!"
    elif savings_pct >= 25:
        title = f"Great deal at {retailer_display}!"
    else:
        title = f"New deal at {retailer_display}"

    # Body — product name + price + savings context
    product_display = product.title()
    body = f"{product_display} for ${best_price:.2f} — {savings_pct:.0f}% below average across multiple retailers near you."

    return {
        "app_id":                    ONESIGNAL_APP_ID,
        "include_subscription_ids":  [subscription_id],
        "headings":                  {"en": title},
        "contents":                  {"en": body},
        "data": {
            "deep_link": "/deals?source=new-deals-alert",
        },
        "ios_sound":    "default",
        "android_sound": "default",
    }


# ---------------------------------------------------------------------------
# Send a single notification
# ---------------------------------------------------------------------------

def send_notification(
    subscription_id: str,
    product:         str,
    retailer:        str,
    best_price:      float,
    savings_pct:     float,
    deal_reason:     str,
    trigger_type:    str = "drop",
    dry_run:         bool = False,
) -> dict:
    """
    Send a push notification via OneSignal.

    Returns:
        {"success": True, "id": onesignal_notification_id}
        {"success": False, "error": reason}
    """
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        logger.warning("OneSignal credentials not set — skipping send")
        return {"success": False, "error": "missing credentials"}

    payload = build_notification_payload(
        subscription_id = subscription_id,
        product         = product,
        retailer        = retailer,
        best_price      = best_price,
        savings_pct     = savings_pct,
        deal_reason     = deal_reason,
        trigger_type    = trigger_type,
    )

    if dry_run:
        logger.info(f"[DRY RUN] Would send: {payload['headings']['en']} — {payload['contents']['en']}")
        return {"success": True, "dry_run": True, "payload": payload}

    try:
        response = requests.post(
            ONESIGNAL_API_URL,
            headers={
                "Authorization": f"Key {ONESIGNAL_API_KEY}",
                "Content-Type":  "application/json",
            },
            json    = payload,
            timeout = 10,
        )
        data = response.json()

        if response.status_code == 200 and data.get("id"):
            logger.info(f"[NOTIF] Sent to {subscription_id[:8]}... → {product} @ {retailer} (id: {data['id']})")
            return {"success": True, "id": data["id"]}
        else:
            logger.error(f"[NOTIF] OneSignal error: {data}")
            return {"success": False, "error": str(data)}

    except requests.exceptions.Timeout:
        logger.error("[NOTIF] OneSignal request timed out")
        return {"success": False, "error": "timeout"}
    except Exception as e:
        logger.error(f"[NOTIF] Failed to send: {e}")
        return {"success": False, "error": str(e)}