#pragma once

#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace dsg {

// Legacy snapshots are queryable, but their deleted-ID allocation history is lost.
inline std::uint64_t readSnapshotNextOriginalId(
    const std::string &path, bool allow_legacy = false) {
    std::ifstream input(path);
    std::string line;
    const std::string prefix = "next_original_id=";
    while (std::getline(input, line)) {
        if (line.compare(0, prefix.size(), prefix) != 0) {
            continue;
        }
        const std::string value = line.substr(prefix.size());
        if (value.empty() || value.find_first_not_of("0123456789\r") !=
                                 std::string::npos) {
            throw std::runtime_error("Invalid snapshot ID high-water mark");
        }
        std::size_t consumed = 0;
        const auto next_id = std::stoull(value, &consumed);
        if (consumed < value.size() && value.substr(consumed) != "\r") {
            throw std::runtime_error("Invalid snapshot ID high-water mark");
        }
        if (next_id > static_cast<std::uint64_t>(
                          std::numeric_limits<unsigned>::max()) + 1) {
            throw std::runtime_error("Snapshot ID high-water mark is out of range");
        }
        return next_id;
    }
    if (allow_legacy) {
        std::cerr << "Legacy snapshot lacks next_original_id; safe allocation "
                     "after deleted IDs requires the saved high-water mark.\n";
        return 0;
    }
    throw std::runtime_error("Snapshot lacks next_original_id: " + path);
}

} // namespace dsg
