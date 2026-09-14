"""Web push delivery.

Unlike email, this needs no third-party account: a push message travels over
the browser vendor's own service (Google's for Chrome, Mozilla's for Firefox,
Apple's for Safari), and all a server needs to be trusted by them is a VAPID
key pair it generates itself.

Generate one once and put it in the environment:

    python -m app.push generate-keys

Without keys configured the app still records notifications and shows them in
the list; only delivery to a closed app is missing. That is the same posture
as email: the feature degrades rather than breaks.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from dataclasses import dataclass

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

logger = logging.getLogger(__name__)

# Push services reject anything much larger; a notification is a headline and
# a line of text, so this is generous.
MAX_PAYLOAD_BYTES = 3000

# How long the push service should hold a message for a device that is
# offline. A day: a training reminder is worthless a week late.
DEFAULT_TTL_SECONDS = 86_400

# A subscription that fails this many times in a row is assumed dead even if
# the service never said so outright.
MAX_CONSECUTIVE_FAILURES = 5


@dataclass(frozen=True)
class VapidKeys:
    private_pem: bytes
    public_pem: bytes
    #: Raw public key, base64url — what the browser wants as
    #: `applicationServerKey` when subscribing.
    public_raw: str


def generate_keys() -> VapidKeys:
    """Create a fresh VAPID key pair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return VapidKeys(
        private_pem=private_pem,
        public_pem=public_pem,
        public_raw=base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"),
    )


def _configured_keys() -> tuple[bytes, bytes] | None:
    """The PEM key pair from the environment, or None if unconfigured.

    Stored base64-encoded because a PEM block spans several lines and most
    environment-variable plumbing mangles newlines.
    """
    private = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    public = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    if not private or not public:
        return None
    try:
        return base64.b64decode(private), base64.b64decode(public)
    except (ValueError, TypeError):
        logger.error("VAPID keys are set but are not valid base64; push is off")
        return None


def public_key() -> str | None:
    """The application server key a browser needs to subscribe."""
    raw = os.environ.get("VAPID_PUBLIC_KEY_RAW", "").strip()
    return raw or None


def is_configured() -> bool:
    return _configured_keys() is not None and public_key() is not None


def subscriber_contact() -> str:
    """The `mailto:` a push service can use to reach the operator.

    Required by the VAPID spec so a service has somewhere to complain; push
    services reject messages without one.
    """
    return os.environ.get("VAPID_SUBJECT", "").strip() or "admin@example.com"


class PushGone(Exception):
    """The subscription is permanently invalid and should be deleted."""


def send(endpoint: str, p256dh: str, auth: str, payload: dict,
         ttl: int = DEFAULT_TTL_SECONDS) -> None:
    """Deliver one notification.

    Raises :class:`PushGone` when the service says the subscription is dead
    (404/410), so the caller can prune it. Any other failure raises the
    underlying error — one broken device must not stop a fan-out, so callers
    handle that per subscription.
    """
    keys = _configured_keys()
    if keys is None:
        raise RuntimeError("push is not configured; set the VAPID keys")

    from webpush import WebPush, WebPushSubscription

    body = json.dumps(payload, ensure_ascii=False)
    if len(body.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("push payload is too large")

    private_pem, public_pem = keys
    pusher = WebPush(
        private_key=private_pem,
        public_key=public_pem,
        subscriber=subscriber_contact().removeprefix("mailto:"),
        ttl=ttl,
    )
    subscription = WebPushSubscription.model_validate({
        "endpoint": endpoint,
        "keys": {"p256dh": p256dh, "auth": auth},
    })
    message = pusher.get(message=body, subscription=subscription)

    response = httpx.post(endpoint, content=message.encrypted,
                          headers=dict(message.headers), timeout=10.0)
    if response.status_code in (404, 410):
        raise PushGone(f"subscription is gone: {response.status_code}")
    response.raise_for_status()


def _main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] != "generate-keys":
        print("usage: python -m app.push generate-keys", file=sys.stderr)
        return 2

    keys = generate_keys()
    print("# Add these to your .env, then restart the API.")
    print("# Keep VAPID_PRIVATE_KEY secret: it is what proves messages are")
    print("# from your server. Changing it invalidates every subscription,")
    print("# so generate it once and keep it.")
    print(f"VAPID_PRIVATE_KEY={base64.b64encode(keys.private_pem).decode()}")
    print(f"VAPID_PUBLIC_KEY={base64.b64encode(keys.public_pem).decode()}")
    print(f"VAPID_PUBLIC_KEY_RAW={keys.public_raw}")
    print("VAPID_SUBJECT=mailto:you@example.com")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
