# MIT mode (BSR v3.7 custom)

## What this is and why

"MIT mode" is the informal name for a direct joint control law popularized
by the MIT Biomimetics Robotics Lab's Mini Cheetah actuator (Ben Katz),
since adopted as a de-facto standard wire protocol by several commercial
BLDC actuator/servo controllers (CubeMars AK-series, Damiao, RobStride, and
others). Instead of position/velocity control modes with *fixed*
configuration gains, the master sends, with every command:

* a desired position and velocity (`pos_des`, `vel_des`)
* a feedforward torque (`torque_ff`)
* the position and velocity gains to use *for this command* (`Kp`, `Kd`)

and the actuator computes torque directly:

```
torque = Kp * (pos_des - pos) + Kd * (vel_des - vel) + torque_ff
```

The important difference from ODrive's normal `CONTROL_MODE_POSITION_CONTROL`
is that `Kp`/`Kd` travel with every command instead of being fixed config -
this lets a whole-body/leg controller vary a joint's mechanical impedance
on the fly (stiff during stance, compliant during swing, for example),
which is what "MIT mode" is actually used for in legged robotics.

We looked at what ODrive's own developers had said about this on the
community forum before implementing it. The closest discussion
(["Can I use Odrive to build a cheetah leg?"](https://discourse.odriverobotics.com/t/can-i-use-odrive-to-build-a-cheetah-leg/1189))
has a developer answering that the *impedance control* shown in the MIT
Cheetah demo videos "should be working without changing the firmware code,
just setting parameters. Specifically a position gain and velocity gain."
That's true for a fixed impedance set once via `config.pos_gain`/
`config.vel_gain` - but it does not give per-command, per-timestep Kp/Kd,
nor the compact single-CAN-frame wire format that the real "MIT mode"
ecosystem (and any master software written for it) expects. This feature
adds that missing piece; it was not found to have been implemented,
requested with technical detail, or rejected anywhere in the ODrive
forums/issue tracker - the analysis above is the extent of what exists on
the topic there.

## Setup

1. Put the axis in `AXIS_STATE_CLOSED_LOOP_CONTROL` as usual.
2. `odrv0.axisN.controller.config.control_mode = CONTROL_MODE_TORQUE_CONTROL`
   (**required** - see below).
3. `odrv0.axisN.controller.config.input_mode = INPUT_MODE_MIT` (9).
4. `odrv0.axisN.config.can.enable_mit = True`.
5. `odrv0.axisN.config.can.mit_can_id = <an arbitration id not used by
   anything else on the bus>` - pick something outside the CANSimple
   `node_id<<5 .. node_id<<5+31` range already in use by your axes (e.g.
   `0x400`/`0x410` for axis0/axis1 if your node ids are 0/1). This is a
   completely separate subscription from the normal CANSimple messages -
   see "Why a separate CAN id" below.
6. Optionally `odrv0.axisN.config.can.mit_reply_can_id = <another unused
   id>` (0 disables the reply frame).
7. Tune `mit_pos_min`/`mit_pos_max`, `mit_vel_min`/`mit_vel_max`,
   `mit_kp_min`/`mit_kp_max`, `mit_kd_min`/`mit_kd_max`,
   `mit_torque_min`/`mit_torque_max` to your actual joint/gearbox and to
   whatever your master-side packing code uses - the defaults are generic
   placeholders (loosely converted from a common small actuator's
   datasheet, radians to turns) and almost certainly need retuning. Getting
   a range wrong doesn't error, it silently clamps - so double check this
   with a known test command before trusting it.

Using `INPUT_MODE_MIT` with any `control_mode` other than
`CONTROL_MODE_TORQUE_CONTROL` raises `ERROR_INVALID_INPUT_MODE`: the
normal position-loop -> velocity-loop cascade only runs for
`CONTROL_MODE_POSITION_CONTROL`/`VELOCITY_CONTROL`, and it uses `config.
pos_gain`/`config.vel_gain`, not `mit_kp`/`mit_kd` - running both at once
would silently stack two different PD laws on top of each other.

## Why a separate CAN id instead of a CANSimple message

The CANSimple protocol packs `node_id` and a 5-bit command id into the
11-bit CAN arbitration id (`node_id << 5 | cmd_id`). That 5-bit command
space (ids 0-31) is already fully allocated by existing BSR v3.7 messages -
see `Firmware/communication/can/can_simple.hpp`, there is no free slot left.

Real MIT-mode actuators don't use command-id sub-addressing at all: the
*entire* CAN arbitration id is the joint's address, with no room for (or
need of) a separate command id, since an actuator running "MIT mode" is
usually not also running a second, unrelated command protocol on the same
id. We followed that same model here: each axis gets its own dedicated
`mit_can_id`, subscribed to independently of (and in addition to) its
normal CANSimple `node_id`. This also means a master built for a
CubeMars/Damiao/RobStride actuator's *command* packing can drive this axis
unmodified, just pointed at `mit_can_id` instead of that actuator's id.

## Wire format

### Command (master -> axis), 8 bytes, sent to `mit_can_id`

Fixed-point, 16/12/12/12/12 bits, matching the widely-used MIT-mode
reference packing:

| Bytes | Bits | Field | Range |
|---|---|---|---|
| 0-1 | 16 | position | `mit_pos_min` .. `mit_pos_max` |
| 2 - 3(hi) | 12 | velocity | `mit_vel_min` .. `mit_vel_max` |
| 3(lo) - 4 | 12 | Kp | `mit_kp_min` .. `mit_kp_max` |
| 5 - 6(hi) | 12 | Kd | `mit_kd_min` .. `mit_kd_max` |
| 6(lo) - 7 | 12 | torque_ff | `mit_torque_min` .. `mit_torque_max` |

```c
uint16_t p_int  = float_to_uint(p_des, P_MIN, P_MAX, 16);
uint16_t v_int  = float_to_uint(v_des, V_MIN, V_MAX, 12);
uint16_t kp_int = float_to_uint(kp,    KP_MIN, KP_MAX, 12);
uint16_t kd_int = float_to_uint(kd,    KD_MIN, KD_MAX, 12);
uint16_t t_int  = float_to_uint(t_ff,  T_MIN, T_MAX, 12);

buf[0] = p_int >> 8;
buf[1] = p_int & 0xFF;
buf[2] = v_int >> 4;
buf[3] = ((v_int & 0xF) << 4) | (kp_int >> 8);
buf[4] = kp_int & 0xFF;
buf[5] = kd_int >> 4;
buf[6] = ((kd_int & 0xF) << 4) | (t_int >> 8);
buf[7] = t_int & 0xFF;

// float_to_uint / uint_to_float:
uint16_t float_to_uint(float x, float x_min, float x_max, int bits) {
    if (x < x_min) x = x_min;
    if (x > x_max) x = x_max;
    return (uint16_t)((x - x_min) * (float)((1 << bits) - 1) / (x_max - x_min));
}
float uint_to_float(uint16_t x_int, float x_min, float x_max, int bits) {
    return ((float)x_int) * (x_max - x_min) / (float)((1 << bits) - 1) + x_min;
}
```

### Reply (axis -> master), 5 bytes, sent on `mit_reply_can_id` (if nonzero)

Sent automatically right after each command frame is processed: measured
position (16 bits), measured velocity (12 bits), measured torque (12
bits), packed the same way and using the *same* configured ranges
(`mit_torque_min`/`max` doubles as the measured-torque range).

**This reply is BSR's own format** - the same encoding style as the
command, for consistency - not a byte-for-byte clone of any specific
vendor's telemetry frame. A master written against a particular actuator
brand's exact reply layout may need its reply-parsing code adjusted even
though its command-sending code should work unmodified.

## Known limitations

* Position is read from the axis's *linear* estimate - `mit_pos_setpoint`
  does not wrap, even if `controller.config.circular_setpoints` is set.
  Not intended for endless-rotation joints.
* Only reachable over CAN via the dedicated `mit_can_id`/`mit_reply_can_id`
  frames described above (by design - that's the point of the compact
  format). Each of the five underlying values (`mit_pos_setpoint`,
  `mit_vel_setpoint`, `mit_kp`, `mit_kd`, `mit_torque_ff`) is also an
  ordinary read/write property, reachable individually over USB, UART, or
  the generic `MSG_CAN_ENDPOINT_OP` CAN command - useful for testing one
  value at a time, but not atomic the way the packed frame is.
* The fixed-point ranges are generic placeholders (see Setup, step 7) and
  must be retuned per joint.
