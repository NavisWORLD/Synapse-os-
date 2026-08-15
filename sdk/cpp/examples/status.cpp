#include <iostream>
#include "synapse.hpp"

int main(int argc, char** argv) {
    const std::string path = argc > 1 ? argv[1] : "/run/synapse/status.json";
    try {
        std::cout << "ABI " << synapse::abi_version() << '\n';
        std::cout << synapse::raw_status(path) << '\n';
        std::cout << "invalid-port " << (synapse::service_reachable("127.0.0.1", 0, 5) ? "open" : "closed") << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 2;
    }
}
