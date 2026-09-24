# BSR v3.7 fork — what changed and why

Fork of [MoonLighTingPY/odrive3.6_web_gui](https://github.com/MoonLighTingPY/odrive3.6_web_gui)
(all credit to Roman Fihel for the original project). Forked with the
author's direct permission (contacted via Telegram, September 2026); the
license terms for this fork are being worked out directly with him and are
not final — treat this as "shared with permission, license TBD", not as
open for further redistribution yet.

## Why fork this instead of the older WinForms GUI

Blue Smart Robotics started with a fork of Stijn Carelsbergh's WinForms GUI
(still in this project's firmware repo, `community-gui-winforms/`, CC
BY-NC-SA 4.0) before this one. This web GUI's mock-device support, config
wizard, and Inspector made it a better fit once its author gave permission
to fork it — the WinForms fork is kept as a lighter-weight fallback.

## What was added

Everything below adds new properties/enum values on top of the existing
0.5.x reference (`frontend/src/utils/odriveApiReference05x.json`) — nothing
existing was removed or renamed. Concretely:

1. **PWRGD monitoring** — `axis{n}.motor.config.enable_pwrgd_check` (bool).
   Fault the axis if the DRV8301 gate driver's PWRGD line drops while armed.
   Exposed in the Config Wizard's Motor step, "BSR v3.7" group.

2. **MIT-mode (Cheetah-style direct CAN joint control)** — 12 new config
   fields under `axis{n}.config.can.*` (`enable_mit`, `mit_can_id`,
   `mit_reply_can_id`, and the 8 `mit_{pos,vel,kp,kd,torque}_{min,max}` range
   fields used to decode/encode CAN command frames), plus a new
   `INPUT_MODE_MIT` (value 9) enum member on `ODrive.Controller.InputMode`.
   Exposed in the Config Wizard's Interface step, "BSR v3.7: MIT-mode CAN
   Control" group (essentials) and "BSR v3.7: MIT-mode Ranges" (advanced).

3. **MIT-mode live setpoints** — `axis{n}.controller.{mit_pos_setpoint,
   mit_vel_setpoint, mit_kp, mit_kd, mit_torque_ff}` (float, read/write,
   runtime only — not persisted config). Not given a bespoke panel; browse/
   edit them via the Inspector tab like any other live property, or through
   the Command Console (`w axis1.controller.mit_pos_setpoint 0.5`).

4. **CAN bus health telemetry** — `can.tx_error_count`, `can.rx_error_count`,
   `can.is_bus_off` (new fields on the top-level `can` singleton), read from
   the STM32 bxCAN peripheral's ESR register by the firmware. The
   `DUPLICATE_CAN_IDS` CAN-error flag this pairs with already existed in the
   upstream reference — nothing to add there.

5. **Firmware identity** — the 0.5.x mock now reports revision `5`
   (`fw_version_revision`) instead of the placeholder `6`, since BSR v3.7 is
   built on upstream `fw-v0.5.5`. Purely cosmetic: revision was never
   validated anywhere in the app (see below).

## Files touched

- `frontend/src/utils/odriveApiReference05x.json` — the 24 new property/enum
  entries (source of truth for the Inspector, Presets, and mock seeding).
  Applied via a small idempotent script (kept out of the repo; see git log)
  rather than hand-edited, to avoid formatting drift.
- `frontend/src/utils/configSchema.js` — Config Wizard groups for the new
  fields (Motor step + Interface step).
- `frontend/src/utils/configEnums.js` — friendly label for `INPUT_MODE_MIT`.
- `frontend/src/utils/odriveErrors.js` — description for `DUPLICATE_CAN_IDS`.
- `backend/app/mock_odrive.py` — realistic default values for the new fields
  (mirrors a typical E-dolly layout: axis0 = wheel, axis1 = damper running
  MIT-mode with CAN IDs 0x410/0x411), and the revision-5 fix above.

## A note on genuine-hardware checks (there aren't any)

Like the WinForms GUI before it, this project has no ODrive
genuine-hardware/OTP check to bypass — it talks to any device that speaks
the ODrive USB/serial protocol (real ODrive, a clone, or a BSR board) the
same way. That's unrelated to, and doesn't interact with, the separate
firmware lineage lock that exists only in the signed firmware BSR's
commercial E-dolly/Khepri units ship with (see the firmware repo's
`Firmware/docs/FIRMWARE_LINEAGE_BSR.md`) — that lock exists so those units'
torque/speed safety limits can't be removed by reflashing them with this
open firmware, and has nothing to do with this GUI.

## What was NOT changed / not verified further

- No new dedicated CAN-health or MIT-mode dashboard panel was built — the
  generic Inspector already exposes every new field once it's in the JSON
  reference (confirmed working, see below). A bespoke panel is a reasonable
  follow-up if the generic Inspector view proves too clunky in practice.
- The properties/enum additions were placed directly into the shared 0.5.x
  reference rather than split into a separate "BSR" firmware line. This
  means a genuine unmodified ODrive 0.5.x board connected to this build will
  show read errors (not crashes — every read/write is already individually
  try/excepted in `backend/app/telemetry.py`) for the BSR-only paths. Given
  this fork's purpose is specifically BSR v3.7 hardware, that tradeoff was
  chosen over the added complexity of a fully separate firmware-line
  variant (see git log for the alternative considered).

## Verification performed

Unlike the WinForms fork (blocked from compiling in that environment by
network policy), this was verified end-to-end in a normal environment with
working PyPI/npm access:

- Backend: instantiated `MockODrive` directly and confirmed every new path
  reads/writes correctly (`get_attr_value`/`set_attr_value`).
- Backend: ran the real Flask server in mock mode (`ODRIVE_MOCK=1
  ODRIVE_MOCK_FW=5`), confirmed `/api/devices` reports `fw_version: "0.5.5"`,
  confirmed `/api/devices/<serial>/api-metadata` serves all 24 new entries,
  and exercised the actual WebSocket read/write protocol
  (`/api/devices/<serial>/telemetry`) against the new paths.
- Frontend: `npm run build` (production Vite build) succeeds; `npx vitest
  run` — all 40 existing tests still pass, 0 regressions; `npx eslint` on
  every file touched — no errors.
