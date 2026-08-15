#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" {
#include "synapse/synapse.h"
}

namespace synapse {
inline std::string raw_status(const std::string& path = "/run/synapse/status.json") {
    std::size_t needed = 0;
    int rc = synapse_status_read(path.c_str(), nullptr, 0, &needed);
    if (rc != SYNAPSE_OK) {
        throw std::runtime_error(std::string("unable to read Synapse status: ") + synapse_result_string(rc));
    }
    std::vector<char> buffer(needed);
    rc = synapse_status_read(path.c_str(), buffer.data(), buffer.size(), &needed);
    if (rc != SYNAPSE_OK) {
        throw std::runtime_error(std::string("unable to read Synapse status: ") + synapse_result_string(rc));
    }
    return std::string(buffer.data());
}

inline bool service_reachable(const std::string& host, std::uint16_t port, std::uint32_t timeout_ms = 200) {
    return synapse_service_reachable(host.c_str(), port, timeout_ms) == 1;
}

inline std::uint32_t abi_version() noexcept {
    return synapse_abi_version();
}
}
