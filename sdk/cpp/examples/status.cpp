#include <iostream>
#include "synapse.hpp"

int main(int argc, char** argv) {
    const std::string path = argc > 1 ? argv[1] : "/run/synapse/status.json";
    try {
        std::cout << synapse::raw_status(path) << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 2;
    }
}
