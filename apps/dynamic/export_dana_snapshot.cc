#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "dynamic_dana.h"

namespace fs = std::filesystem;

void writeFbin(
    const fs::path &path,
    const std::vector<
        dsg::DynamicDanaIndex::SnapshotPoint> &points,
    std::size_t dim) {

    std::ofstream output(
        path,
        std::ios::binary | std::ios::trunc);

    const std::uint32_t count =
        static_cast<std::uint32_t>(points.size());

    const std::uint32_t dimension =
        static_cast<std::uint32_t>(dim);

    output.write(
        reinterpret_cast<const char *>(&count),
        sizeof(count));

    output.write(
        reinterpret_cast<const char *>(&dimension),
        sizeof(dimension));

    for (const auto &point : points) {
        output.write(
            reinterpret_cast<const char *>(
                point.vector.data()),
            sizeof(float) * dim);
    }
}

void writeAttributes(
    const fs::path &path,
    const std::vector<
        dsg::DynamicDanaIndex::SnapshotPoint> &points) {

    std::ofstream output(path);

    for (std::size_t local_id = 0;
         local_id < points.size();
         ++local_id) {
        output << local_id;

        for (const float value :
             points[local_id].attrs) {
            output << "," << value;
        }

        output << "\n";
    }
}

void writeStableIds(
    const fs::path &path,
    const std::vector<
        dsg::DynamicDanaIndex::SnapshotPoint> &points) {

    std::ofstream output(
        path,
        std::ios::binary | std::ios::trunc);

    const std::uint32_t count =
        static_cast<std::uint32_t>(points.size());

    output.write(
        reinterpret_cast<const char *>(&count),
        sizeof(count));

    for (const auto &point : points) {
        output.write(
            reinterpret_cast<const char *>(
                &point.original_id),
            sizeof(point.original_id));
    }
}

int main() {
    std::cerr
        << "This utility provides snapshot writers. "
        << "Call them from the dynamic rebuild driver.\n";

    return 0;
}
