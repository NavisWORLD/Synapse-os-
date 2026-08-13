#pragma once
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace synapse {
inline std::string raw_status(const std::string& path = "/run/synapse/status.json") {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("unable to open Synapse status: " + path);
    std::ostringstream buf;
    buf << in.rdbuf();
    return buf.str();
}
}
