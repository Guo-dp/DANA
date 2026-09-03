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
#include "filter_query.h"

namespace {

struct Config {
    int data_size = 100000;
    int query_num = 300;
    int query_k = 10;
    unsigned attr_count = 3;
    unsigned search_ef = 64;
    unsigned candidate_k = 64;

    std::string dataset = "multiattr_100k_balanced";
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
    double raw_sum = 0.0;
    double passed_sum = 0.0;
    std::size_t insufficient = 0;
};


class MultiAttributeFilter final
    : public hnswlib::BaseFilterFunctor {
public:
    MultiAttributeFilter(
        const DataWrapper &data,
        const MultiRangeQuery &query)
        : data_(data), query_(query) {}

    bool operator()(hnswlib::labeltype label) override {
        if (label >=
            static_cast<hnswlib::labeltype>(
                data_.data_size)) {
            return false;
        }

        return data_.passFilter(
            static_cast<unsigned>(label),
            query_);
    }

private:
    const DataWrapper &data_;
    const MultiRangeQuery &query_;
};

std::vector<std::string> splitComma(
    const std::string &line) {
    std::vector<std::string> columns;
    std::stringstream stream(line);
    std::string value;

    while (std::getline(stream, value, ',')) {
        columns.push_back(value);
    }

    return columns;
}

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
        else if (arg == "-attr_path")
            cfg.attr_path = value("-attr_path");
        else if (arg == "-attr_count")
            cfg.attr_count = std::stoul(value("-attr_count"));
        else if (arg == "-filter_path")
            cfg.filter_path = value("-filter_path");
        else if (arg == "-query_num")
            cfg.query_num = std::stoi(value("-query_num"));
        else if (arg == "-query_k")
            cfg.query_k = std::stoi(value("-query_k"));
        else if (arg == "-search_ef")
            cfg.search_ef = std::stoul(value("-search_ef"));
        else if (arg == "-candidate_k")
            cfg.candidate_k = std::stoul(value("-candidate_k"));
    }

    if (cfg.dataset_path.empty() ||
        cfg.query_path.empty() ||
        cfg.index_path.empty() ||
        cfg.attr_path.empty() ||
        cfg.filter_path.empty()) {
        throw std::runtime_error("Required paths are missing");
    }

    cfg.search_ef =
        std::max(cfg.search_ef, cfg.candidate_k);

    return cfg;
}

std::vector<FilterCase> readFilters(
    const std::string &path,
    unsigned attr_count) {
    std::ifstream input(path);

    if (!input.is_open()) {
        throw std::runtime_error(
            "Cannot open filter file: " + path);
    }

    std::vector<FilterCase> result;
    std::string line;
    bool first = true;

    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }

        if (first) {
            first = false;
            if (line.find("query_idx") !=
                std::string::npos) {
                continue;
            }
        }

        const auto columns = splitComma(line);
        const std::size_t required =
            3 + static_cast<std::size_t>(attr_count) * 2;

        if (columns.size() < required) {
            throw std::runtime_error(
                "Malformed filter row: " + line);
        }

        FilterCase current;
        current.query_idx = std::stoul(columns[0]);
        current.profile = columns[1];
        current.filter.primary_attr =
            std::stoul(columns[2]);
        current.filter.bounds.resize(attr_count);

        std::size_t position = 3;

        for (unsigned attr = 0;
             attr < attr_count;
             ++attr) {
            current.filter.bounds[attr].low =
                std::stof(columns[position++]);
            current.filter.bounds[attr].high =
                std::stof(columns[position++]);
        }

        result.push_back(std::move(current));
    }

    return result;
}

float squaredL2(const float *left,
                const float *right,
                std::size_t dim) {
    float distance = 0.0F;

    for (std::size_t i = 0; i < dim; ++i) {
        const float difference = left[i] - right[i];
        distance += difference * difference;
    }

    return distance;
}

std::vector<unsigned> exactTopK(
    const DataWrapper &data,
    const float *query,
    const MultiRangeQuery &filter,
    std::size_t k) {
    std::vector<std::pair<float, unsigned>> candidates;

    for (unsigned id = 0;
         id < static_cast<unsigned>(data.data_size);
         ++id) {
        if (!data.passFilter(id, filter)) {
            continue;
        }

        candidates.emplace_back(
            squaredL2(query, data.nodes[id], data.data_dim),
            id);
    }

    std::sort(candidates.begin(), candidates.end());

    std::vector<unsigned> result;
    const std::size_t count =
        std::min(k, candidates.size());

    result.reserve(count);

    for (std::size_t i = 0; i < count; ++i) {
        result.push_back(candidates[i].second);
    }

    return result;
}

double recallAtK(const std::vector<unsigned> &exact,
                 const std::vector<unsigned> &actual,
                 std::size_t k) {
    const std::size_t denominator =
        std::min(k, exact.size());

    if (denominator == 0) {
        return 1.0;
    }

    std::size_t matches = 0;

    for (std::size_t i = 0;
         i < std::min(k, actual.size());
         ++i) {
        if (std::find(
                exact.begin(),
                exact.begin() + denominator,
                actual[i]) !=
            exact.begin() + denominator) {
            ++matches;
        }
    }

    return static_cast<double>(matches) /
           static_cast<double>(denominator);
}

void printMetrics(const std::string &name,
                  const Metrics &metrics) {
    if (metrics.queries == 0) {
        return;
    }

    const double count =
        static_cast<double>(metrics.queries);

    const double qps =
        metrics.graph_seconds > 0.0
            ? count / metrics.graph_seconds
            : 0.0;

    std::cout
        << std::left << std::setw(13) << name
        << " queries=" << metrics.queries
        << " recall=" << std::fixed << std::setprecision(4)
        << metrics.recall_sum / count
        << " graph_ms="
        << metrics.graph_seconds * 1000.0 / count
        << " exact_ms="
        << metrics.exact_seconds * 1000.0 / count
        << " qps=" << qps
        << " hops=" << metrics.hops_sum / count
        << " dist=" << metrics.distance_sum / count
        << " raw=" << metrics.raw_sum / count
        << " passed=" << metrics.passed_sum / count
        << " insufficient=" << metrics.insufficient
        << "\n";
}

} // namespace

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
        data.readAttributes(cfg.attr_path, cfg.attr_count);

        hnswlib::L2Space space(data.data_dim);

        hnswlib::HierarchicalNSW<float> index(
            &space,
            cfg.index_path);

        index.setEf(cfg.search_ef);

        const auto cases =
            readFilters(cfg.filter_path, cfg.attr_count);

        std::unordered_map<std::string, Metrics> by_profile;
        std::vector<std::string> profile_order;
        Metrics total;

        for (const auto &test : cases) {
            if (test.query_idx >= data.querys.size()) {
                continue;
            }

            if (by_profile.find(test.profile) ==
                by_profile.end()) {
                profile_order.push_back(test.profile);
            }

            const float *query =
                data.querys.at(test.query_idx);

            const auto exact_start =
                std::chrono::steady_clock::now();

            const auto exact = exactTopK(
                data,
                query,
                test.filter,
                static_cast<std::size_t>(cfg.query_k));

            const auto exact_end =
                std::chrono::steady_clock::now();

            const long hops_before =
                index.metric_hops.load();
            const long dist_before =
                index.metric_distance_computations.load();

            const auto graph_start =
                std::chrono::steady_clock::now();

            MultiAttributeFilter allowed(
                data, test.filter);

            auto candidates =
                index.searchKnn(
                    query,
                    static_cast<std::size_t>(cfg.query_k),
                    &allowed);

            std::vector<std::pair<float, unsigned>> passed;
            const std::size_t raw_count = candidates.size();
            passed.reserve(raw_count);

            while (!candidates.empty()) {
                const auto current = candidates.top();
                candidates.pop();

                passed.emplace_back(
                    current.first,
                    static_cast<unsigned>(current.second));
            }

            std::sort(passed.begin(), passed.end());

            std::vector<unsigned> actual;
            const std::size_t result_count =
                std::min(
                    static_cast<std::size_t>(cfg.query_k),
                    passed.size());

            actual.reserve(result_count);

            for (std::size_t i = 0;
                 i < result_count;
                 ++i) {
                actual.push_back(passed[i].second);
            }

            const auto graph_end =
                std::chrono::steady_clock::now();

            const long query_hops =
                index.metric_hops.load() - hops_before;
            const long query_dist =
                index.metric_distance_computations.load() -
                dist_before;

            const double recall = recallAtK(
                exact,
                actual,
                static_cast<std::size_t>(cfg.query_k));

            const double exact_seconds =
                std::chrono::duration<double>(
                    exact_end - exact_start).count();

            const double graph_seconds =
                std::chrono::duration<double>(
                    graph_end - graph_start).count();

            auto update = [&](Metrics &metrics) {
                ++metrics.queries;
                metrics.recall_sum += recall;
                metrics.graph_seconds += graph_seconds;
                metrics.exact_seconds += exact_seconds;
                metrics.hops_sum += query_hops;
                metrics.distance_sum += query_dist;
                metrics.raw_sum += raw_count;
                metrics.passed_sum += passed.size();

                if (passed.size() <
                    static_cast<std::size_t>(cfg.query_k)) {
                    ++metrics.insufficient;
                }
            };

            update(by_profile[test.profile]);
            update(total);
        }

        std::cout
            << "search_ef=" << cfg.search_ef
            << " mode=in-search-filter"
            << "\n";

        for (const auto &profile : profile_order) {
            printMetrics(profile, by_profile[profile]);
        }

        printMetrics("all", total);
    } catch (const std::exception &error) {
        std::cerr
            << "query_hnsw_insearch_benchmark failed: "
            << error.what() << "\n";
        return 1;
    }

    return 0;
}
