# BSR v3.7 changelog

This file tracks every commit made on top of upstream ODrive firmware
(`odriverobotics/ODrive`, base tag `fw-v0.5.5`, commit `dc261567`) for the
BSR v3.7 board and the E-dolly project. It is separate from the upstream
`Firmware/CHANGELOG.md` (which follows upstream's own "Keep a Changelog"
release process for the ODrive project) so the two don't get tangled
together. Branch: `bsr-v3.7`.

The remote named `origin` in this repo is still the public upstream
`odriverobotics/ODrive` repository - it must **never** be pushed to.
These commits are local-only until they are pushed to BSR's own private
repository.

Commits are listed oldest to newest, matching `git log --oneline dc261567..HEAD`
(reversed).

## 1. `6a98ac4f` - Fix VBUS_S_DIVIDER_RATIO for BSR v3.7 board

The BSR v3.7 board's actual VBUS sense divider is 10k/1k, not the 18k/1k
value inherited from the upstream ODrive v3.6-56V reference design. Fixed
the firmware constant to match the real hardware, correcting the reported
bus voltage.

## 2. `6ce8d0b9` - Add PWRGD monitoring on M0/M1 via GPIO_7/GPIO_8

Added monitoring of the DRV8301 gate driver PWRGD (power-good) signal for
both motor channels, wired to GPIO_7 (M0) and GPIO_8 (M1) on the BSR v3.7
board, to detect gate-driver faults that the stock firmware did not watch.

## 3. `5bc80f17` - Add runtime enable/disable for the PWRGD check (USB, UART, CAN)

Made the PWRGD check from commit 2 toggleable at runtime (rather than
compile-time only), exposed consistently over USB, UART, and CAN
(`MSG_SET_PWRGD_CHECK_ENABLE`, CAN id `0x1E`) - useful for bench testing
without PWRGD wired up, or for boards/revisions where it isn't applicable.

## 4. `defd428d` - Backport confirmed 0.5.5 bug fixes from upstream fw-v0.5.6 + forum

Backported a set of bug fixes that shipped in upstream's fw-v0.5.6 release
(and were separately confirmed/discussed on the ODrive forum as applying to
0.5.5) without pulling in the rest of the 0.5.6 changeset, to keep BSR
v3.7's fork close to the known-good 0.5.5 base while still getting the
fixes.

## 5. `202e433d` - Add generic CAN endpoint get/set for full USB/UART/CAN command parity

Added `MSG_CAN_ENDPOINT_OP` (CAN id `0x1F`, the last free slot in the 5-bit
CANSimple command space), which calls the same generic Fibre endpoint
dispatcher (`fibre::endpoint_handler`) that USB and UART already use. This
gives CAN read/write access to any property or function by its numeric
endpoint id - the same ids exposed to USB/UART - closing the gap where
some commands were only reachable over USB/UART and not CAN. (64-bit
types don't fit in the 6-byte payload and are not supported by this
message.)

Delivered alongside a full reference table (`BSR_v3.7_Commandes_USB_UART_CAN.xlsx`)
listing all ~745 firmware endpoints plus the 33 dedicated CANSimple
messages, with French descriptions, cross-referencing which of the three
transports (USB, UART, CAN) can reach each one.

## 6. `ffeb0d8d` - Push axis errors on CAN immediately on change, not just on the heartbeat timer

`CANSimple::service_stack()` now compares each axis's current error
against the last error reported over CAN on every iteration, and sends a
heartbeat frame immediately when it changes, in addition to the existing
periodic `heartbeat_rate_ms` timer. This is a software polling-and-push
scheme, not a hardware CAN interrupt - worst-case latency is bounded by
how often `service_stack()` reruns (about 10 ms with the default
`encoder_rate_ms` of 10 ms), but in practice this means a CAN master no
longer has to poll for errors to notice them promptly.

## 7. `b156e0d9` - Add MIT-mode (Cheetah-style) direct joint control over CAN

Added `INPUT_MODE_MIT`, a new controller input mode implementing the
de-facto "MIT mode" direct joint control law (popularized by MIT
Biomimetics Lab's Mini Cheetah actuator, now used by CubeMars/Damiao/
RobStride and other actuators):

```
torque = Kp * (pos_des - pos) + Kd * (vel_des - vel) + torque_ff
```

with `pos_des`, `vel_des`, `Kp`, `Kd`, and `torque_ff` all supplied fresh
with every command, instead of ODrive's normal fixed `config.pos_gain`/
`config.vel_gain`. Only usable with `CONTROL_MODE_TORQUE_CONTROL`.

Forum research turned up no prior ODrive developer discussion, feature
request, or rejection of true per-command Kp/Kd control - see
`Firmware/docs/MIT_MODE_BSR.md` for the full writeup and the closest
related forum thread found.

Since the CANSimple 5-bit command-id space (ids 0-31) was already fully
allocated by commit 5, MIT-mode commands are received on a separate,
dedicated CAN arbitration id per axis (`Axis.config.can.mit_can_id`),
independent of the normal `node_id`/`cmd_id` addressing - matching how
real MIT-mode actuators are addressed on a bus. Full setup steps, wire
format, and known limitations are documented in
`Firmware/docs/MIT_MODE_BSR.md`.

(Commit `c21d1eba`, adding this changelog file, isn't listed separately -
it documents commits 1-7 above and is otherwise self-explanatory.)

## 8. `e932c06a` - Fix MIT-mode watchdog gap, detect CAN id conflicts, add bus health telemetry

Three CAN safety/diagnostics fixes, prompted by configuring E-dolly's two
axes very differently (wheel in velocity/torque control, damper in MIT
mode):

- MIT-mode commands (commit 7) never fed the axis watchdog, since
  `mit_command_callback()` bypasses the normal `do_command()` dispatcher
  that feeds it for every other command. Fixed - an axis driven purely
  over MIT mode now correctly disarms if commands stop arriving (with
  `enable_watchdog`/`watchdog_timeout` configured), instead of either
  tripping spuriously or (without the watchdog enabled) having no
  protection at all against a dead master or dropped bus.
- Added `CANSimple::check_can_id_conflicts()`, which flags
  `odrv0.can.error`'s `DUPLICATE_CAN_IDS` bit (declared upstream in
  odrive-interface.yaml but never actually set by any code until now) if
  any axis's normal CAN range and any axis's `mit_can_id` overlap - catches
  a config typo before it silently corrupts CAN traffic. Also fixed
  `clear_errors()` not clearing `can_.error_`, which would have made this
  flag a one-way trip requiring a reboot.
- Added `odrv0.can.tx_error_count`/`rx_error_count`/`is_bus_off`, read
  from the STM32 bxCAN peripheral's ESR register, so a master can notice a
  physically degraded bus (loose connector, bad wiring/termination) from
  rising error counts instead of only seeing a generic send failure after
  the fact.

See `Firmware/docs/CAN_SAFETY_BSR.md` for the full writeup.

## 9. `bd75692e` - Add BSR v3.7 CAN DBC file and generator script

Added `tools/create_bsr_can_dbc.py` and the `tools/bsr-v3.7-cansimple.dbc`
it generates: a self-contained DBC (only needs `cantools`, not the
`odrive` python package upstream's own DBC script depends on) covering
every CANSimple message for this project's actual two axes - including
both BSR-custom messages and the MIT-mode command/reply frames - so any
DBC-aware tool (SavvyCAN, PCAN-View, `cantools`, or a custom CAN stack) can
decode/encode BSR v3.7's traffic directly instead of hand-deriving frame
layouts from the firmware source or `MIT_MODE_BSR.md`. The MIT-mode
signal bit positions were verified by round-tripping `cantools`'
encode/decode against the exact reference packing code in that doc.

## 10. `d7f5c370` - Add BSR firmware lineage lock (simulation phase)

Added the OTP-based mechanism that lets a board "claim" itself to a BSR
private firmware fork (E-dolly-control or flight-control-khepri-libel) the
first time such a fork boots on it, and refuse (hang, same idiom as
`check_board_version()`) any later boot with a different product, a
different signer key, or the public firmware - so a board can't be
reflashed via the standard DFU/USB tools to bypass restrictions or be
swapped between products. Uses the same OTP area as ODrive's own
"genuine board" check, at offsets that never collide with it.

Deliberately simulation-only: `otp_lineage_burn_simulated()` only ever
writes `fake_otp` (RAM), the signature check is a stub returning `true`,
and no flash write-protection (WRP) or read-protection (RDP) option bytes
are touched - so this is safe to build and flash on real hardware today,
but does not yet lock anything for real. Generated one Ed25519 keypair per
fork; only the public halves are in `bsr_signing_keys.cpp`, the private
keys were delivered separately and must never be committed anywhere.

See `Firmware/docs/FIRMWARE_LINEAGE_BSR.md` for the full design, the
phase-2 TODO (real OTP burn, real Ed25519 verification, WRP+RDP), and an
explicit statement of what this does and doesn't defend against (no
secure boot on the STM32F405 - a JTAG/SWD attacker with a full mass-erase
is out of scope without adding a hardware secure element on a future
board revision).

## 11. Add community Windows GUI (BSR v3.7 fork) at `community-gui-winforms/`

Forked [Stijn Carelsbergh's ODrive V3 GUI](https://github.com/stijnsprojects/ODrive-V3-GUI)
(CC BY-NC-SA 4.0 - kept under the same license per its ShareAlike term,
distributed free of charge same as the original) and updated it for this
project's open-source BSR v3.7 firmware fork:

- Added the PWRGD enable/disable setting, the full MIT-mode (Cheetah-style
  direct CAN control) config + live setpoint panels, and CAN bus health
  telemetry (tx/rx error counts, bus-off flag, the `DUPLICATE_CAN_IDS`
  error) - see `Firmware/docs/MIT_MODE_BSR.md` and `CAN_SAFETY_BSR.md` for
  what each of these is.
- Recognizes firmware revision 5 (this project's base, upstream
  fw-v0.5.5) in addition to the 6/0 the original handled.
- Fixed two stale values in the original that predate this fork and
  didn't match any real ODrive firmware: the control-mode dropdown had an
  invalid 5th entry, and the axis-error list was missing
  `MOTOR_FAILED`/`SENSORLESS_ESTIMATOR_FAILED`/`ENCODER_FAILED`/
  `CONTROLLER_FAILED`.
- Fixed a build-breaking bug inherited from upstream: the `.csproj`
  referenced a `PackageIcon` file (`odrive border.png`) that doesn't
  exist anywhere in that project's git history, which made
  `dotnet build`/`dotnet pack` fail with a missing-file error. Dropped
  the missing reference; the actual window/taskbar icon is untouched.
- Added a "Demo mode" (`Transport.cs`: `IDeviceTransport`,
  `RealSerialTransport`, `DemoOdriveTransport`) that simulates a BSR v3.7
  board's ASCII-protocol responses entirely in memory, so the interface -
  including the new BSR panels - can be previewed with no board attached.
  This GUI never had, and still doesn't have, any genuine-hardware/OTP
  check to bypass: it talks to any board (upstream ODrive, a clone, or a
  BSR board) that speaks the plain-text serial protocol.

Note the distinction from item 10 above: this GUI configures the *open*
BSR v3.7 design that this repository publishes. It has no relationship to
the firmware lineage lock, which exists only in the separate, BSR-signed
firmware that commercial E-dolly/Khepri units ship with, specifically so
those units' torque/speed safety limits can't be removed by reflashing
them with this open firmware.

Not compiled/verified in this environment - the sandbox this fork was
written in blocks `nuget.org` and `dot.net` by organization egress
policy, so `dotnet restore`/`build` couldn't be run here. Reviewed by
hand instead (brace/structure balance, call-site consistency, layout grid
math); build on a normal machine per `community-gui-winforms/README.md`
before relying on it.

## 12. Add community Web GUI (BSR v3.7 fork) at `community-gui-web/`

Forked [MoonLighTingPY's odrive3.6_web_gui](https://github.com/MoonLighTingPY/odrive3.6_web_gui)
(Python/Flask backend + React/Vite/Chakra UI frontend, built-in mock
device, config wizard, Inspector, live charts) with the author's direct
permission - contacted and confirmed via Telegram. **License terms for
this fork are still being finalized with him**; see
`community-gui-web/BSR_V3.7_CHANGES.md` for the current status and full
technical detail.

Adds, on top of the shared 0.5.x API reference both the backend and
frontend read from: PWRGD gate-driver monitoring
(`axis{n}.motor.config.enable_pwrgd_check`); MIT-mode (Cheetah-style)
direct CAN joint control - 12 config fields under `axis{n}.config.can.*`
plus a new `INPUT_MODE_MIT` enum value, and 5 live setpoint fields under
`axis{n}.controller.*`; and CAN bus health telemetry
(`can.tx_error_count`, `can.rx_error_count`, `can.is_bus_off`). Also fixed
the mock device's simulated firmware revision (was a placeholder `6`, now
`5` to match BSR v3.7's upstream base fw-v0.5.5).

Unlike item 11 (blocked from compiling by this sandbox's network policy),
this fork's tooling isn't blocked - PyPI and npm both work here - so it
was verified for real: the Flask server was run in mock mode and
exercised over its actual WebSocket read/write protocol (not just
inspected), the existing frontend test suite (40 vitest tests) still
passes with zero regressions, eslint is clean on every file touched, and
the production Vite build succeeds. This is now the recommended community
GUI; the WinForms fork (item 11) is kept as a lighter-weight fallback.

---

## When pushing to GitHub

These commits are currently local-only on `bsr-v3.7` (the `origin` remote
is upstream's public repo and must not receive them). Once BSR's own
private repository is reachable, push `bsr-v3.7` there and update this
note. Patch files (`000N-*.patch`, via `git format-patch`) and a
`bsr-odrive-v3.7.zip` snapshot are kept as an interim backup until then.
