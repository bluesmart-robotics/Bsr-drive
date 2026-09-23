# CAN safety and diagnostics improvements (BSR v3.7 custom)

Three small, focused additions on top of the CAN work already documented in
`MIT_MODE_BSR.md`, prompted by using E-dolly's two very differently-configured
axes (a wheel in velocity/torque control, a damper in MIT mode) as a concrete
test case for what was still missing.

## 1. MIT-mode commands now feed the axis watchdog

ODrive has a built-in watchdog (`Axis.config.enable_watchdog` /
`watchdog_timeout`): if no command "feeds" it within the configured timeout,
the axis disarms the motor (`main.cpp`'s main control loop calls
`motor_.disarm()` when `watchdog_check()` fails). Every normal CANSimple
command already fed it (`CANSimple::do_command()` calls
`axis.watchdog_feed()` unconditionally), but the MIT-mode command callback
(`CANSimple::mit_command_callback()`) is not dispatched through
`do_command()` - it's a separate, independent CAN subscription (see
`MIT_MODE_BSR.md`'s "Why a separate CAN id" section) - so it was never
feeding the watchdog.

Left unfixed, this meant: an axis run purely over MIT mode with the
watchdog enabled would trip spuriously (a false disarm while commands ARE
still arriving normally), and one without the watchdog enabled had no
protection at all against a dead master or a dropped/disconnected CAN bus -
it would just keep applying the last received Kp/Kd/torque_ff forever.
For an axis driving a physical damper, that's a real safety gap, not just
an inconvenience.

**Fixed**: `mit_command_callback()` now calls `axis.watchdog_feed()` on
every valid command, exactly like every other command source. If you use
MIT mode, you're strongly encouraged to also set
`enable_watchdog = True` and a sensible `watchdog_timeout` (in seconds) on
that axis - without it, a dead master / disconnected bus is silently
invisible to the firmware, watchdog fix or not.

## 2. CAN id conflict detection (`Can.error.DUPLICATE_CAN_IDS`)

Two independent addressing schemes now coexist on the same physical bus:
each axis's normal CANSimple range (`node_id << 5` through `+31`), and any
axis's dedicated `mit_can_id` (a completely separate, freely-configurable
arbitration id - see `MIT_MODE_BSR.md`). Nothing previously cross-checked
these against each other: a typo, or copying axis0's CAN config onto axis1
and forgetting to change every field, could silently make two different
callbacks both fire on the same physical CAN frame - one axis reading it as
a normal command, another (or the same axis's MIT callback) reading it as
an 8-byte MIT command - with no warning.

`odrive-interface.yaml` already declared a `DUPLICATE_CAN_IDS` flag on
`ODrive.Can.error` upstream, but nothing ever actually set it.
`CANSimple::check_can_id_conflicts()` (called once per `service_stack()`
tick - cheap, at most 2 axes) now checks, for every pair of ranges/ids in
use (respecting standard vs. extended frame ids being genuinely separate
address spaces), whether any overlap, and sets `odrv0.can.error |=
DUPLICATE_CAN_IDS` if so. Read `odrv0.can.error` after changing any CAN id
config to confirm you didn't create a conflict. Like every other `*.error`
flag in this firmware, it's sticky until `clear_errors()` (previously
`can_.error_` wasn't even touched by `clear_errors()` - also fixed, so this
flag is actually usable rather than a one-way trip requiring a reboot).

## 3. CAN bus health telemetry (`odrv0.can.tx_error_count` / `rx_error_count` / `is_bus_off`)

The STM32 bxCAN peripheral tracks its own transmit/receive error counters
and bus-off state in hardware (the ESR register), but nothing in this
firmware read them before - only the coarser `HAL_CAN_GetError()` bitmask
was used, enough to notice *that* something is currently wrong but not to
see a problem building up (rising error counts) or to distinguish a
firmware/logic issue from a physical/wiring one.

Three new read-only properties, updated once per CAN service loop
iteration (`ODriveCAN::update_bus_health()`):

- `odrv0.can.tx_error_count` / `rx_error_count` (0-255): per the CAN spec,
  these climb on failed transmissions/receptions and fall on successful
  ones. Should read 0 almost all the time on a healthy bus - persistent
  nonzero values are worth investigating even before anything visibly
  breaks (a connector vibrating loose on a moving robot is exactly the kind
  of thing this would catch early).
- `odrv0.can.is_bus_off`: true if the peripheral hit 256 TX errors and
  disconnected itself from the bus per the CAN spec. This board has
  `AutoBusOff` enabled (`Board/v3/Src/can.c`), so it automatically
  re-arbitrates and recovers once conditions clear - no firmware or master
  action needed for that - but a bus that goes bus-off even occasionally
  still indicates a real physical/wiring problem worth fixing, not a
  transient to shrug off just because it self-heals.

All three are reachable over USB, UART, or the generic
`MSG_CAN_ENDPOINT_OP` CAN command, same as any other property.

## DBC file

`tools/create_bsr_can_dbc.py` generates `tools/bsr-v3.7-cansimple.dbc`,
covering all standard CANSimple messages (including the two BSR-custom
ones, PWRGD enable and the generic endpoint accessor) for this project's
two actual axes, plus the MIT-mode command/reply frames at whatever
`mit_can_id`/`mit_reply_can_id` you configure (edit the constants at the
top of the script and re-run it if your node ids or MIT ids differ from
the defaults baked into the committed `.dbc`). Load it into SavvyCAN,
PCAN-View, `cantools`, or point your own CAN stack's DBC loader at it,
instead of re-deriving frame layouts by hand from this file or
`MIT_MODE_BSR.md`.
