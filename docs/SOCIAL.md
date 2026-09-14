# The social layer

Strava's shape, not Twitter's — and closer still to Spotify's. There is no
feed and no comment thread. You publish a workout, someone opens your profile
and sees it, and following you means being told when you publish again.

That shape is a deliberate choice, not an unfinished one. The unit of content
here is *a workout that already happened*, which the app produces anyway; no
one is ever asked to author a post. Most social features in fitness apps die
because they ask for writing and get silence.

## The two rules

Everything in `app/social.py` exists to enforce these:

1. **Nothing is public until it is published.** Not a session, not a profile.
   Publishing is per session and always a separate, deliberate act — never a
   side effect of finishing a workout. Following someone grants no access to
   anything they have not published.
2. **A handle is the only public identifier.** Email never appears in a
   profile response, so sharing a link cannot leak an address. An account
   without a handle has no profile at all, and is fully usable that way.

This matters legally as well as ethically: training history and body metrics
are health data, which both KVKK and the GDPR treat as a special category
needing explicit consent. Private-by-default with per-item opt-in is the
design that follows from that, so it is built in rather than bolted on.

## Shapes

| Table | What it holds |
| --- | --- |
| `users.username` / `username_display` | The public handle, lowercased for uniqueness plus the athlete's own capitalisation. Null until claimed. |
| `workout_sessions.published_at` / `caption` | When it went public, and the line the athlete wrote about it. Null means private. |
| `follows` | follower → followee. Decides who gets told; grants nothing. |
| `notifications` | Stored events. No foreign key to the session, so unpublishing leaves a dead link rather than deleting history or failing. |

## Endpoints

| Endpoint | Auth | Purpose |
| --- | --- | --- |
| `GET /v1/profiles/{username}` | optional | A public profile and its published workouts. |
| `GET /v1/profiles/{username}/sessions/{id}` | none | One published workout by its own link. |
| `POST /v1/workouts/sessions/{id}/publish` | required | Publish, or edit the caption. |
| `DELETE /v1/workouts/sessions/{id}/publish` | required | Take it back off. |
| `POST`/`DELETE /v1/profiles/{username}/follow` | required | Follow, unfollow. |
| `GET /v1/me/following`, `/v1/me/followers` | required | Who you follow, who follows you. |
| `GET /v1/notifications`, `/unread-count` | required | The activity list and its badge. |
| `POST /v1/notifications/read` | required | Mark all read. |

A profile is readable signed-out on purpose: a shared card has to lead
somewhere for a reader who does not have the app. An unpublished or
non-existent session both answer 404 — a 403 would confirm the session exists.

## The share card

`web/src/lib/shareCard.ts` draws a workout onto a canvas and hands it to the
phone's share sheet, falling back to a download where that is unavailable.

This is the piece that works on day one with nobody else signed up: the
audience is already on WhatsApp and Instagram, so the card goes to them rather
than asking them to come here first. The handle on the card is the way back.
It is 1080×1350 — the tallest ratio Instagram shows uncropped — and its
labels are translated, so it speaks the athlete's language.

## What is deliberately not here

- **Comments.** The technical work is small; the ongoing work is not. User
  text means harassment, spam and moderation, and fitness is a rough corner of
  the internet for that. Comments should not ship without report, block and
  delete shipping in the same change.
- **A feed.** A new app's feed is an empty room, which is worse than no feed.
  Profiles and notifications give the same value without the emptiness.
- **Push to a locked phone.** Notifications are stored and polled while the
  app is open. Real push is a smaller gap than email delivery, and a
  different kind: web push runs over the browser vendors' own push services,
  which are free and need no third-party account — only a VAPID key pair,
  generated once by the deployment. What is missing is work, not a decision:
  the key pair, a `push` listener in `web/public/sw.js` (there is none yet),
  a permission prompt, and a sender on the server. Note that iOS delivers web
  push only to a PWA the user has added to their home screen (16.4+).
