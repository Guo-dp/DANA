#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <map>
#include <iostream>
#include <memory>
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
    std::string dataset_path;
    std::string query_path;
    std::string index_root;
    std::string reordered_data_root;
    std::string nav_mode = "adaptive";
    std::string indexed_attrs_arg;
    int fixed_attr = 0;
    std::string attr_weights_arg;
    std::vector<double> attr_weights;
    std::string per_query_path;
    std::string admission_mode = "bridge";
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
    double hard_pruned_sum = 0.0;
    std::size_t insufficient = 0;
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


std::vector<unsigned> parseIndexedAttrs(const std::string &text,
                                        unsigned attr_count) {
    std::vector<unsigned> attrs;

    if (text.empty()) {
        for (unsigned attr = 0; attr < attr_count; ++attr) {
            attrs.push_back(attr);
        }
        return attrs;
    }

    std::stringstream stream(text);
    std::string token;

    while (std::getline(stream, token, ',')) {
        if (token.empty()) {
            continue;
        }

        const unsigned attr =
            static_cast<unsigned>(std::stoul(token));

        if (attr >= attr_count) {
            throw std::runtime_error("indexed_attrs contains out-of-range attribute");
        }

        if (std::find(attrs.begin(), attrs.end(), attr) ==
            attrs.end()) {
            attrs.push_back(attr);
        }
    }

    if (attrs.empty()) {
        throw std::runtime_error("indexed_attrs is empty");
    }

    return attrs;
}

std::uint64_t rankRangeWidth(const DataWrapper &data,
                             const MultiRangeQuery &query,
                             unsigned attr) {
    const auto bound = data.valueRangeToRankRange(
        attr,
        query.bounds[attr].low,
        query.bounds[attr].high);

    if (bound.first > bound.second) {
        return 0;
    }

    return static_cast<std::uint64_t>(
               bound.second - bound.first) + 1ULL;
}

std::vector<double> parseAttrWeights(const std::string &text,
                                     unsigned attr_count) {
    std::vector<double> weights(attr_count, 1.0);

    if (text.empty()) {
        return weights;
    }

    std::stringstream stream(text);
    std::string token;
    unsigned attr = 0;

    while (std::getline(stream, token, ',')) {
        if (attr >= attr_count) {
            throw std::runtime_error("attr_weights has too many values");
        }
        weights[attr++] = std::stod(token);
    }

    if (attr != attr_count) {
        throw std::runtime_error("attr_weights count does not match attr_count");
    }

    return weights;
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
        else if (arg == "-index_root") cfg.index_root = value("-index_root");
        else if (arg == "-reordered_data_root")
            cfg.reordered_data_root = value("-reordered_data_root");
        else if (arg == "-nav_mode") cfg.nav_mode = value("-nav_mode");
        else if (arg == "-indexed_attrs") cfg.indexed_attrs_arg = value("-indexed_attrs");
        else if (arg == "-fixed_attr")
            cfg.fixed_attr = std::stoi(value("-fixed_attr"));
        else if (arg == "-attr_weights")
            cfg.attr_weights_arg = value("-attr_weights");
        else if (arg == "-per_query_path")
            cfg.per_query_path = value("-per_query_path");
        else if (arg == "-admission_mode")
            cfg.admission_mode = value("-admission_mode");
        else if (arg == "-attr_path") cfg.attr_path = value("-attr_path");
        else if (arg == "-attr_count") cfg.attr_count = std::stoul(value("-attr_count"));
        else if (arg == "-filter_path") cfg.filter_path = value("-filter_path");
        else if (arg == "-query_num") cfg.query_num = std::stoi(value("-query_num"));
        else if (arg == "-query_k") cfg.query_k = std::stoi(value("-query_k"));
        else if (arg == "-search_ef") cfg.search_ef = std::stoul(value("-search_ef"));
    }

    if (cfg.dataset_path.empty() || cfg.query_path.empty() ||
        cfg.index_root.empty() || cfg.reordered_data_root.empty() ||
        cfg.attr_path.empty() || cfg.filter_path.empty()) {
        throw std::runtime_error("Required paths are missing");
    }
    cfg.attr_weights = parseAttrWeights(cfg.attr_weights_arg, cfg.attr_count);
    if (cfg.admission_mode != "bridge" &&
        cfg.admission_mode != "hard_prune") {
        throw std::runtime_error(
            "admission_mode must be bridge or hard_prune");
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

std::vector<unsigned>
readRankMapping(const std::string &path) {
    std::ifstream input(path, std::ios::binary);

    if (!input.is_open()) {
        throw std::runtime_error(
            "Cannot open rank mapping: " + path);
    }

    std::uint32_t count = 0;
    input.read(
        reinterpret_cast<char *>(&count),
        sizeof(count));

    std::vector<unsigned> mapping(count);

    input.read(
        reinterpret_cast<char *>(mapping.data()),
        sizeof(unsigned) * mapping.size());

    return mapping;
}

float squaredL2(const float *lhs,
                const float *rhs,
                std::size_t dim) {
    float result = 0.0F;

    for (std::size_t i = 0; i < dim; ++i) {
        const float difference = lhs[i] - rhs[i];
        result += difference * difference;
    }

    return result;
}

std::vector<unsigned> exactTopK(const DataWrapper &data,
                                const float *query,
                                const MultiRangeQuery &filter,
                                std::size_t k) {
    std::vector<std::pair<float, unsigned>> candidates;

    for (unsigned original_id = 0;
         original_id < static_cast<unsigned>(data.data_size);
         ++original_id) {
        if (!data.passFilter(original_id, filter)) {
            continue;
        }

        candidates.emplace_back(
            squaredL2(query, data.nodes[original_id], data.data_dim),
            original_id);
    }

    std::sort(candidates.begin(), candidates.end());

    const std::size_t result_count =
        std::min(k, candidates.size());

    std::vector<unsigned> result;
    result.reserve(result_count);

    for (std::size_t i = 0; i < result_count; ++i) {
        result.push_back(candidates[i].second);
    }

    return result;
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
              << " pruned=" << metrics.hard_pruned_sum / count
              << " insufficient=" << metrics.insufficient
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

        const auto indexed_attrs = parseIndexedAttrs(
            cfg.indexed_attrs_arg, cfg.attr_count);

        std::vector<int> attr_to_slot(cfg.attr_count, -1);

        for (std::size_t slot = 0; slot < indexed_attrs.size(); ++slot) {
            attr_to_slot[indexed_attrs[slot]] =
                static_cast<int>(slot);
        }

        std::cout << "indexed_attributes";

        for (const unsigned attr : indexed_attrs) {
            std::cout << " attr" << attr;
        }

        std::cout << "\n";

        std::vector<std::unique_ptr<DataWrapper>> ranked_data;
        std::vector<std::unique_ptr<hnswlib::L2Space>> spaces;
        std::vector<std::unique_ptr<dsg::DynamicSegmentGraph>> indexes;
        std::vector<std::vector<unsigned>> rank_to_original;

        for (const unsigned attr : indexed_attrs) {
            auto current_data = std::make_unique<DataWrapper>(
                cfg.query_num, cfg.query_k, cfg.dataset, cfg.data_size);

            std::string ranked_path =
                cfg.reordered_data_root + "/base.attr" +
                std::to_string(attr) + ".fbin";

            current_data->readData(ranked_path, query_path);

            auto current_space =
                std::make_unique<hnswlib::L2Space>(current_data->data_dim);

            auto current_index = std::make_unique<dsg::DynamicSegmentGraph>(
                current_space.get(), current_data.get());

            current_index->setSearchEf(cfg.search_ef);

            current_index->load(
                cfg.index_root + "/attr" + std::to_string(attr) + ".dsg");

            rank_to_original.push_back(
                readRankMapping(
                    cfg.reordered_data_root + "/rank_to_original.attr" +
                    std::to_string(attr) + ".ibin"));

            ranked_data.push_back(std::move(current_data));
            spaces.push_back(std::move(current_space));
            indexes.push_back(std::move(current_index));
        }

        const auto cases = readFilters(cfg.filter_path, cfg.attr_count);

        // Number of queries assigned to each navigation attribute.
        std::vector<std::size_t> selected_attr_count(
            cfg.attr_count, 0);
        
std::unordered_map<std::string, Metrics> by_profile;
        Metrics total;
        std::ofstream per_query;
        if (!cfg.per_query_path.empty()) {
            per_query.open(cfg.per_query_path);
            if (!per_query.is_open()) {
                throw std::runtime_error("Cannot open per-query output: " +
                                         cfg.per_query_path);
            }
            per_query << "query_idx,profile,nav_attr,recall,graph_ms,exact_ms,hops,dist,pruned,result_count,insufficient,span0,span1,span2" << "\n";
        }

        auto chooseIndexedNavigationAttribute =
            [&](const MultiRangeQuery &filter) -> unsigned {
                unsigned best_attr = indexed_attrs.front();
                double best_score =
                    static_cast<double>(rankRangeWidth(data, filter, best_attr)) *
                    cfg.attr_weights.at(best_attr);

                for (const unsigned attr : indexed_attrs) {
                    const double score =
                        static_cast<double>(rankRangeWidth(data, filter, attr)) *
                        cfg.attr_weights.at(attr);

                    if (score < best_score) {
                        best_score = score;
                        best_attr = attr;
                    }
                }

                return best_attr;
            };

        for (const auto &test : cases) {
            if (test.query_idx >= data.querys.size()) {
                continue;
            }
            const float *query = data.querys.at(test.query_idx);

            const auto exact_start = std::chrono::steady_clock::now();
            const auto exact = exactTopK(
                data, query, test.filter,
                static_cast<std::size_t>(cfg.query_k));
            const auto exact_end = std::chrono::steady_clock::now();

            unsigned navigation_attr = 0;

            if (cfg.nav_mode == "adaptive" ||
                cfg.nav_mode == "weighted") {
                navigation_attr =
                    chooseIndexedNavigationAttribute(test.filter);
            } else {
                navigation_attr = static_cast<unsigned>(cfg.fixed_attr);
            }

            if (navigation_attr >= selected_attr_count.size()) {
                throw std::runtime_error(
                    "Navigation attribute is out of range");
            }
            ++selected_attr_count[navigation_attr];

            const int navigation_slot =
                navigation_attr < attr_to_slot.size()
                    ? attr_to_slot[navigation_attr]
                    : -1;

            if (navigation_slot < 0) {
                throw std::runtime_error(
                    "navigation attribute is not indexed");
            }

            const auto rank_bound = data.valueRangeToRankRange(
                navigation_attr,
                test.filter.bounds[navigation_attr].low,
                test.filter.bounds[navigation_attr].high);

            std::vector<unsigned> graph;

            const auto graph_start = std::chrono::steady_clock::now();

            if (rank_bound.first <= rank_bound.second) {
                auto &selected_index = *indexes[static_cast<std::size_t>(navigation_slot)];

                selected_index.setSearchEf(cfg.search_ef);
                selected_index.setQueryTopK(
                    static_cast<unsigned>(cfg.query_k));

                selected_index.rangeSearchDana(
                    query,
                    {static_cast<int>(rank_bound.first),
                     static_cast<int>(rank_bound.second)},
                    test.filter,
                    &data,
                    rank_to_original[static_cast<std::size_t>(navigation_slot)],
                    cfg.admission_mode == "hard_prune");

                graph = selected_index.returned_nns;
            }

            const auto graph_end = std::chrono::steady_clock::now();

            const double exact_seconds =
                std::chrono::duration<double>(exact_end - exact_start).count();
            const double graph_seconds =
                std::chrono::duration<double>(graph_end - graph_start).count();
            const double recall = recallAtK(
                exact, graph, static_cast<std::size_t>(cfg.query_k));

            auto update = [&](Metrics &metrics) {
                ++metrics.queries;
                metrics.recall_sum += recall;
                metrics.graph_seconds += graph_seconds;
                metrics.exact_seconds += exact_seconds;
                metrics.hops_sum += static_cast<double>(
                    indexes[static_cast<std::size_t>(navigation_slot)]->last_hop_count());
                metrics.distance_sum += static_cast<double>(
                    indexes[static_cast<std::size_t>(navigation_slot)]->last_distance_eval_count());
                metrics.hard_pruned_sum += static_cast<double>(
                    indexes[static_cast<std::size_t>(navigation_slot)]->last_hard_pruned_count());
                if (graph.size() < static_cast<std::size_t>(cfg.query_k) &&
                    exact.size() >= static_cast<std::size_t>(cfg.query_k)) {
                    ++metrics.insufficient;
                }
            };
            update(by_profile[test.profile]);
            update(total);

            if (per_query.is_open()) {
                per_query << test.query_idx << ","
                          << test.profile << ","
                          << navigation_attr << ","
                          << std::setprecision(8) << recall << ","
                          << graph_seconds * 1000.0 << ","
                          << exact_seconds * 1000.0 << ","
                          << indexes[static_cast<std::size_t>(navigation_slot)]->last_hop_count() << ","
                          << indexes[static_cast<std::size_t>(navigation_slot)]->last_distance_eval_count() << ","
                          << indexes[static_cast<std::size_t>(navigation_slot)]->last_hard_pruned_count() << ","
                          << graph.size() << ","
                          << ((graph.size() < static_cast<std::size_t>(cfg.query_k) &&
                               exact.size() >= static_cast<std::size_t>(cfg.query_k)) ? 1 : 0);
                for (unsigned attr = 0; attr < cfg.attr_count; ++attr) {
                    per_query << "," << rankRangeWidth(data, test.filter, attr);
                }
                per_query << "\n";
            }
        }

        std::cout << "selected_attributes";
        for (std::size_t attr = 0;
             attr < selected_attr_count.size();
             ++attr) {
            std::cout << " attr" << attr
                      << "=" << selected_attr_count[attr];
        }
        std::cout << "\n";

        std::cout << "search_ef=" << cfg.search_ef
                  << " nav_mode=" << cfg.nav_mode
                  << " admission_mode=" << cfg.admission_mode;
        if (cfg.nav_mode == "fixed") {
            std::cout << " fixed_attr=" << cfg.fixed_attr;
        }
        std::cout << "\n";

        for (const std::string profile : {
                 "narrow",
                 "medium",
                 "mixed",
                 "broad",
                 "attr0_narrow",
                 "attr1_narrow",
                 "attr2_narrow"}) {
            printMetrics(profile, by_profile[profile]);
        }
        printMetrics("balanced", by_profile["balanced"]);
        {
            std::map<std::string, Metrics> ordered_profiles(
                by_profile.begin(), by_profile.end());

            for (const auto &entry : ordered_profiles) {
                printMetrics(entry.first, entry.second);
            }
        }

        printMetrics("all", total);
    } catch (const std::exception &error) {
        std::cerr << "query_dana_benchmark failed: "
                  << error.what() << "\n";
        return 1;
    }
    return 0;
}
