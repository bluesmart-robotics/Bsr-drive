# Community GUI (Windows) — BSR v3.7 fork

A Windows desktop configuration GUI for boards running the **BSR v3.7**
open-source firmware fork (the public design in this repository — not the
locked-down firmware shipped on commercial E-dolly / Khepri units, see
below). It talks to the board over plain serial using ODrive's ASCII
protocol (`w <path> <value>` / `r <path>`), the same protocol
`odrivetool`'s low-level shell uses.

This is a fork of [Stijn Carelsbergh's ODrive V3 GUI](https://github.com/stijnsprojects/ODrive-V3-GUI),
used and redistributed here under its
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
license: **Attribution, NonCommercial, ShareAlike**. Per that license:

- All credit for the original design, layout and protocol work goes to
  Stijn Carelsbergh / Stijns Projects. See his
  [GitHub](https://github.com/stijnsprojects/ODrive-V3-GUI) and
  [YouTube video](https://www.youtube.com/watch?v=tPq89fzb6Mw).
- This fork is distributed free of charge, for the community, same as the
  original — not sold or bundled as part of a paid product. If that ever
  changes, the NonCommercial term means BSR would need a separate
  arrangement with the original author first.
- Under ShareAlike, this fork (and any further fork of it) stays under
  the same CC BY-NC-SA 4.0 license — see `LICENSE.md`.

## What changed vs. the original

- Support for everything added in the BSR v3.7 open-source firmware fork:
  - PWRGD monitoring enable/disable (`{axis}.motor.config.enable_pwrgd_check`)
  - MIT-mode (Cheetah-style) direct CAN joint control: full config panel
    (CAN IDs, position/velocity/gain/torque ranges) and a live setpoint
    panel (`{axis}.controller.mit_pos_setpoint` etc.)
  - CAN bus health telemetry (`can.tx_error_count`, `can.rx_error_count`,
    `can.is_bus_off`) and the new `DUPLICATE_CAN_IDS` error flag
  - Recognizes firmware revision 5 (this project is built on upstream
    fw-v0.5.5) instead of only 6/0
- Fixed a few stale values in the original that didn't match any real
  ODrive firmware: the control-mode dropdown had an invalid 5th value,
  and the axis-error list was missing `MOTOR_FAILED`,
  `SENSORLESS_ESTIMATOR_FAILED`, `ENCODER_FAILED` and `CONTROLLER_FAILED`.
- **Demo mode**: a checkbox that simulates a BSR v3.7 board entirely in
  memory (see `Transport.cs`), so you can click through every panel —
  including the new BSR ones — with no board attached. Nothing behind it
  is a real motor, encoder or CAN bus; values you write are just held for
  the session. This does not require, use, or bypass any hardware
  identity/genuine-board check — this GUI never had one; it talks to any
  board that speaks the ODrive ASCII protocol, upstream ODrive, a clone,
  or a BSR board alike.

## Building

This fork is source-only here — no precompiled `.exe` is included. To
build one yourself (a couple of minutes on a normal machine with internet
access):

1. Install the [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0).
2. From `source/ODrive GUI/`, run either:
   - `dotnet run` — builds and launches it directly, for trying it out.
   - `dotnet publish -c Release -p:PublishProfile=FolderProfile` — produces
     a single self-contained `.exe` under
     `bin/Release/net8.0-windows/win-x64/publish/` that runs on any
     Windows machine, no .NET install required there.

## Why a separate lock exists on commercial units

The BSR v3.7 design in this repository is open-source and freely
reflashable — that's the point of publishing it. Commercial E-dolly and
Khepri units run a different, BSR-signed firmware build that enforces
torque/speed limits for safety and regulatory reasons; those units check
firmware signature/lineage on boot specifically so those limits can't be
silently removed by reflashing them with this open firmware. That lock is
implemented in the firmware (`Firmware/docs/FIRMWARE_LINEAGE_BSR.md`), not
in this GUI — this GUI works the same against any board, open or
commercial, that will talk to it.
