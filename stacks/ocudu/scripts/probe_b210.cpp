#include <uhd/device.hpp>
#include <uhd/usrp/multi_usrp.hpp>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <stdexcept>

int main()
{
    try {
        const auto devices = uhd::device::find(uhd::device_addr_t("type=b200"));
        if (devices.size() != 1) throw std::runtime_error("Exactly one B200-family device is required");
        const auto serial = devices.front().get("serial", std::string());
        if (serial.empty() || !std::all_of(serial.begin(), serial.end(), [](unsigned char c) { return std::isalnum(c); }))
            throw std::runtime_error("Invalid UHD serial");
        const auto radio = uhd::usrp::multi_usrp::make(devices.front());
        if (radio->get_mboard_name() != "B210") throw std::runtime_error("Selected radio is not a B210");
        const auto rx = radio->get_rx_gain_range(0);
        const auto tx = radio->get_tx_gain_range(0);
        std::cout << "AOC_PROBE_JSON={\"serial\":\"" << serial << "\",\"model\":\"B210\","
                  << "\"rx_min\":" << rx.start() << ",\"rx_max\":" << rx.stop()
                  << ",\"tx_min\":" << tx.start() << ",\"tx_max\":" << tx.stop() << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
