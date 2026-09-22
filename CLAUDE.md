# Muhai — project state and next steps

**Muhai / MuhAI** — AI-powered accounting & finance OS for Turkish SMEs.
TEKNOFEST 2026 Financial Technologies. Team Nasimi BHOS · Team ID 821808 ·
Application ID 4579275 · Baku Higher Oil School.

Auto-loaded each session. Read it before starting; update it when facts change.
**Keep it lean — delete finished work rather than striking it through.**

Last verified: **2026-09-14**.

---

## 1. Layout

```
/
  backend/              FastAPI — data + compute API, Alembic migrations
  web/                  Vite + React 18 frontend (src/, own package.json)
  docs/                 DEPLOY.md — the VPS runbook
  db_backup/            pg_dump of an earlier development database
  docker-compose.yml            the deployable stack
  docker-compose.override.yml   development layer, applied automatically
  .env.example                  every setting the stack has
```

Repo: `https://github.com/UghurGambarov/MuhAI.git` (private), branch `master`.

## 2. Architecture

**Self-hosted, entirely in Docker.** Postgres is the system of record and
FastAPI owns both the data and the maths. No managed database, and nothing
third-party in the **data** path. The one exception, added 2026-09-19, is
**sign in with Google**: Firebase Auth identifies the person, the API verifies
the ID token offline and issues its own JWT. Google never becomes the session
and never sees a ledger. A VPS with Docker on it is still the whole
deployment target.

```
  Browser (React)
        │  nginx serves the bundle and proxies /api — one origin, no CORS
        ▼
  FastAPI  ──▶  PostgreSQL 15 (the only stateful service)
     │
     └── 2026 tax engine · Muhai Score · Prophet forecast · payroll
         Tesseract OCR · assistant (Gemini online, local BM25 offline)
```

Everything is synchronous. A Celery worker and a Redis broker were removed on
2026-09-13: the worker had executed **zero** tasks in its lifetime because
nothing ever dispatched to it, and server OCR — the only plausible candidate —
answers in ~0.3 s measured against `web/public/sample-invoice.png`. Redis
existed solely as that worker's broker. Recover both from commit `5c91e18` if
background work ever earns its keep.

Two halves to the API:

* **`/api/workspace`** — the data layer. Company profile plus five
  collections. The signed-in token *is* the company scope: every query is
  filtered by the caller's `company_id`, so no client can name another
  company's rows. That replaced the Firestore security rules with something
  the database enforces.
* **`/api/compute`** — stateless. Reads no table; a pure function of the
  snapshot posted to it plus today's date. Authenticates the caller but never
  resolves a company.

Sessions are JWTs signed by the API (`SECRET_KEY`), passwords bcrypt hashes.

### Data model

```
companies                 name, taxId, taxOffice, sector, city, legalForm,
                          currency, cashBalance, seeded, ownerUid
users                     email, hashed_password, display_name, role, company_id
company_invoices          number, vendor, direction, issueDate, dueDate,
                          paidDate, netAmount, vatAmount, amount, status,
                          category, source, ocrConfidence, needsReview
company_transactions      date, amount, type, category, description, vendor
company_products          name, sku, stock, minStock, unitPrice, monthlyUsage
company_employees         name, role, grossSalary, startDate, sgkNo
company_tax_obligations   type, name, period, dueDate, amount, status
```

The client still speaks **documents** — camelCase keys, ISO `YYYY-MM-DD` date
strings. `app/services/workspace.py` is the only place that maps documents to
rows, and it is covered by `tests/test_workspace_mapping.py`. Every table also
has an `extra` JSONB column that round-trips keys without a column of their
own, so an unrecognised field is preserved rather than dropped.

## 3. Running it

```bash
cp .env.example .env                  # then set SECRET_KEY: openssl rand -hex 32
docker compose up -d --build          # dev stack; API on :8000
npm --prefix web install && npm --prefix web run dev     # frontend :5173
curl http://localhost:8000/health     # -> {"status":"healthy"}
```

On Windows, `Muhai-Baslat.ps1` on the Desktop does all of that in one go:
it finds the repo, installs web dependencies if they are missing, writes a
`.env` with a generated `SECRET_KEY`, brings the stack up, waits for
`/health`, starts Vite in its own window and opens the browser. `-SkipBackend`
runs the web app alone, `-Build` serves a production build on :4173, `-Stop`
shuts down what it started.

A bare `docker compose` also applies `docker-compose.override.yml` — that is
the development layer (bind-mounts, `--reload`, Postgres on localhost,
web container disabled behind the `ui` profile). **Deploying uses the base file
alone**: `docker compose -f docker-compose.yml up -d --build`. Runbook in
`docs/DEPLOY.md`.

Tests (dev deps are deliberately absent from the runtime image, see N11):

```bash
docker compose exec backend pip install -r requirements-dev.txt
docker compose exec backend python -m pytest
```

Environment: root `.env` configures the whole stack and is the only file the
containers read. `backend/.env` is for running the API outside Docker;
`web/.env.local` for the Vite dev server. All three are git-ignored.

## 4. Current state

**Backend** — FastAPI 0.110, SQLAlchemy 2 (async), Pydantic v2, Alembic
through `0011_drop_legacy_tables`. **4 routers, 33 endpoints, 332 tests.**

- `/api/workspace/*` — company CRUD, generic collection CRUD, bulk insert,
  clear, and two atomic invoice↔ledger operations. **Six** collections now:
  the five business ones plus `vendorCategories`
- `/api/auth/*` — register (account + company in one transaction), login,
  **google**, me, company recovery, change password, delete account
- `/api/auth/google` takes a Firebase ID token and returns a normal Muhai
  session. `services/google_identity.py` verifies it against Google's
  published x509 certificates — no `firebase-admin`, no service-account key,
  nothing secret stored to accept a sign-in. It checks signature, `aud`
  (= `FIREBASE_PROJECT_ID`), `iss`, expiry, a non-empty `sub`, a verified
  email, **and that `sign_in_provider` is `google.com`**. That last check is
  load-bearing: the Firebase project is shared with another of Emin's apps,
  so without it an anonymous or password token from that project would mint a
  Muhai account. Accounts match on lowercased email, so Google and password
  sign-in land in the same account rather than forking it. A Google account
  arrives with **no company** — a Google profile has no tax id — so
  `ProtectedRoute` sends it to the existing setup screen, which is the one
  path that already existed for a company-less session. 13 tests in
  `tests/test_google_identity.py`, each negative case a token that would open
  an account if its check were dropped
- `/api/compute/{dashboard,muhai-score,forecast,tax-summary,payroll,classify,compliance,ocr,chat}`
- Compliance is the rule engine, not a table: duplicate invoices (by number,
  and by amount+date+vendor), KDV that matches no legal rate or exceeds the
  total, and tax deadlines inside their warning window. Stateless like the
  rest, so an alert disappears the moment the invoice is corrected — nothing
  to resolve, nothing to dedupe. `compliance_service.py` is unchanged; the
  compute route just feeds it the snapshot the dashboard already posts
- `/api/compute/classify` takes a `learned` map (vendor key → category) and
  prefers it over the keyword rules. The map is workspace data the browser
  posts with the request, which is how the classifier learns without the
  compute layer ever reading a table. Vendor keys are normalised by
  `expense_classifier.vendor_key()` — folded, punctuation **deleted** so
  "A.Ş." and "AŞ" are one vendor — and `web/src/lib/db.js` must keep applying
  the identical transform
- Assistant has two modes. **Online** it calls `gemini-2.5-flash` over the REST
  endpoint with stdlib `urllib` (override with `GEMINI_MODEL`). **Offline** —
  on any network, quota or key failure — it answers from a local BM25 knowledge
  base plus pre-answered questions and returns `source="offline"`, which the
  chat UI badges. Neither mode needs anything downloaded at runtime (N14)
- Prophet 1.1.5 forecasting on real data, moving-average fallback under 10
  points and on any Prophet failure
- Tesseract 5 + `tesseract-ocr-tur`; per-field confidence, threshold 0.7.
  Both paths run **Turkish only at PSM 6**, with the server path also
  preprocessing (grayscale, upscale under 1600 px, autocontrast, unsharp).
  See N18 — the settings matter far more than the model does. The browser-side
  OCR mode is fully vendored under `web/public/tessdata`, so **neither OCR
  path needs internet** (see N13)
- Muhai Score: 8 weighted categories. Tax engine: 2026 KDV / income / corporate
  / stopaj / SGK / stamp rates
- The user-scoped routes from before the workspace (`/api/invoices`,
  `/api/transactions`, …) and their ten tables were **deleted on 2026-09-13**
  — 14 routers, 10 models, 11 schemas, 4 services, dropped by migration `0011`.
  The API went from 60 endpoints to 21. `tests/test_api_smoke.py` asserts both
  that they are gone and that every mounted path belongs to one of the three
  live routers, so a stray import cannot quietly restore a second, unscoped
  data surface. **`bank_service.py` went with them** — the Turkish bank-CSV
  parser and fuzzy matcher. Recover it from commit `5cb59c0` when bank
  reconciliation gets built on the workspace

**Web frontend** — Vite + React 18, TR/EN, custom SVG charts. Bundle **524 kB (163 kB gzipped)** plus three lazy Firebase chunks
that only load when someone clicks "Google ile devam et".

The interface was restyled on 2026-09-19 into the **Repilay design
language** (`~/.claude/skills/repilay-design`), reverse-engineered from
repilay.com's shipped stylesheet — its `lp-*` landing tokens and its
`dash-*` console tokens, both of which ship in one global bundle there.
It replaces the near-monochrome console; `.claude/skills/monochrome-console`
still describes the dock, which was kept. What the new language means in
practice:

- **Cool slate surfaces, one warm accent.** `src/index.css` holds the whole
  token set for both themes. The page is `#f8fafc`, cards are white, wells
  are `#f5f7fa`, and text runs down a slate ramp. `--accent` (`#d64126`) is
  the primary action and `--brand-red` (`#ff4d2d`) the focus ring and the one
  figure that matters. **The accent stays rare** — two or three per screen.
  The legacy token names (`--bg`, `--ink`, `--rule`, `--ok`…) were kept and
  repointed, which is what moved 3,000 lines of component CSS at once; a
  stray `--brand` now resolves to the warm accent rather than to ink
- **The tray is the signature.** A tinted, faintly frosted container holding
  white cards at an **8px gutter**, tray radius 40, card radius 32. `.tray`,
  `.tray--console`, `.tray-card` in `index.css`. Cards go in trays; they do
  not float on the page with a border each. The hero figures, the module
  index, the assistant slab, the auth pair and `.mini-stats` are all trays
- **Radii nest downward.** Landing 40 → 32 → 24 → 16; console 12 → 10 → 8 →
  6 (`--r-tray`, `--r-panel`, `--r-card`, `--r-control`). Two adjacent layers
  never share a radius
- **Separation is an inset hairline, not a border plus a shadow.**
  `--shadow-1` is now `inset 0 0 0 1px`. Only trays, sheets and popovers cast
  anything real
- **Status is a tint pill with no outline and no dot.** Eight ink/tint pairs
  (`--tag-*-ink` / `--tag-*-tint`); the four legacy tones map onto green /
  amber / red / blue. The card behind a status stays white
- **Inputs are sunken and borderless** with a 2px `--brand-red` ring on
  focus-within — `.field__wrap`, `.topbar__search`, `.search-inline`,
  `.calc-input`. An outlined input with a blue focus ring is the generic
  default this replaces, and putting one back is the fastest way to lose the
  look
- **Cal Sans + Manrope + IBM Plex Mono**, three separate Google Fonts
  requests so a failure on one cannot take the others down. Cal Sans
  (`--display`) carries every heading, page title, figure and modal title —
  it is the whole personality, and it ships **one weight**, so never ask it
  for bold. Manrope carries body and UI at 14.5px. Inter and Geist Mono are
  gone
- **Labels are no longer uppercase.** A label is a plain 12px noun in
  `--text-tertiary` at −0.03em. Every letter-spaced caps micro-label in
  `pages.css` and `chat.css` was converted; caps read as a different product
- The dashboard still leads with **one figure, not four tiles**
  (`components/ui/Figures.jsx`), now set in Cal Sans at 42px. A row of four
  identical bordered cards, each with an icon in a rounded square and a
  floating sparkline, is still the most templated component on the web — do
  not put it back
- **The landing page is the roomy register**: an 80px section rhythm, a
  floating pill header that turns to glass on scroll, a centred hero whose
  claim carries a hand-drawn stroke that draws itself in, a product mock in a
  lifted tray whose foot dissolves under a stacked blur, one pastel
  (`--panel-iris`) illustration bed, and a single inverted navy slab
  (`--surface-inverted`, `#131c2e`) for the closing CTA
- **Light and dark are both first class.** `context/ThemeContext.jsx` owns the
  choice, writes `document.documentElement.dataset.theme`, persists to
  `muhai.theme`, and follows the OS until the user picks. Dark is built on the
  inverted navy rather than on black, so the two themes are one family, and
  the accent lifts a step (`#e05237`) because `#d64126` goes muddy on navy. An
  inline script in `index.html` paints the stored theme **before first paint**
  — without it a dark-mode user gets a white flash on every reload
- **Navigation is still the macOS-style magnifying dock**, kept on purpose:
  Repilay's own console uses a 58px icon rail, but a dock is the better answer
  at this width and the language transfers either way.
  `components/layout/Dock.jsx` + `styles/dock.css` are the portable primitive
  (framer-motion springs the tile width off pointer distance);
  `components/layout/AppDock.jsx` wires the eight tiles. The bar is glass held
  by a hairline inset ring, tiles rest on the sunken surface, and **the live
  tile is the accent** — the one place red appears in the chrome. Counts ride
  as slate badges, not red ones. `Sidebar.jsx` was **deleted**
- The topbar is 52px, blurred, carries identity + the Muhai Score chip +
  language + notifications + account, and **no navigation at all**. That is
  what gives the full width back to the work
- **The assistant owns the only gradient.** `.orb` in `index.css` and the
  `.chat-fab` are a drifting four-stop radial field (ember / iris / mauve /
  red) behind a masked well. It appears nowhere else
- Modals are **right-hand sheets** (`.modal-scrim` / `.modal`), now with a
  12px leading radius and a 200ms slide
- Own JWT auth against `/api/auth`, token in localStorage, two-step company
  sign-up, protected `/app`. **"Google ile devam et"** sits above the email
  form on `/login` and on step 1 of `/register`
  (`components/auth/GoogleButton.jsx`). The Firebase SDK is **lazy-loaded**:
  imported at the top level it cost ~34 kB gzipped on every page including the
  landing, so `lib/firebase.js` imports it inside the functions that use it
  and the redirect-return check is gated on a sessionStorage flag. Only auth
  is initialised — not Analytics, not the RTDB, both of which the console's
  config snippet offers. Signing out of Muhai signs out of Google too, or the
  next Google sign-in silently resumes the account just left. The auth screen is a centred tray holding two
  cards — a `--panel-steel` pitch panel and the form — replacing the
  full-height ink split. **There is no password reset**; Firebase used to send
  that mail and self-hosting would need an SMTP sender. Removed on purpose
  (2026-09-08); do not re-add it as a dead button
- `lib/client.js` is the only place that knows where the API is or how a
  request is authenticated. `lib/db.js` is the workspace client, `lib/api.js`
  the compute client
- Writes announce themselves through `db.js`'s `onChange`, and `DataContext`
  reloads (debounced). That replaced Firestore's push updates without making
  seven screens each remember to refetch
- **No mock data anywhere.** Every figure derives from the workspace + the
  compute API
- Falls back to local aggregation with a "hesaplama servisi çevrimdışı" badge
  when the API is unreachable — never a blank screen, never an invented number
- **Demo data is generated on the server, not in the browser.**
  `backend/app/services/demo_seed.py` holds the deterministic dataset and
  `backend/scripts/seed_demo.py` writes it into one demo account
  (`demo@muhai.app`). A real sign-up gets an empty workspace: nothing in
  `web/src` manufactures business figures any more
- **Charts kept their validated palette.** `--d1`…`--d8` are eight fixed
  categorical slots, assigned in order and never cycled; a ninth series folds
  into "other". They were re-checked against the dataviz skill's
  `validate_palette.js` before the restyle and were **not** re-toned for
  Repilay, because the order is the safety mechanism — re-ordering or
  re-colouring means re-running the validator against the new surfaces
  (`#ffffff` light, `#161f33` dark). `--trace` (single-series marks) is slate,
  not accent: spending the accent on every sparkline spends it on nothing
- The dashboard's **Uyum & Risk** card renders compliance alerts,
  severity-marked, with a link back to the offending invoice. Headings and
  severities are TR/EN; the detail sentence is Turkish in both, exactly like
  the assistant insight card above it
- Correcting an invoice's category teaches the classifier: the modal records
  vendor → category on save, the next invoice from that vendor is pre-filled,
  and the hint under the field says whether the answer came from the rules or
  from the company's own correction. Settings lists what has been learned and
  can forget one entry or all of them. Deliberately outside the `COLLECTIONS`
  object that "clear all data" iterates — learned knowledge is not demo data

**Mobile** — there is **no native client**; the Expo/React Native app was lost
and has not been rebuilt. The responsive web app is the mobile story. On
2026-09-14 every route was measured signed-in at **375 px** and again at
960 px: `document.body.scrollWidth` equals `clientWidth` on all ten, and
nothing hides behind the dock. The drawer sidebar is gone with the sidebar
itself — below 760 px the dock holds one tile size and scrolls sideways.

## 5. Open items

1. **Walk the signed-in screens on a real phone.** Widths were measured in a
   browser on 2026-09-14 and every route is clean at 375 px (N19), but nobody
   has put a thumb on them: touch targets, the sheets, long lists and the
   dock's sideways scroll are still untested on hardware. There is a test
   account in the dev database — `compliance-test@example.com` /
   `TestParola2026!`, seeded.
2. Grow the offline knowledge base. 20 passages cover the common ground; add a
   passage whenever a plausible question falls through to the default reply.
3. Build bank reconciliation on the workspace if it earns its place: import a
   statement CSV, match rows to invoices, show what did not match. The engine
   was written and then deleted with the rest of the legacy code — start from
   `git show 5cb59c0:backend/app/services/bank_service.py`, which already
   parses Turkish bank CSVs and fuzzy-matches on amount, date and vendor.

## 6. TEKNOFEST claims that do not match the code

| Claim | Reality | Action |
|---|---|---|
| Slide 4 says **Django** | Code is FastAPI, and staying that way | fix the deck |
| Speech says forecasting is **OLS regression** | Prophet, with a **moving-average** fallback | correct the wording |
| S2 **PostgreSQL 15 + Redis 7** | Redis is **gone** (2026-09-13). Postgres 15 is the only stateful service | drop Redis from the slide |
| S4 **Docker Compose, 4 services** | 3 — postgres, backend, web (plus a one-shot migrate job) | restate |
| S18 **"13 servis geliştirildi"** | 3 routers, 22 endpoints, 207 tests. 17 routers existed until the legacy half was deleted | say "22 uç nokta, 207 test" — a small, defensible surface beats a big one you cannot explain |
| S14 **Expo / React Native shipped** | Mobile **works** — the responsive web app runs on a phone (landing and auth verified at 375 px). What does not exist is a *native* Expo/React Native build. | keep the mobile capability in the pitch; word it as the web app on mobile, not a native app |
| S3/S16 **GİB / SGK / bank APIs** | **No external API call exists anywhere.** `bank_service.py` parses an uploaded CSV; the tax routes read a local 2026 calendar and rate table | say "bank statement import + local tax engine — works with no internet". It is true and a stronger claim |

The **UI copy** was corrected to match on 2026-09-14: the landing page no
longer claims a CNN model or an SGK integration, and the engine names
(Tesseract, Prophet, RAG, "backend vergi motoru") were taken out of the
screens. What the modules say now is what the code does. The deck still needs
the same pass.

True as written and needing no change: S1 (Python 3.11 / FastAPI / SQLAlchemy 2
/ Pydantic v2 — drop Celery if the slide names it), S5 (Tesseract 5 + Turkish pack, swappable `OcrEngine`),
S6 (Prophet), S7 (Gemini 2.5 Flash + RAG), S9 (per-field confidence, 0.7
threshold with a working review queue).

## 7. Conventions and gotchas

- **N1 — Avoid unnecessary rebuilds.** `docker-compose.yml` declares `image:`
  alongside `build:` so existing images are reused. Rebuild only when
  `requirements.txt`, `package.json` or a `Dockerfile` changes.
- **N1b — Pins in `requirements.txt` carry comments explaining why.** Do not
  bump `cmdstanpy` without re-running `tests/test_forecast_service.py`; that pin
  is what makes Prophet load at all.
- **N2 — The compose project name is pinned** (`name: muhai`) so `postgres_data`
  resolves to the existing `muhai_postgres_data`. Changing it orphans the DB.
- **N3 — `.dockerignore` excludes `tests/` and `.env`.** That is how they were
  lost once. Keep them in git. The dev override bind-mounts `./backend`, which
  is what puts the tests back inside the container.
- **N4 — Migrations belong to the one-shot `migrate` service**, not to app
  startup: several uvicorn workers would race for the same lock. The app's own
  startup hook still runs them when `RUN_MIGRATIONS_ON_STARTUP` is true, which
  is the default outside Docker and in the dev override.
- **N5 — The Bash tool cannot reach `D:`**; use PowerShell for that drive.
- **N6 — `useInView` / `whileInView` are not trustworthy.** Use
  `web/src/lib/useReveal.js` or `components/ui/Reveal.jsx` for any
  scroll-triggered animation. Every variant starts at `opacity: 0`, so a missed
  trigger renders a *blank section*, not merely an unanimated one.
- **N6b — Global type selectors beat inherited colour.** `index.css` has
  `h1, h2, h3, h4, h5 { color: var(--ink) }`, which out-specifies a `color`
  inherited from a dark parent. Any heading on a dark ground needs its colour
  set explicitly.
- **N6c — Colour has to mean something.** Before calling a screen done,
  cover every status pill and every chart with your thumb. If anything is
  still coloured, it is wrong — the interface chrome is greyscale and hue
  lives in the four status tones and the eight chart slots, nowhere else. Two decorative greens were found that way on 2026-09-14 — the
  "paid" and "net pay" totals in the summary strips — and made ink.
- **N6d — The dock is fixed, so pages have to make room.** `.page` reserves
  `--dock-clearance` (148px, 132px under 960px) as bottom padding. Anything
  that floats at the foot of the window — the assistant launcher, a toast —
  has to clear it too: below 760px the dock runs nearly the full width and
  becomes a horizontal scroll container, which is why `chat.css` lifts the
  launcher to `calc(var(--dock-clearance) - 44px)` there.
- **N7 — Screenshots of the Browser pane lie while the pane is hidden.** A
  hidden pane suspends `requestAnimationFrame` entirely, so every Framer Motion
  animation freezes at its `initial` state and the page looks blank. Front the
  tab, or check `getComputedStyle(...).opacity` in the DOM, before concluding
  anything is broken.
- **N8 — Recovering source from an image** (the trick that saved this project):
  `docker create --name tmp <image>` → `docker cp tmp:/app ./dest` → `docker rm tmp`.
- **N10 — `web/public/sample-invoice.png`** is a synthetic Turkish invoice for
  exercising OCR (net 12.350, KDV 2.470, total 14.820).
- **N11 — `pytest` is not in the runtime image.** Run
  `docker compose exec backend pip install -r requirements-dev.txt` once after
  any `docker compose down` or rebuild. The dev override runs the backend as
  root for exactly this reason — the image's own user cannot write to
  `/opt/venv`.
- **N12 — The API does not come back by itself after a reboot.** The containers
  restart, but only once the Docker *daemon* runs, and Docker Desktop's
  autostart is currently off. With Docker down the app shows "hesaplama servisi
  çevrimdışı" and the assistant drops to the keyword fallback.
- **N13 — Browser OCR assets are vendored, not fetched.** `web/public/tessdata`
  holds the worker, both LSTM wasm cores and the gzipped `tur` traineddata
  (English was dropped on 2026-09-13, see N18);
  `web/src/lib/ocr.js` passes `workerPath`, `corePath` and `langPath` so
  nothing is pulled from a CDN. `.gitattributes` marks the directory `-text`
  because the cores inline their wasm as base64 and a CRLF rewrite would
  corrupt them. If you upgrade `tesseract.js`, re-copy the worker and cores
  from `node_modules` — a version mismatch between worker and core fails at
  init, not at build.
- **N14 — The offline assistant's two numbers do different jobs.** In
  `rag.py`, `Hit.score` is raw BM25 and only orders results; `Hit.ratio` is
  idf-weighted query coverage in [0, 1] and is the only one safe to threshold,
  because BM25's magnitude moves with query length. Unknown words must stay in
  the coverage denominator — excluding them lets a mostly-nonsense question
  score 1.00 off one incidental term. Thresholds live in `chat_service.py`;
  re-measure against the corpus before changing them.
- **N14b — Fold anything you compare against folded text.** `rag.py`'s
  stopword list was written with Turkish diacritics while `tokenize()` folds
  first, so none of the diacritic words ever matched and they leaked through as
  content terms. The list is folded at definition time now. Same trap as F9.
- **N15 — Measure mobile layout, do not eyeball it.** Inject a representative
  element at a 375 px viewport and compare `scrollWidth` against the parent's
  `clientWidth`. That is how the two real overflows were found — a nine-column
  table at 684 px in a 341 px panel, and a five-button `.seg` at 389 px — while
  `.ocr-fields` and `.ocr-item`, which looked equally suspect in the CSS,
  measured clean. Wide content scrolls in its own container (`.tbl-scroll`,
  and `.seg` below 760 px); the page body must never scroll sideways.
- **N16 — In production the browser and the API share an origin.** nginx in the
  web container proxies `/api` to the backend, so `VITE_API_URL` is empty in a
  Docker build and CORS never applies. `BACKEND_CORS_ORIGINS` matters only for
  the Vite dev server, which is on a different port.

- **N17 — A grid item's `min-width: auto` beats its child's `overflow-x`.**
  `.dash-invoices` has a `.tbl-scroll` around its table, and the page still
  scrolled sideways on a phone: the item's automatic minimum is its table's
  min-content width, so the *track* grew to 602 px at a 375 px viewport and
  the scroll container never got the chance to scroll. `.dash-grid > * {
  min-width: 0 }` hands the overflow back to `.tbl-scroll`. The same block
  also had to re-collapse `grid-template-columns`, because the later
  `.dash-grid` rule in `pages.css` out-ordered the media query at the top of
  the file and the dashboard had been two-column on mobile all along.
  Measure with `document.body.scrollWidth` against `clientWidth` (N15).

- **N19 — A `nowrap` string in the topbar takes the whole page sideways.**
  The offline pill reads "Hesaplama servisi çevrimdişı" — about 200px that
  cannot wrap — and at a 375px viewport it stretched the topbar to 518px and
  the body with it. Below 760px `.topbar-meta .pill__text` is hidden and the
  glyph carries the state, with the sentence moved to the `title`. Measure the
  *topbar* as well as the page when checking a phone width (N15).

- **N18 — OCR: the config beats the model. Measured, 2026-09-13.** The
  temptation is to download a bigger traineddata file. Benchmarked on
  `sample-invoice.png` across four simulated capture conditions (clean, phone
  photo, dim light, photographed from too far), scoring four fields each:

  | change | score | speed |
  |---|---|---|
  | before — `tur+eng`, PSM 3, no preprocessing | 25/32 | 0.30 s |
  | `tessdata_best` tur (7.5 MB download) | 25/32 | ~40% slower |
  | drop `+eng` | 26/32 | faster |
  | **PSM 6 instead of PSM 3** | **28/32** | faster |

  `tessdata_best` was *not better even once*. PSM 3 runs full layout analysis
  and reads an invoice as two columns, so amounts land on different lines from
  their labels and `_extract_fields` — which matches per line — sees
  "Ara Toplam:" with no number. PSM 6 treats the page as one block. Running
  `tur+eng` makes Tesseract reconcile two dictionaries against Turkish text
  and loses fields rather than winning them. Preprocessing is what rescues a
  distant photo (1/4 fields → 3/4); it does nothing for a clean scan. If you
  do revisit the model, re-run the benchmark rather than assuming — and
  remember any model must be baked into the image, never fetched at runtime
  (N13).

The 2026-09-01 data-loss recovery is history now; `docs/RECOVERY.md` was
deleted in ca3f72f. The dump that survived it is `db_backup/`, and the
technique that saved the source is N8 above.
