#ifndef __ODRIVE_CAN_HPP
#define __ODRIVE_CAN_HPP

#include <cmsis_os.h>

#include "canbus.hpp"
#include "can_simple.hpp"
#include <autogen/interfaces.hpp>

#define CAN_CLK_HZ (42000000)
#define CAN_CLK_MHZ (42)

// Anonymous enum for defining the most common CAN baud rates
enum {
    CAN_BAUD_125K = 125000,
    CAN_BAUD_250K = 250000,
    CAN_BAUD_500K = 500000,
    CAN_BAUD_1000K = 1000000,
    CAN_BAUD_1M = 1000000
};

class ODriveCAN : public CanBusBase, public ODriveIntf::CanIntf {
public:
    struct Config_t {
        uint32_t baud_rate = CAN_BAUD_250K;
        Protocol protocol = PROTOCOL_SIMPLE;

        ODriveCAN* parent = nullptr; // set in apply_config()
        void set_baud_rate(uint32_t value) { parent->set_baud_rate(value); }
    };

    ODriveCAN() {}

    bool apply_config();
    bool start_server(CAN_HandleTypeDef* handle);

    Error error_ = ERROR_NONE;

    Config_t config_;
    // BSR v3.7: CANSimple also gets a plain ODriveCAN* (in addition to the
    // CanBusBase* it uses for the actual bus API) so it can report
    // bus-level errors (like DUPLICATE_CAN_IDS below) directly into
    // error_ - see CANSimple::check_can_id_conflicts().
    CANSimple can_simple_{this, this};

    osThreadId thread_id_;
    const uint32_t stack_size_ = 1024;  // Bytes

    // BSR v3.7: bus health telemetry - see odrive-interface.yaml's doc on
    // ODrive.Can.tx_error_count/rx_error_count/is_bus_off for what these
    // mean. Updated once per can_server_thread() loop iteration by
    // update_bus_health(). Named with the trailing underscore so the
    // generated readonly-property accessors (see autogen/interfaces.hpp's
    // convention for e.g. Axis::step_dir_active_) find them.
    uint8_t tx_error_count_ = 0;
    uint8_t rx_error_count_ = 0;
    bool is_bus_off_ = false;

private:
    static const uint8_t kCanFifoNone = 0xff;

    // BSR v3.7: reads the STM32 bxCAN peripheral's ESR register into
    // tx_error_count_/rx_error_count_/is_bus_off_. Cheap (one register
    // read), safe to call every can_server_thread() loop iteration.
    void update_bus_health();

    struct ODriveCanSubscription : CanSubscription {
        uint8_t fifo = kCanFifoNone;
        on_can_message_cb_t callback;
        void* ctx;
    };

    bool reinit();
    void can_server_thread();
    bool set_baud_rate(uint32_t baud_rate);
    void process_rx_fifo(uint32_t fifo);
    bool send_message(const can_Message_t& message) final;
    bool subscribe(const MsgIdFilterSpecs& filter, on_can_message_cb_t callback, void* ctx, CanSubscription** handle) final;
    bool unsubscribe(CanSubscription* handle) final;

    // Hardware supports at most 28 filters unless we do optimizations. For now
    // we don't need that many.
    std::array<ODriveCanSubscription, 8> subscriptions_;
    CAN_HandleTypeDef *handle_ = nullptr;
};

#endif  // __ODRIVE_CAN_HPP
