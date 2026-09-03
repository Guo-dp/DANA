#include <chrono>
#include <iostream>
#include <stdexcept>
#include <string>

#include "base_hnsw/hnswlib.h"
#include "data_wrapper.h"

struct Config {
    int data_size = 100000;
    int query_num = 1;
    int query_k = 10;
    unsigned M = 16;
    unsigned ef_construction = 200;
    unsigned seed = 2028;
    std::string dataset = "multiattr";
    std::string dataset_path;
    std::string query_path;
    std::string index_path;
};

Config parseArgs(int argc, char **argv) {
    Config cfg;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];

        auto value = [&](const char *flag) {
            if (i + 1 >= argc) {
                throw std::runtime_error(
                    std::string("Missing value for ") + flag);
            }
            return argv[++i];
        };

        if (arg == "-dataset")
            cfg.dataset = value("-dataset");
        else if (arg == "-N")
            cfg.data_size = std::stoi(value("-N"));
        else if (arg == "-dataset_path")
            cfg.dataset_path = value("-dataset_path");
        else if (arg == "-query_path")
            cfg.query_path = value("-query_path");
        else if (arg == "-index_path")
            cfg.index_path = value("-index_path");
        else if (arg == "-M")
            cfg.M = std::stoul(value("-M"));
        else if (arg == "-ef_construction")
            cfg.ef_construction =
                std::stoul(value("-ef_construction"));
        else if (arg == "-seed")
            cfg.seed = std::stoul(value("-seed"));
    }

    if (cfg.dataset_path.empty() ||
        cfg.query_path.empty() ||
        cfg.index_path.empty()) {
        throw std::runtime_error(
            "dataset_path, query_path and index_path are required");
    }

    return cfg;
}

int main(int argc, char **argv) {
    try {
        const Config cfg = parseArgs(argc, argv);

        DataWrapper data(
            cfg.query_num,
            cfg.query_k,
            cfg.dataset,
            cfg.data_size);

        std::string dataset_path = cfg.dataset_path;
        std::string query_path = cfg.query_path;
        data.readData(dataset_path, query_path);

        hnswlib::L2Space space(data.data_dim);

        hnswlib::HierarchicalNSW<float> index(
            &space,
            static_cast<std::size_t>(cfg.data_size),
            cfg.M,
            cfg.ef_construction,
            cfg.seed);

        const auto start = std::chrono::steady_clock::now();

        for (unsigned id = 0;
             id < static_cast<unsigned>(cfg.data_size);
             ++id) {
            index.addPoint(data.nodes[id], id);
        }

        const auto end = std::chrono::steady_clock::now();

        index.saveIndex(cfg.index_path);

        std::cout
            << "HNSW build_seconds="
            << std::chrono::duration<double>(end - start).count()
            << " N=" << cfg.data_size
            << " M=" << cfg.M
            << " ef_construction=" << cfg.ef_construction
            << " index_bytes=" << index.indexFileSize()
            << "\n";

        std::cout << "Saved HNSW index to "
                  << cfg.index_path << "\n";
    } catch (const std::exception &error) {
        std::cerr << "build_hnsw_index failed: "
                  << error.what() << "\n";
        return 1;
    }

    return 0;
}
