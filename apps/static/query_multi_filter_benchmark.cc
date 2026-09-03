#include <algorithm>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "base_hnsw/hnswlib.h"
#include "data_wrapper.h"
#include "dsg.h"
#include "filter_query.h"

namespace {

struct Config {
    std::string dataset = "multiattr_10k";
    int data_size = 10000;
    int query_num = 100;
    int query_k = 10;
    unsigned search_ef = 64;
    unsigned attr_count = 3;
    unsigned primary_attr = 0;
    std::string dataset_path;
    std::string query_path;
    std::string index_path;
    std::string attr_path;
    std::string filter_path;
};

struct FilterCase {
    unsigned query_idx = 0;
    std::string profile;
    MultiRangeQuery filter;
};

struct Metrics {
    std::size_t queries = 0;
    double recall_sum = 0.0;
    double graph_seconds = 0.0;
    double exact_seconds = 0.0;
    double hops_sum = 0.0;
    double distance_sum = 0.0;
};

std::vector<std::string> splitComma(const std::string &line) {
    std::vector<std::string> columns;
    std::stringstream stream(line);
    std::string column;
    while (std::getline(stream, column, ',')) {
        columns.push_back(column);
    }
    return columns;
}

Config parseArgs(int argc, char **argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto value = [&](const char *flag) -> const char * {
            if (i + 1 >= argc) {
                throw std::runtime_error(std::string("Missing value for ") + flag);
            }
            return argv[++i];
        };

        if (arg == "-dataset") cfg.dataset = value("-dataset");
        else if (arg == "-N") cfg.data_size = std::stoi(value("-N"));
        else if (arg == "-dataset_path") cfg.dataset_path = value("-dataset_path");
        else if (arg == "-query_path") cfg.query_path = value("-query_path");
        else if (arg == "-index_path") cfg.index_path = value("-index_path");
        else if (arg == "-attr_path") cfg.attr_path = value("-attr_path");
        else if (arg == "-attr_count") cfg.attr_count = std::stoul(value("-attr_count"));
        else if (arg == "-primary_attr") cfg.primary_attr = std::stoul(value("-primary_attr"));
        else if (arg == "-filter_path") cfg.filter_path = value("-filter_path");
        else if (arg == "-query_num") cfg.query_num = std::stoi(value("-query_num"));
        else if (arg == "-query_k") cfg.query_k = std::stoi(value("-query_k"));
        else if (arg == "-search_ef") cfg.search_ef = std::stoul(value("-search_ef"));
    }

    if (cfg.dataset_path.empty() || cfg.query_path.empty() || cfg.index_path.empty() ||
        cfg.attr_path.empty() || cfg.filter_path.empty()) {
        throw std::runtime_error("dataset/query/index/attr/filter paths are required.");
    }
    return cfg;
}

std::vector<FilterCase> readFilters(const std::string &path, unsigned attr_count) {
    std::ifstream input(path);
    if (!input.is_open()) {
        throw std::runtime_error("Cannot open filter file: " + path);
    }

    std::vector<FilterCase> cases;
    std::string line;
    bool first = true;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        if (first) {
            first = false;
            if (line.find("query_idx") != std::string::npos) {
                continue;
            }
        }

        const auto columns = splitComma(line);
        const std::size_t minimum_columns =
            3 + static_cast<std::size_t>(attr_count) * 2;
        if (columns.size() < minimum_columns) {
            throw std::runtime_error("Malformed filter row: " + line);
        }

        FilterCase current;
        current.query_idx = std::stoul(columns[0]);
        current.profile = columns[1];
        current.filter.primary_attr = std::stoul(columns[2]);
        current.filter.bounds.resize(attr_count);

        std::size_t position = 3;
        for (unsigned attr = 0; attr < attr_count; ++attr) {
            current.filter.bounds[attr].low = std::stof(columns[position++]);
            current.filter.bounds[attr].high = std::stof(columns[position++]);
        }
        cases.push_back(std::move(current));
    }
    return cases;
}

double recallAtK(const std::vector<unsigned> &exact,
                 const std::vector<unsigned> &graph,
                 std::size_t k) {
    const std::size_t denominator = std::min(k, exact.size());
    if (denominator == 0) {
        return 1.0;
    }

    std::size_t matches = 0;
    const std::size_t graph_limit = std::min(k, graph.size());
    for (std::size_t i = 0; i < graph_limit; ++i) {
        if (std::find(exact.begin(), exact.begin() + denominator, graph[i]) !=
            exact.begin() + denominator) {
            ++matches;
        }
    }
    return static_cast<double>(matches) / static_cast<double>(denominator);
}

void printMetrics(const std::string &name, const Metrics &metrics) {
    if (metrics.queries == 0) {
        return;
    }
    const double count = static_cast<double>(metrics.queries);
    const double qps =
        metrics.graph_seconds > 0.0 ? count / metrics.graph_seconds : 0.0;

    std::cout << std::left << std::setw(10) << name
              << " queries=" << metrics.queries
              << " recall=" << std::fixed << std::setprecision(4)
              << metrics.recall_sum / count
              << " graph_ms=" << metrics.graph_seconds * 1000.0 / count
              << " exact_ms=" << metrics.exact_seconds * 1000.0 / count
              << " qps=" << qps
              << " hops=" << metrics.hops_sum / count
              << " dist=" << metrics.distance_sum / count
              << "\n";
}

} // namespace

int main(int argc, char **argv) {
    try {
        const Config cfg = parseArgs(argc, argv);

        DataWrapper data(cfg.query_num, cfg.query_k, cfg.dataset, cfg.data_size);
        std::string dataset_path = cfg.dataset_path;
        std::string query_path = cfg.query_path;
        data.readData(dataset_path, query_path);
        data.readAttributes(cfg.attr_path, cfg.attr_count);
        data.setPrimaryAttribute(cfg.primary_attr);

        hnswlib::L2Space space(data.data_dim);
        dsg::DynamicSegmentGraph index(&space, &data);
        index.setQueryTopK(static_cast<unsigned>(cfg.query_k));
        index.setSearchEf(cfg.search_ef);
        index.load(cfg.index_path);

        const auto cases = readFilters(cfg.filter_path, cfg.attr_count);
        std::unordered_map<std::string, Metrics> by_profile;
        Metrics total;

        for (const auto &test : cases) {
            if (test.query_idx >= data.querys.size()) {
                continue;
            }
            const float *query = data.querys.at(test.query_idx);

            const auto exact_start = std::chrono::steady_clock::now();
            index.rangeSearchMultiExact(query, test.filter);
            const auto exact_end = std::chrono::steady_clock::now();
            const auto exact = index.returned_nns;

            index.setSearchEf(cfg.search_ef);
            index.setQueryTopK(static_cast<unsigned>(cfg.query_k));
            const auto graph_start = std::chrono::steady_clock::now();
            index.rangeSearch(query, test.filter);
            const auto graph_end = std::chrono::steady_clock::now();
            const auto graph = index.returned_nns;

            const double exact_seconds =
                std::chrono::duration<double>(exact_end - exact_start).count();
            const double graph_seconds =
                std::chrono::duration<double>(graph_end - graph_start).count();
            const double recall =
                recallAtK(exact, graph, static_cast<std::size_t>(cfg.query_k));

            auto update = [&](Metrics &metrics) {
                ++metrics.queries;
                metrics.recall_sum += recall;
                metrics.graph_seconds += graph_seconds;
                metrics.exact_seconds += exact_seconds;
                metrics.hops_sum += static_cast<double>(index.last_hop_count());
                metrics.distance_sum +=
                    static_cast<double>(index.last_distance_eval_count());
            };
            update(by_profile[test.profile]);
            update(total);
        }

        std::cout << "search_ef=" << cfg.search_ef << "\n";
        for (const std::string profile : {"narrow", "medium", "mixed", "broad"}) {
            printMetrics(profile, by_profile[profile]);
        }
        printMetrics("all", total);
    } catch (const std::exception &error) {
        std::cerr << "query_multi_filter_benchmark failed: "
                  << error.what() << "\n";
        return 1;
    }
    return 0;
}
