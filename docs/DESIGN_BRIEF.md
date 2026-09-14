# Design brief

Everything a visual designer — or Claude Design — needs in order to produce a
layer that drops into this app without a component rewrite.

The app is already complete and usable. What it lacks is a visual identity: the
current CSS is deliberately plain. So this is a **re-skin**, not a redesign of
the flows. The flows are settled and validated in a real browser.

## The contract

Two rules keep a designed layer mergeable:

1. **Do not rename the class names.** Every component in `web/src/**` writes a
   fixed set of classes (listed below). A design that restyles `.card` and
   `.button` merges by replacing one file. A design that invents
   `.fitness-card-wrapper` needs every `.tsx` file edited by hand.
2. **Express colour, spacing and radius as the custom properties below.** They
   already exist in `web/src/styles.css`. Light and dark are both required —
   Android and iOS both hand the app a theme, and the app follows it.

Deliverable: **one replacement `web/src/styles.css`**, plus a list of any new
class names if a component genuinely needs new structure (then say which
component, and I wire it up here).

## Tokens

Defined three times in `web/src/styles.css` — on `:root` (light), under
`@media (prefers-color-scheme: dark)` and under `:root[data-theme='dark']`.
All three must be filled in.

| Token | Role |
| --- | --- |
| `--surface-0` | page background |
| `--surface-1` | raised surface: cards, header, tab bar |
| `--surface-2` | recessed surface: inputs, inactive tabs, table header |
| `--border` | hairlines and input outlines |
| `--text-primary` | body text and headings |
| `--text-secondary` | supporting text |
| `--text-muted` | timestamps, hints, disabled |
| `--accent` | primary action, links, the active tab |
| `--accent-ink` | text on `--accent` (contrast ≥ 4.5:1) |
| `--danger` | destructive action, errors, the deload marker |
| `--series-1` | chart line |
| `--grid` | chart gridlines |
| `--radius` | corner radius |
| `--gap` | base spacing step |
| `--page-max` | content column width (currently 720px) |

Add tokens freely (`--shadow-card`, `--radius-pill`, a type scale) — just define
them in all three blocks.

## Physical constraints

The end target is an **installed app on a phone**, so:

- **No browser chrome.** There is no URL bar and no browser back button. Every
  screen needs its own way back, and the tab bar is the only global navigation.
- **Safe areas.** `body` already pads by `env(safe-area-inset-*)`. The tab bar
  must keep clear of the home indicator; the header must clear the notch.
- **Thumb reach.** Minimum touch target 44px. The controls used mid-set — the
  set logger's counters, the rest timer — belong in the lower half of the
  screen.
- **One-handed, sweaty, in a gym.** High contrast, large numerals, and the
  primary action of each screen unmistakable.
- **Offline.** Writes queue when there is no signal, so the design needs a
  visible-but-calm "not synced yet" treatment (`.status-banner`).
- **Narrow first.** 360px wide is the design width. 720px is the cap; above
  that the column simply centres.

## Two apps

The product ships as two installable apps from one codebase:

- **the athlete app** — everything below except the operator screen;
- **the operator app** — the operator screen only, for the person running the
  service.

They can share one visual language, or the operator app can be deliberately
plainer. If they differ, say so and I will split the stylesheet.

## Screens

All of these exist and work today.

| Route | What it is | Primary action |
| --- | --- | --- |
| `/` | **Today** — the current session: each exercise with its target sets, reps and suggested load, a set logger per exercise, a rest timer between sets. The screen someone stares at for an hour in a gym. | log a set |
| `/programs/new` | **Program builder** — a short form (goal, days per week, minutes per session, equipment, experience), then a preview of the generated block before saving. | generate, then save |
| `/programs` | **Programs** — the saved blocks, with the week tabs of the active one. | open a program |
| `/exercises` | **Exercise catalogue** — search and facet filters (pattern, equipment, muscle, difficulty) over a large list, as a grid of cards with images. | open an exercise |
| `/exercises/:id` | **Exercise detail** — image and video demonstration, the movement's classification, and alternatives that fit the same slot. | swap it into the program |
| `/progress` | **Progress** — estimated one-rep-max over time per lift, weekly volume, body metrics. Charts. | pick a lift |
| `/activity` | **Activity** — notifications as a plain reverse-chronological list, unread marked. | open the linked item |
| `/settings` | **Settings** — account, language, theme, units, quiet hours, per-category notification switches, push permission, sign out. | grant notifications |
| `/sign-in`, `/sign-up` | **Sign in / register** — email and password, one panel each. Signed out, `/` shows the program builder instead, so someone can try the engine before registering. | submit |
| `/forgot-password`, `/reset-password` | **Password reset** — request a link, and set a new password from one. | submit |
| `/:handle` | **Profile** — `@username`, bio, counters, published workouts. Someone else's or one's own. Readable while signed out. | follow |
| `/operator` | **Operator** — the admin screen: compose an announcement and send it, switch whole notification categories on and off, see delivery counts. Admin accounts only; **this becomes the second app**. | send |

## Components and their states

Each needs every state drawn, not just the resting one.

- **`.button`** — variants `.primary`, `.subtle`, `.small`, `.wide`; states rest,
  pressed, focus-visible, disabled, busy.
- **`.card`, `.card.row`, `.card-head`, `.grid-card`** — the universal container.
  `.grid-card` carries an image.
- **`.panel`, `.panel.narrow`** — the form container (auth, builder, dialogs).
- **`.tab-bar`** — bottom navigation. Six items today (Today, Programs,
  Exercises, Activity, Progress, Settings), which is one or two too many for a
  360px screen: a proposal that moves something behind the Settings screen, or
  drops to icons with labels, is welcome. `.active` marks the current tab;
  `.tab-badge` and `.tab-with-badge` carry the unread count.
- **`.app-header`** — `.brand` plus `.auth-links`.
- **`.set-logger`, `.set-inputs`, `.counter`, `.logged-sets`** — the most-used
  control in the product. `.counter` is a stepper: −, a number, +. `.logged-sets`
  lists what is already done this session.
- **`.rest-timer`, `.rest-timer.done`, `.rest-time`** — a countdown that must be
  legible at arm's length, and a clearly different finished state.
- **`.suggestion`** — the engine's next-load advice, with a one-line reason.
- **`.plan-row`, `.week-tabs`, `.steps`** — the program preview. The deload week
  needs its own marking.
- **`.swap-panel`, `.swap-head`, `.swap-option`** — choosing a replacement
  exercise.
- **`.publish-dialog`** — publish a workout: caption, a preview of the share
  card, share or download.
- **`.exercise-grid`, `.exercise-list`, `.exercise-media`, `.play-hint`** — the
  catalogue. Images vary in aspect ratio and some are missing.
- **`.filters`, `.options`, `.option`, `.sliders`, `.inline-check`** — form
  controls: facet chips, radio groups, ranges, checkboxes.
- **`.chart`, `.axis-label`, `.series-line`, `.series-dot`, `.crosshair`,
  `.bar`** — inline SVG charts, not a library. Gridlines must recede.
- **`.stat-tiles`, `.stat-tile`, `.stat-value`** — the numbers on Progress and
  Profile.
- **`.profile-head`, `.bio`, `.badge`** — profile identity.
- **`.status-banner`** — offline, queued writes, and other transient truths.
- **`.callout`, `.error`** — inline explanation and inline failure.
- **`.data-table`, `.history-list`, `.plain-list`, `.pager`** — the operator
  screen and history.
- **`.quiet-hours`, `.profile-settings`, `.volume-row`, `.actions`,
  `.page-header`, `.muted`, `.small`, `.attribution`** — supporting pieces.
- **`.visually-hidden`** — must stay a screen-reader-only utility. Do not
  "style" it.

## Copy

All user-facing text comes from `web/src/lib/i18n.tsx` (English and Turkish).
Turkish strings run roughly 20–30% longer than English, so nothing may depend on
a label fitting on one line. Design with the Turkish text.

## Accessibility floor

- Text contrast ≥ 4.5:1 against the surface it sits on, in both themes.
- Never colour alone: the deload week, an unread notification and a failed sync
  each need a second signal.
- A visible `:focus-visible` ring on everything interactive — an Android user
  may have a keyboard or a switch.
- Respect `prefers-reduced-motion` for the rest timer and any transition.

## Bringing a design back

This session cannot reach a Claude Design project directly. Two routes work:

- In Claude Design, use **"Send to Claude Code Web"** — the project lands in the
  workspace and I merge from there;
- or paste the produced CSS into the conversation.
