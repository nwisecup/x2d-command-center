# X2D Command Center

**The app to have if you own a Bambu Lab X2D and run Home Assistant.**

One HACS integration + one bundled card = live control, hybrid local/cloud
connectivity, a heat-soak engine, a timelapse studio, a built-in filament
science database, a print queue, maintenance tracking and an advisor that
catches mistakes before they cost you a spool. It speaks the same local
protocol as the H2D and P/A series, but the X2D is what it's built around.

---

## Enrollment is the product demo

**Settings → Devices & services → Add integration → X2D Command Center**, then
pick one of three paths:

| Path | What you type | What you get |
|---|---|---|
| **Sign in with Bambu account** | email + emailed code | It fetches your printer list, each printer's **access code**, and — if the printer is on your LAN — its address too. Zero printer-screen transcription. Lands in **hybrid** mode. |
| **Scan my network** | the 8-char access code | Fully local from the first second. |
| **Manual** | IP, serial, code | For VLANs and stubborn networks. |

Install the integration *before* the printer arrives and the bundled card
shows a polished **ready-to-enroll landing screen** — when the X2D shows up,
you tap one button.

## Hybrid connectivity (new in 0.2)

Three modes, switchable live from a **Connection mode** select (or Options →
Connection):

- **LAN only** — nothing leaves your network. Full feature set.
- **Hybrid** — local first; if the LAN link drops (IP change, Wi-Fi blip,
  printer in cloud mode after a firmware toggle) telemetry and control fail
  over to Bambu's cloud MQTT automatically. Bambu Handy keeps working.
- **Cloud only** — no LAN needed at all (no camera/file-browser, which are
  LAN-borne). For the printer at the shop while HA lives at home.

Tokens expire after a few months; HA opens a re-auth flow that emails you a
fresh code. The header chip always shows which link is live.

## The filament science database (new in 0.2)

Seventeen materials — PLA (basic/matte/silk/CF), PETG (+CF), ABS, ASA, PC,
PA/Nylon, PAHT-CF, TPU 95A/85A, PVA, HIPS, PET-CF, Support W/G — each with
typical published values for: nozzle/bed/chamber temps, enclosure needs,
cooling, max volumetric speed, density, tensile strength, flexural modulus,
impact, heat deflection, shore hardness, hygroscopy, **drying temp & hours**,
AMS compatibility (AMS / AMS HT / external-only), abrasiveness & hardened-nozzle
requirements, minimum nozzle size, plate/glue advice, warp risk, real-world use
cases and the gotcha everyone learns the hard way.

Plus a **bonding matrix** for dual-nozzle work: any job's material pairing is
classified as *weld / laminate / break-away support / soluble support /
incompatible* — so "PETG interface under PLA" is recognized as the trick it is,
and "PLA + ABS" is flagged before the first layer goes down.

Tap any AMS tray in the card for the full spec sheet, with a one-tap
**Dry now** (AMS 2 Pro / HT drying at the database's temp/hours for that
material).

## The advisor (new in 0.2)

Cross-references everything live, like only a custom app can:

- **CF filament + stainless nozzle** → alert with a push notification (this is
  the classic $30 new-owner mistake).
- Filled filament + 0.2 mm nozzle → clog warning.
- ABS/ASA/PC starting with a **cold chamber** → "run a heat soak first".
- PLA in a **hot chamber** → heat-creep warning (the other classic).
- **Humid AMS + hygroscopic filament loaded** → drying spec + one-tap dry.
- Room below your startup floor → soak suggestion.
- Door open mid-ABS-print, low filament on the active spool, risky pairings.

All of it surfaces as a sensor (automatable), in the card's Insights tab, and
as actionable notifications for alerts.

## Print queue (new in 0.2)

Queue any number of printer-storage files (plate + options each). When a print
finishes you get a notification with a **Start next (N)** button — or flip
**auto-continue** and it starts 90 s after finish if the printer is idle
(you clear the bed, it keeps the plastic flowing). Queue survives restarts.

## Maintenance tracker (new in 0.2)

Real print-hours drive service intervals (rails/lead-screw lube, rods & belts,
nozzle & sock inspection, extruder gears, fans, carbon filter, AMS path, plate
wash) and **abrasive-filament grams** drive nozzle wear against
stainless/hardened budgets. Progress bars in Insights, binary sensor for
automations, one-tap "done".

## Everything from 0.1 is still here

90+ entities (dual-nozzle aware), heat-soak state machine with cold-weather
scaling and ready-by scheduling, HA-side frame-per-layer timelapse studio
(render/GIF/speed-up/rename/library/media-browser/casting), SD browser +
.3mf upload-and-print from the card, tap-to-skip objects on a bed map,
first-layers snapshot check, rich actionable notifications, per-job filament +
energy cost, pace-based ETA with drift, services for everything, diagnostics,
repairs, and the raw G-code/JSON consoles.

## Install

1. HACS → custom repository → this repo → *Integration* → install → restart.
2. Add the integration (see enrollment above).
3. Options → point it at your room sensor / heater plug / power plug / phones /
   prices. All optional — defaults are sane.
4. Add the card: `type: custom:x2d-command-card` (it registers itself).

**Installing before your printer arrives?** Home Assistant doesn't load an
integration until a device is added, so the card can't register yet. Add this
single line to `configuration.yaml`, restart, and refresh your browser — the
card then shows its ready-to-enroll landing screen:

```yaml
bambu_x2d:
```

You can leave the line in place after enrolling; it does nothing else.

For **control** on current Bambu firmware the printer needs LAN Only Mode +
Developer Mode (printer screen → Settings → Network); monitoring works without.
The cloud link covers monitoring + core job control per Bambu's own channel.

## Honesty box

- The X2D is new. Dual-nozzle parsing follows the H2D convention with
  single-nozzle fallbacks; calibration bit flags, `M141` chamber heating and
  AMS drying are community conventions — verify once, and the raw console +
  diagnostics file make differences easy to report.
- The Bambu cloud API is the community-documented one that Studio/Handy use;
  Bambu can change it. LAN mode never depends on it.
- Filament numbers are typical published values — batch, color and settings
  move them. They're for guidance and advisor logic, not datasheets.

## Development

Pure modules (`models`, `commands`, `soak`, `threemf`, `derived`, `discovery`,
`filament_db`, `advisor`, `maintenance`, `cloud` parsing) import without Home
Assistant and carry a 44-test suite: `pytest tests/`. CI runs hassfest, HACS
validation, ruff and the tests.

## License

MIT. Not affiliated with Bambu Lab. Protocol knowledge builds on the
OpenBambuAPI / ha-bambulab community's documentation — thank you.
