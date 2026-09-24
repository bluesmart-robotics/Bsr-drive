// BSR v3.7 fork addition.
//
// The upstream GUI (Stijn Carelsbergh, CC BY-NC 4.0) talks to the board by
// calling System.IO.Ports.SerialPort directly from dozens of call sites
// throughout Form1.cs. To add a "Demo mode" that lets someone preview the
// interface with no board attached (Antoine has no BSR v3.7 hardware on
// hand to test with), every one of those call sites is redirected through
// this small interface instead of talking to SerialPort directly.
//
// RealSerialTransport is a one-to-one wrapper around the real SerialPort -
// behavior with real hardware is unchanged.
// DemoOdriveTransport simulates just enough of the ASCII protocol
// (communication/ascii_protocol.cpp in the firmware) to answer "r <path>"
// and "w <path> <value>" the way a BSR v3.7 board would, seeded with the
// real default values from the firmware source (axis.hpp, motor.hpp,
// odrive-interface.yaml) for every property this GUI reads or writes,
// including the BSR-specific ones (PWRGD, MIT-mode, CAN bus health).

using System.Globalization;

namespace ODrive_GUI
{
    public interface IDeviceTransport
    {
        bool IsOpen { get; }
        void Open();
        void Close();
        void WriteLine(string text);
        string ReadExisting();
    }

    public class RealSerialTransport : IDeviceTransport
    {
        private readonly System.IO.Ports.SerialPort port;

        public RealSerialTransport(System.IO.Ports.SerialPort port)
        {
            this.port = port;
        }

        public bool IsOpen => port.IsOpen;
        public void Open() => port.Open();
        public void Close() => port.Close();
        public void WriteLine(string text) => port.WriteLine(text);
        public string ReadExisting() => port.ReadExisting();
    }

    // Simulates a BSR v3.7 board's ASCII (USB/UART) protocol responses in
    // memory. No real device is contacted - this exists purely so the GUI's
    // layout, labels and BSR-specific panels can be previewed and clicked
    // through without hardware. Values you "write" are held for the rest of
    // the demo session; there is no motor, no encoder and no CAN bus behind
    // this, so numbers do not evolve on their own (e.g. mit_pos_setpoint
    // will not start tracking a "real" position).
    public class DemoOdriveTransport : IDeviceTransport
    {
        private bool open;
        private string pendingResponse = "";
        private readonly Dictionary<string, string> values;

        public DemoOdriveTransport()
        {
            values = BuildDefaults();
        }

        public bool IsOpen => open;
        public void Open() => open = true;
        public void Close() => open = false;

        public void WriteLine(string text)
        {
            pendingResponse = "";
            string line = text.Trim();
            if (line.Length == 0) return;

            // "ss" (save+reboot) and "se" (erase config) - the real firmware
            // gives no useful response to either over the ASCII protocol;
            // simulate "erase" by resetting every value to its default.
            if (line == "ss") return;
            if (line == "se")
            {
                values.Clear();
                foreach (var kv in BuildDefaults()) values[kv.Key] = kv.Value;
                return;
            }

            string[] parts = line.Split(new[] { ' ' }, 3);
            if (parts.Length < 2) return;
            string verb = parts[0];
            string path = parts[1];

            if (verb == "r")
            {
                pendingResponse = values.TryGetValue(path, out var v) ? v : "0";
            }
            else if (verb == "w" && parts.Length == 3)
            {
                values[path] = parts[2].Trim();
            }
        }

        public string ReadExisting()
        {
            string response = pendingResponse;
            pendingResponse = "";
            return response;
        }

        private static Dictionary<string, string> BuildDefaults()
        {
            var d = new Dictionary<string, string>();
            void Set(string path, object value) =>
                d[path] = Convert.ToString(value, CultureInfo.InvariantCulture) ?? "0";

            // --- Top-level / board ------------------------------------------------
            Set("fw_version_revision", 5);                 // BSR v3.7 is based on fw-v0.5.5
            Set("error", 0);                                // ODriveIntf::Error - NONE
            Set("config.brake_resistance", 0.5f);
            Set("config.enable_brake_resistor", 1);

            // --- CAN bus health (BSR v3.7 custom, see CAN_SAFETY_BSR.md) -----------
            Set("can.error", 0);                            // NONE (no DUPLICATE_CAN_IDS)
            Set("can.tx_error_count", 0);
            Set("can.rx_error_count", 0);
            Set("can.is_bus_off", 0);

            // --- Per-axis ------------------------------------------------------------
            for (int i = 0; i < 2; i++)
            {
                string axis = $"axis{i}";

                Set($"{axis}.error", 0);
                Set($"{axis}.motor.error", 0);
                Set($"{axis}.encoder.error", 0);
                Set($"{axis}.controller.error", 0);

                Set($"{axis}.motor.config.motor_type", 0);          // MOTOR_TYPE_HIGH_CURRENT
                Set($"{axis}.motor.config.pole_pairs", 7);
                Set($"{axis}.motor.config.current_lim", 10);
                Set($"{axis}.motor.config.calibration_current", 10);
                Set($"{axis}.motor.config.resistance_calib_max_voltage", 4);
                Set($"{axis}.motor.config.current_control_bandwidth", 1000);
                Set($"{axis}.motor.config.torque_constant", 0.0827f);
                Set($"{axis}.motor.config.requested_current_range", 60);
                Set($"{axis}.motor.config.pre_calibrated", 0);
                Set($"{axis}.motor.config.enable_pwrgd_check", 1);  // BSR v3.7 default (motor.hpp)

                Set($"{axis}.encoder.config.mode", 0);              // ENCODER_MODE_INCREMENTAL
                Set($"{axis}.encoder.config.use_index", 0);
                Set($"{axis}.encoder.config.abs_spi_cs_gpio_pin", 1);
                Set($"{axis}.encoder.config.cpr", 4000);
                Set($"{axis}.encoder.config.calib_scan_distance", 50.0f);
                Set($"{axis}.encoder.config.calib_scan_omega", 12.566f);
                Set($"{axis}.encoder.config.bandwidth", 1000);
                Set($"{axis}.encoder.config.pre_calibrated", 0);

                Set($"{axis}.controller.config.vel_limit", 2);
                Set($"{axis}.controller.config.vel_limit_tolerance", 1.2f);
                Set($"{axis}.controller.config.control_mode", 3);   // CONTROL_MODE_POSITION_CONTROL
                Set($"{axis}.controller.config.input_mode", 1);     // INPUT_MODE_PASSTHROUGH
                Set($"{axis}.controller.config.input_filter_bandwidth", 2);
                Set($"{axis}.controller.config.pos_gain", 20);
                Set($"{axis}.controller.config.vel_gain", 0.00016f);
                Set($"{axis}.controller.config.vel_integrator_gain", 0.00032f);

                Set($"{axis}.config.startup_motor_calibration", 0);
                Set($"{axis}.config.startup_encoder_offset_calibration", 0);
                Set($"{axis}.config.startup_encoder_index_search", 0);
                Set($"{axis}.config.startup_closed_loop_control", 0);

                // BSR v3.7 custom: MIT-mode (Cheetah-style) direct CAN control.
                // Demo defaults mirror a typical E-dolly setup: axis0 = wheel
                // (MIT disabled), axis1 = damper (MIT enabled) - see axis.hpp
                // for the real firmware defaults these are copied from.
                bool isDamperAxis = i == 1;
                Set($"{axis}.config.can.enable_mit", isDamperAxis ? 1 : 0);
                Set($"{axis}.config.can.mit_can_id", isDamperAxis ? 0x410 : 0);
                Set($"{axis}.config.can.mit_reply_can_id", isDamperAxis ? 0x411 : 0);
                Set($"{axis}.config.can.mit_pos_min", -2.0f);
                Set($"{axis}.config.can.mit_pos_max", 2.0f);
                Set($"{axis}.config.can.mit_vel_min", -6.0f);
                Set($"{axis}.config.can.mit_vel_max", 6.0f);
                Set($"{axis}.config.can.mit_kp_min", 0.0f);
                Set($"{axis}.config.can.mit_kp_max", 3200.0f);
                Set($"{axis}.config.can.mit_kd_min", 0.0f);
                Set($"{axis}.config.can.mit_kd_max", 30.0f);
                Set($"{axis}.config.can.mit_torque_min", -12.0f);
                Set($"{axis}.config.can.mit_torque_max", 12.0f);

                Set($"{axis}.controller.mit_pos_setpoint", 0.0f);
                Set($"{axis}.controller.mit_vel_setpoint", 0.0f);
                Set($"{axis}.controller.mit_kp", 0.0f);
                Set($"{axis}.controller.mit_kd", 0.0f);
                Set($"{axis}.controller.mit_torque_ff", 0.0f);
            }

            return d;
        }
    }
}
