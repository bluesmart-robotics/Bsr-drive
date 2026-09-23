#!/usr/bin/env python3
"""
BSR v3.7 CANSimple DBC generator.

Adapted from upstream ODrive's own tools/create_can_dbc.py (which loops
over 8 generic axis slots and needs the `odrive` python package purely for
its enums), but:
  - self-contained: enum choices are inlined below, taken directly from
    this fork's autogen/interfaces.hpp, so this script has no dependency on
    the `odrive` python package - only `cantools` (pip install cantools).
  - generates messages only for BSR v3.7's actual two axes, using their
    ASSUMED node_id (see AXIS_NODE_IDS below - edit this if you configure
    different node_ids than the 0/1 default suggested in this project's
    setup docs).
  - adds BSR v3.7's two custom messages that upstream's script doesn't
    know about: MSG_SET_PWRGD_CHECK_ENABLE (0x1E) and the generic Fibre
    endpoint accessor MSG_CAN_ENDPOINT_OP (0x1F).
  - adds the MIT-mode command/reply frames. These are NOT part of the
    node_id<<5|cmd_id scheme - each axis listens on its own independent,
    freely configurable CAN id (Axis.config.can.mit_can_id /
    mit_reply_can_id) - so this script can only describe them at whatever
    ids you actually configure. Edit MIT_CAN_IDS below to match your real
    configuration and re-run this script if you change it.

Usage:
    pip install cantools --break-system-packages
    python3 generate_dbc.py
    -> writes bsr-v3.7-cansimple.dbc in the current directory
"""

import cantools.database as can
from cantools.database.conversion import BaseConversion


def Signal(name, start, length, is_float=False, is_signed=False, scale=1, choices=None,
           unit=None, receivers=None, byte_order="little_endian", comment=None):
    """Compatibility wrapper: newer cantools (this script was written
    against 44.1.0) moved scale/is_float/choices off Signal's constructor
    and into a separate `conversion` object (BaseConversion.factory), unlike
    the older cantools API upstream's create_can_dbc.py was written against.
    This keeps the rest of this script's call sites unchanged."""
    conversion = None
    if choices is not None or is_float or scale != 1:
        conversion = BaseConversion.factory(scale=scale, offset=0, choices=choices, is_float=is_float)
    kwargs = dict(byte_order=byte_order, is_signed=is_signed, unit=unit,
                  receivers=receivers or [], comment=comment)
    if conversion is not None:
        kwargs["conversion"] = conversion
    return can.Signal(name, start, length, **kwargs)


def be_start(msb_bit_index):
    """Convert a big-endian (Motorola) signal's MSB position - counted the
    "natural" way, sequentially from bit 0 = the very first (most
    significant) bit of byte 0, through bit 63 = the last (least
    significant) bit of byte 7 - into the `start` value cantools/the DBC
    format actually expect for byte_order="big_endian". DBC's own bit
    numbering for Motorola signals is not sequential this way (it restarts
    counting down from the top of each byte), so this conversion is
    necessary any time a signal's bit layout is easier to reason about, and
    to cross-check against reference code, in the natural/sequential form -
    which is how the MIT-mode wire format is documented in
    Firmware/docs/MIT_MODE_BSR.md and in the reference C packing code there.
    Verified against that exact C code by round-tripping cantools'
    Message.encode()/decode() before using this in the messages below."""
    byte_idx = msb_bit_index // 8
    bit_in_byte = msb_bit_index % 8
    return byte_idx * 8 + (7 - bit_in_byte)

# ---------------------------------------------------------------------------
# EDIT THESE to match your actual configuration before regenerating.
# ---------------------------------------------------------------------------

# node_id configured on odrv0.axis0.config.can.node_id / axis1's, in that
# order. BSR v3.7's default node_id is 0 for both axes until configured -
# this project's setup docs suggest setting axis1's node_id to 1.
AXIS_NODE_IDS = [0, 1]

# mit_can_id / mit_reply_can_id configured on each axis, if you use MIT mode
# there (Axis.config.can.enable_mit). Set an entry to None to skip
# generating MIT messages for that axis (e.g. axis0, the wheel, which in
# the E-dolly project runs velocity/torque control instead of MIT mode).
MIT_CAN_IDS = [
    None,                                  # axis0 (wheel) - not using MIT mode
    {"cmd": 0x410, "reply": 0x411},        # axis1 (damper) - MIT mode
]

NUM_CMD_ID_BITS = 5  # matches CANSimple::NUM_CMD_ID_BITS in can_simple.hpp

# ---------------------------------------------------------------------------
# Enum choices, copied from this fork's Firmware/autogen/interfaces.hpp
# (generated from odrive-interface.yaml) at the time this script was
# written. Re-check these against autogen/interfaces.hpp if you add/change
# error flags or state values later.
# ---------------------------------------------------------------------------

AXIS_ERROR = {
    0x00000000: "NONE", 0x00000001: "INVALID_STATE", 0x00000040: "MOTOR_FAILED",
    0x00000080: "SENSORLESS_ESTIMATOR_FAILED", 0x00000100: "ENCODER_FAILED",
    0x00000200: "CONTROLLER_FAILED", 0x00000800: "WATCHDOG_TIMER_EXPIRED",
    0x00001000: "MIN_ENDSTOP_PRESSED", 0x00002000: "MAX_ENDSTOP_PRESSED",
    0x00004000: "ESTOP_REQUESTED", 0x00020000: "HOMING_WITHOUT_ENDSTOP",
    0x00040000: "OVER_TEMP", 0x00080000: "UNKNOWN_POSITION",
}
AXIS_STATE = {
    0: "UNDEFINED", 1: "IDLE", 2: "STARTUP_SEQUENCE", 3: "FULL_CALIBRATION_SEQUENCE",
    4: "MOTOR_CALIBRATION", 6: "ENCODER_INDEX_SEARCH", 7: "ENCODER_OFFSET_CALIBRATION",
    8: "CLOSED_LOOP_CONTROL", 9: "LOCKIN_SPIN", 10: "ENCODER_DIR_FIND", 11: "HOMING",
    12: "ENCODER_HALL_POLARITY_CALIBRATION", 13: "ENCODER_HALL_PHASE_CALIBRATION",
}
MOTOR_ERROR = {
    0x00000000: "NONE", 0x00000001: "PHASE_RESISTANCE_OUT_OF_RANGE",
    0x00000002: "PHASE_INDUCTANCE_OUT_OF_RANGE", 0x00000008: "DRV_FAULT",
    0x00000010: "CONTROL_DEADLINE_MISSED", 0x00000080: "MODULATION_MAGNITUDE",
    0x00000400: "CURRENT_SENSE_SATURATION", 0x00001000: "CURRENT_LIMIT_VIOLATION",
    0x00010000: "MODULATION_IS_NAN", 0x00020000: "MOTOR_THERMISTOR_OVER_TEMP",
    0x00040000: "FET_THERMISTOR_OVER_TEMP", 0x00080000: "TIMER_UPDATE_MISSED",
    0x00100000: "CURRENT_MEASUREMENT_UNAVAILABLE", 0x00200000: "CONTROLLER_FAILED",
    0x00400000: "I_BUS_OUT_OF_RANGE", 0x00800000: "BRAKE_RESISTOR_DISARMED",
    0x01000000: "SYSTEM_LEVEL", 0x02000000: "BAD_TIMING",
    0x04000000: "UNKNOWN_PHASE_ESTIMATE", 0x08000000: "UNKNOWN_PHASE_VEL",
    0x10000000: "UNKNOWN_TORQUE", 0x20000000: "UNKNOWN_CURRENT_COMMAND",
    0x40000000: "UNKNOWN_CURRENT_MEASUREMENT", 0x80000000: "UNKNOWN_VBUS_VOLTAGE",
}
ENCODER_ERROR = {
    0x00000000: "NONE", 0x00000001: "UNSTABLE_GAIN", 0x00000002: "CPR_POLEPAIRS_MISMATCH",
    0x00000004: "NO_RESPONSE", 0x00000008: "UNSUPPORTED_ENCODER_MODE",
    0x00000010: "ILLEGAL_HALL_STATE", 0x00000020: "INDEX_NOT_FOUND_YET",
    0x00000040: "ABS_SPI_TIMEOUT", 0x00000080: "ABS_SPI_COM_FAIL",
    0x00000100: "ABS_SPI_NOT_READY", 0x00000200: "HALL_NOT_CALIBRATED_YET",
}
SENSORLESS_ERROR = {
    0x00000000: "NONE", 0x00000001: "UNSTABLE_GAIN", 0x00000002: "UNKNOWN_CURRENT_MEASUREMENT",
}
CONTROLLER_ERROR = {
    0x00000000: "NONE", 0x00000001: "OVERSPEED", 0x00000002: "INVALID_INPUT_MODE",
    0x00000004: "UNSTABLE_GAIN", 0x00000008: "INVALID_MIRROR_AXIS",
    0x00000010: "INVALID_LOAD_ENCODER", 0x00000020: "INVALID_ESTIMATE",
    0x00000040: "INVALID_CIRCULAR_RANGE", 0x00000080: "SPINOUT_DETECTED",
}
CONTROL_MODE = {0: "VOLTAGE_CONTROL", 1: "TORQUE_CONTROL", 2: "VELOCITY_CONTROL", 3: "POSITION_CONTROL"}
INPUT_MODE = {
    0: "INACTIVE", 1: "PASSTHROUGH", 2: "VEL_RAMP", 3: "POS_FILTER", 4: "MIX_CHANNELS",
    5: "TRAP_TRAJ", 6: "TORQUE_RAMP", 7: "MIRROR", 8: "TUNING",
    9: "MIT",  # BSR v3.7 custom - see Firmware/docs/MIT_MODE_BSR.md
}

# ---------------------------------------------------------------------------

nodes = [can.Node("Master")]
buses = [can.Bus("BSR_v3.7", None, 250000)]  # BSR v3.7 default CAN baud rate
msgList = []

for slot, node_id in enumerate(AXIS_NODE_IDS):
    axis_node = can.Node(f"BSR_Axis{slot}")
    nodes.append(axis_node)

    axisError = Signal("Axis_Error", 0, 32, receivers=["Master"], choices=AXIS_ERROR)
    axisState = Signal("Axis_State", 32, 8, receivers=["Master"], choices=AXIS_STATE)
    motorErrorFlag = Signal("Motor_Error_Flag", 40, 1, receivers=["Master"])
    encoderErrorFlag = Signal("Encoder_Error_Flag", 48, 1, receivers=["Master"])
    controllerErrorFlag = Signal("Controller_Error_Flag", 56, 1, receivers=["Master"])
    trajectoryDoneFlag = Signal("Trajectory_Done_Flag", 63, 1, receivers=["Master"])
    heartbeatMsg = can.Message(
        0x000, "Heartbeat", 8,
        [axisError, axisState, motorErrorFlag, encoderErrorFlag, controllerErrorFlag, trajectoryDoneFlag],
        send_type="cyclic", cycle_time=100, senders=[axis_node.name],
        comment="Also pushed immediately on any axis.error_ change (BSR v3.7), not just on the heartbeat_rate_ms timer.",
    )

    estopMsg = can.Message(0x002, "Estop", 0, [], senders=["Master"])
    # (upstream's own create_can_dbc.py builds this message but never
    # actually adds it to the database - a latent bug there. Estop is
    # dispatched per-axis just like everything else here (see
    # CANSimple::do_command()'s MSG_ODRIVE_ESTOP case), so it belongs in
    # axisMsgs below with the same node_id<<5 frame_id shift, not as a
    # separate un-shifted "master" message.)

    motorError = Signal("Motor_Error", 0, 32, receivers=["Master"], choices=MOTOR_ERROR)
    motorErrorMsg = can.Message(0x003, "Get_Motor_Error", 8, [motorError], senders=[axis_node.name])

    encoderError = Signal("Encoder_Error", 0, 32, receivers=["Master"], choices=ENCODER_ERROR)
    encoderErrorMsg = can.Message(0x004, "Get_Encoder_Error", 8, [encoderError], senders=[axis_node.name])

    sensorlessError = Signal("Sensorless_Error", 0, 32, receivers=["Master"], choices=SENSORLESS_ERROR)
    sensorlessErrorMsg = can.Message(0x005, "Get_Sensorless_Error", 8, [sensorlessError], senders=[axis_node.name])

    axisNodeID = Signal("Axis_Node_ID", 0, 32, receivers=[axis_node.name])
    axisNodeMsg = can.Message(0x006, "Set_Axis_Node_ID", 8, [axisNodeID], senders=["Master"])

    axisRequestedState = Signal("Axis_Requested_State", 0, 32, receivers=[axis_node.name], choices=AXIS_STATE)
    setAxisState = can.Message(0x007, "Set_Axis_State", 8, [axisRequestedState], senders=["Master"])

    encoderPosEstimate = Signal("Pos_Estimate", 0, 32, is_float=True, receivers=["Master"], unit="rev")
    encoderVelEstimate = Signal("Vel_Estimate", 32, 32, is_float=True, receivers=["Master"], unit="rev/s")
    encoderEstimates = can.Message(
        0x009, "Get_Encoder_Estimates", 8, [encoderPosEstimate, encoderVelEstimate],
        senders=[axis_node.name], send_type="cyclic", cycle_time=10,
    )

    encoderShadowCount = Signal("Shadow_Count", 0, 32, receivers=["Master"], unit="counts")
    encoderCountInCPR = Signal("Count_in_CPR", 32, 32, receivers=["Master"], unit="counts")
    encoderCountMsg = can.Message(0x00A, "Get_Encoder_Count", 8, [encoderShadowCount, encoderCountInCPR], senders=[axis_node.name])

    controlMode = Signal("Control_Mode", 0, 32, receivers=[axis_node.name], choices=CONTROL_MODE)
    inputMode = Signal("Input_Mode", 32, 32, receivers=[axis_node.name], choices=INPUT_MODE)
    setControllerModeMsg = can.Message(0x00B, "Set_Controller_Mode", 8, [controlMode, inputMode], senders=["Master"])

    inputPos = Signal("Input_Pos", 0, 32, is_float=True, receivers=[axis_node.name], unit="rev")
    velFF = Signal("Vel_FF", 32, 16, is_signed=True, scale=0.001, receivers=[axis_node.name], unit="rev/s")
    torqueFF = Signal("Torque_FF", 48, 16, is_signed=True, scale=0.001, receivers=[axis_node.name], unit="Nm")
    setInputPosMsg = can.Message(0x00C, "Set_Input_Pos", 8, [inputPos, velFF, torqueFF], senders=["Master"])

    inputVel = Signal("Input_Vel", 0, 32, is_float=True, receivers=[axis_node.name], unit="rev/s")
    inputTorqueFF = Signal("Input_Torque_FF", 32, 32, is_float=True, receivers=[axis_node.name], unit="Nm")
    setInputVelMsg = can.Message(0x00D, "Set_Input_Vel", 8, [inputVel, inputTorqueFF], senders=["Master"])

    inputTorque = Signal("Input_Torque", 0, 32, is_float=True, receivers=[axis_node.name], unit="Nm")
    setInputTqMsg = can.Message(0x00E, "Set_Input_Torque", 8, [inputTorque], senders=["Master"])

    velLimit = Signal("Velocity_Limit", 0, 32, is_float=True, receivers=[axis_node.name], unit="rev/s")
    currentLimit = Signal("Current_Limit", 32, 32, is_float=True, receivers=[axis_node.name], unit="A")
    setVelLimMsg = can.Message(0x00F, "Set_Limits", 8, [velLimit, currentLimit], senders=["Master"])

    startAnticoggingMsg = can.Message(0x010, "Start_Anticogging", 0, [], senders=["Master"])

    trajVelLim = Signal("Traj_Vel_Limit", 0, 32, is_float=True, receivers=[axis_node.name], unit="rev/s")
    setTrajVelMsg = can.Message(0x011, "Set_Traj_Vel_Limit", 8, [trajVelLim], senders=["Master"])

    trajAccelLim = Signal("Traj_Accel_Limit", 0, 32, is_float=True, receivers=[axis_node.name], unit="rev/s^2")
    trajDecelLim = Signal("Traj_Decel_Limit", 32, 32, is_float=True, receivers=[axis_node.name], unit="rev/s^2")
    setTrajAccelMsg = can.Message(0x012, "Set_Traj_Accel_Limits", 8, [trajAccelLim, trajDecelLim], senders=["Master"])

    trajInertia = Signal("Traj_Inertia", 0, 32, is_float=True, receivers=[axis_node.name], unit="Nm / (rev/s^2)")
    trajInertiaMsg = can.Message(0x013, "Set_Traj_Inertia", 8, [trajInertia], senders=["Master"])

    iqSetpoint = Signal("Iq_Setpoint", 0, 32, is_float=True, receivers=["Master"], unit="A")
    iqMeasured = Signal("Iq_Measured", 32, 32, is_float=True, receivers=["Master"], unit="A")
    getIqMsg = can.Message(0x014, "Get_Iq", 8, [iqSetpoint, iqMeasured], senders=[axis_node.name])

    sensorlessPosEstimate = Signal("Sensorless_Pos_Estimate", 0, 32, is_float=True, receivers=["Master"], unit="rev")
    sensorlessVelEstimate = Signal("Sensorless_Vel_Estimate", 32, 32, is_float=True, receivers=["Master"], unit="rev/s")
    getSensorlessEstMsg = can.Message(0x015, "Get_Sensorless_Estimates", 8, [sensorlessPosEstimate, sensorlessVelEstimate], senders=[axis_node.name])

    rebootMsg = can.Message(0x016, "Reboot", 0, [], senders=["Master"])

    busVoltage = Signal("Bus_Voltage", 0, 32, is_float=True, receivers=["Master"], unit="V")
    getVbusMsg = can.Message(0x017, "Get_Bus_Voltage", 8, [busVoltage], senders=[axis_node.name])

    clearErrorsMsg = can.Message(0x018, "Clear_Errors", 0, [], senders=["Master"])

    position = Signal("Position", 0, 32, is_signed=True, receivers=[axis_node.name], unit="counts")
    setLinearCountMsg = can.Message(0x019, "Set_Linear_Count", 8, [position], senders=["Master"])

    posGain = Signal("Pos_Gain", 0, 32, is_float=True, receivers=[axis_node.name], unit="(rev/s) / rev")
    setPosGainMsg = can.Message(0x01A, "Set_Pos_Gain", 8, [posGain], senders=["Master"])

    velGain = Signal("Vel_Gain", 0, 32, is_float=True, receivers=[axis_node.name], unit="Nm / (rev/s)")
    velIntGain = Signal("Vel_Integrator_Gain", 32, 32, is_float=True, receivers=[axis_node.name], unit="(Nm / (rev/s)) / s")
    setVelGainsMsg = can.Message(0x01B, "Set_Vel_Gains", 8, [velGain, velIntGain], senders=["Master"])

    # Request (Master->axis, 1 byte: GPIO_Num) and response (axis->Master,
    # 4-byte float) share this one id/message like every other Get_* message
    # here - cantools models one CAN id as one Message, so only the response
    # signal is declared; the request's payload is documented in the comment
    # instead of as a second, id-colliding Message.
    adcVoltage = Signal("ADC_Voltage", 0, 32, is_float=True, receivers=["Master"], unit="V")
    getADCVoltageMsg = can.Message(
        0x01C, "Get_ADC_Voltage", 8, [adcVoltage], senders=[axis_node.name],
        comment="Request (Master->axis) is 1 byte: GPIO_Num (uint8) at byte 0. Response (shown here) is the ADC voltage reading.",
    )

    controllerError = Signal("Controller_Error", 0, 32, receivers=["Master"], choices=CONTROLLER_ERROR)
    controllerErrorMsg = can.Message(0x01D, "Get_Controller_Error", 8, [controllerError], senders=[axis_node.name])

    # --- BSR v3.7 custom messages (ids 0x1E, 0x1F) ---
    pwrgdEnable = Signal("Enable", 0, 8, receivers=[axis_node.name])
    setPwrgdCheckMsg = can.Message(
        0x01E, "Set_PWRGD_Check_Enable", 1, [pwrgdEnable], senders=["Master"],
        comment="BSR v3.7 custom. Nonzero enables the DRV8301 PWRGD gate-driver-fault check for this axis.",
    )

    endpointId = Signal("Endpoint_ID", 0, 16, receivers=[axis_node.name, "Master"])
    endpointData = Signal("Value", 16, 48, receivers=[axis_node.name, "Master"], byte_order="little_endian")
    canEndpointOpMsg = can.Message(
        0x01F, "CAN_Endpoint_Op", 8, [endpointId, endpointData], senders=["Master", axis_node.name],
        comment=(
            "BSR v3.7 custom, request AND response share this id/layout. Generic read/write of any "
            "Fibre property or function by its numeric endpoint id (same ids USB/UART use) - see "
            "CANSimple::endpoint_op_callback() in can_simple.cpp. The 'Value' field's actual meaning "
            "depends entirely on which endpoint id is addressed and cannot be described generically "
            "here; empty (2-byte message) = read, present = write-then-read-back. 64-bit endpoints "
            "don't fit and are not reachable this way."
        ),
    )

    axisMsgs = [
        heartbeatMsg, estopMsg, motorErrorMsg, encoderErrorMsg, sensorlessErrorMsg, axisNodeMsg, setAxisState,
        encoderEstimates, encoderCountMsg, setControllerModeMsg, setInputPosMsg, setInputVelMsg,
        setInputTqMsg, setVelLimMsg, startAnticoggingMsg, setTrajVelMsg, setTrajAccelMsg, trajInertiaMsg,
        getIqMsg, getSensorlessEstMsg, rebootMsg, getVbusMsg, clearErrorsMsg, setLinearCountMsg,
        setPosGainMsg, setVelGainsMsg, getADCVoltageMsg, controllerErrorMsg,
        setPwrgdCheckMsg, canEndpointOpMsg,
    ]

    for msg in axisMsgs:
        msg.name = f"Axis{slot}_{msg.name}"
        msg.frame_id = (node_id << NUM_CMD_ID_BITS) | msg.frame_id
    msgList.append(axisMsgs)

    # --- MIT-mode command/reply, if configured for this axis slot ---
    mit = MIT_CAN_IDS[slot] if slot < len(MIT_CAN_IDS) else None
    if mit:
        mitPos = Signal("Pos_Des_Raw", be_start(0), 16, byte_order="big_endian", receivers=[axis_node.name],
                             comment="16-bit fixed point over [mit_pos_min, mit_pos_max] - see MIT_MODE_BSR.md")
        mitVel = Signal("Vel_Des_Raw", be_start(16), 12, byte_order="big_endian", receivers=[axis_node.name],
                             comment="12-bit fixed point over [mit_vel_min, mit_vel_max]")
        mitKp = Signal("Kp_Raw", be_start(28), 12, byte_order="big_endian", receivers=[axis_node.name],
                            comment="12-bit fixed point over [mit_kp_min, mit_kp_max]")
        mitKd = Signal("Kd_Raw", be_start(40), 12, byte_order="big_endian", receivers=[axis_node.name],
                            comment="12-bit fixed point over [mit_kd_min, mit_kd_max]")
        mitTff = Signal("Torque_FF_Raw", be_start(52), 12, byte_order="big_endian", receivers=[axis_node.name],
                             comment="12-bit fixed point over [mit_torque_min, mit_torque_max]")
        mitCmdMsg = can.Message(
            mit["cmd"], f"Axis{slot}_MIT_Command", 8, [mitPos, mitVel, mitKp, mitKd, mitTff], senders=["Master"],
            comment=(
                "BSR v3.7 custom MIT-mode command frame - NOT part of the node_id<<5|cmd_id scheme, this "
                "is its own dedicated arbitration id (Axis.config.can.mit_can_id). Raw values are packed "
                "16/12/12/12/12-bit fixed point; decode with the ranges configured in Axis.config.can."
                "mit_*_min/max (see Firmware/docs/MIT_MODE_BSR.md). Standard cantools scaling can't "
                "express 'range depends on runtime config', so this DBC only documents bit positions/"
                "widths, not physical units - decode the raw ints and apply the ODrive-side range "
                "yourself (or read them back over USB/UART/CAN-endpoint-op to confirm)."
            ),
        )
        if mit.get("reply"):
            rPos = Signal("Pos_Meas_Raw", be_start(0), 16, byte_order="big_endian", receivers=["Master"])
            rVel = Signal("Vel_Meas_Raw", be_start(16), 12, byte_order="big_endian", receivers=["Master"])
            rTrq = Signal("Torque_Meas_Raw", be_start(28), 12, byte_order="big_endian", receivers=["Master"])
            mitReplyMsg = can.Message(
                mit["reply"], f"Axis{slot}_MIT_Reply", 5, [rPos, rVel, rTrq], senders=[axis_node.name],
                comment="BSR v3.7 custom MIT-mode reply frame, sent on Axis.config.can.mit_reply_can_id after each command.",
            )
            msgList.append([mitCmdMsg, mitReplyMsg])
        else:
            msgList.append([mitCmdMsg])

from itertools import chain
msgList = list(chain.from_iterable(msgList))

db = can.Database(msgList, nodes, buses, version="bsr-v3.7")
can.dump_file(db, "bsr-v3.7-cansimple.dbc")
print(f"Wrote bsr-v3.7-cansimple.dbc with {len(msgList)} messages.")
