#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "base_hnsw/hnswlib.h"
#include "data_wrapper.h"
#include "dsg.h"
#include "dynamic_multi_dsg.h"
#include "filter_query.h"

namespace {

struct Config {
    std::string dataset = "multiattr_100k_independent";
    std::string dataset_path;
    std::string query_path;
    std::string attr_path;
    std::string filter_path;
    std::string index_root;
    std::string reordered_data_root;

    int data_size = 100000;
    int query_num = 300;
    int query_k = 10;

    unsigned attr_count = 3;
    unsigned search_ef = 512;
    unsigned eval_queries = 100;

    unsigned insert_count = 100;
    unsigned update_count = 100;
    unsigned delete_count = 100;

    unsigned seed = 2030;
    double rebuild_fraction = 0.05;
    std::string snapshot_dir;
    bool audit_correctness = false;
};

struct FilterCase {
    unsigned query_idx = 0;
    MultiRangeQuery filter;
};

struct EvalResult {
    double recall = 0.0;
    double approximate_ms = 0.0;
    double exact_ms = 0.0;
    double delta_scanned = 0.0;
    double base_candidates = 0.0;
    double base_search_ms = 0.0;
    double delta_scan_ms = 0.0;
    double merge_ms = 0.0;
    std::size_t queries = 0;
    std::size_t audited_results = 0;
    std::size_t stale_version_violations = 0;
    std::size_t deleted_id_violations = 0;
    std::size_t duplicate_id_violations = 0;
    std::size_t predicate_violations = 0;
    std::size_t invalid_id_violations = 0;
    std::size_t inserted_visibility_violations = 0;
    std::size_t updated_visibility_violations = 0;
    std::size_t deleted_visibility_violations = 0;
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
        else if (arg == "-attr_path")
            cfg.attr_path = value("-attr_path");
        else if (arg == "-filter_path")
            cfg.filter_path = value("-filter_path");
        else if (arg == "-index_root")
            cfg.index_root = value("-index_root");
        else if (arg == "-reordered_data_root")
            cfg.reordered_data_root =
                value("-reordered_data_root");
        else if (arg == "-attr_count")
            cfg.attr_count =
                std::stoul(value("-attr_count"));
        else if (arg == "-query_num")
            cfg.query_num =
                std::stoi(value("-query_num"));
        else if (arg == "-query_k")
            cfg.query_k =
                std::stoi(value("-query_k"));
        else if (arg == "-search_ef")
            cfg.search_ef =
                std::stoul(value("-search_ef"));
        else if (arg == "-eval_queries")
            cfg.eval_queries =
                std::stoul(value("-eval_queries"));
        else if (arg == "-insert_count")
            cfg.insert_count =
                std::stoul(value("-insert_count"));
        else if (arg == "-update_count")
            cfg.update_count =
                std::stoul(value("-update_count"));
        else if (arg == "-delete_count")
            cfg.delete_count =
                std::stoul(value("-delete_count"));
        else if (arg == "-seed")
            cfg.seed = std::stoul(value("-seed"));
        else if (arg == "-rebuild_fraction")
            cfg.rebuild_fraction =
                std::stod(value("-rebuild_fraction"));
        else if (arg == "-snapshot_dir")
            cfg.snapshot_dir = value("-snapshot_dir");
        else if (arg == "-audit_correctness")
            cfg.audit_correctness =
                std::stoul(value("-audit_correctness")) != 0;
    }

    if (cfg.dataset_path.empty() ||
        cfg.query_path.empty() ||
        cfg.attr_path.empty() ||
        cfg.filter_path.empty() ||
        cfg.index_root.empty() ||
        cfg.reordered_data_root.empty()) {
        throw std::runtime_error(
            "Required paths are missing");
    }

    return cfg;
}

std::vector<std::string> splitComma(
    const std::string &line) {
    std::vector<std::string> values;
    std::stringstream stream(line);
    std::string value;

    while (std::getline(stream, value, ',')) {
        values.push_back(value);
    }

    return values;
}

std::vector<FilterCase> readFilters(
    const std::string &path,
    unsigned attr_count) {

    std::ifstream input(path);

    if (!input.is_open()) {
        throw std::runtime_error(
            "Cannot open filters: " + path);
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

        if (columns.size() <
            3 + static_cast<std::size_t>(
                    attr_count) * 2) {
            throw std::runtime_error(
                "Malformed filter row");
        }

        FilterCase current;
        current.query_idx =
            std::stoul(columns[0]);

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

std::vector<unsigned> readRankMapping(
    const std::string &path) {

    std::ifstream input(path, std::ios::binary);

    if (!input.is_open()) {
        throw std::runtime_error(
            "Cannot open mapping: " + path);
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

double recallAtK(
    const std::vector<unsigned> &exact,
    const std::vector<unsigned> &actual,
    unsigned k) {

    const std::size_t denominator =
        std::min<std::size_t>(k, exact.size());

    if (denominator == 0) {
        return 1.0;
    }

    std::size_t matches = 0;

    for (std::size_t i = 0;
         i < std::min<std::size_t>(k, actual.size());
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

std::vector<float> attributesOf(
    const DataWrapper &data,
    unsigned original_id) {

    std::vector<float> result(data.attr_count);

    for (unsigned attr = 0;
         attr < data.attr_count;
         ++attr) {
        result[attr] =
            data.attrs[attr][original_id];
    }

    return result;
}


namespace fs = std::filesystem;

void exportSnapshot(
    const std::string &directory,
    const std::vector<
        dsg::DynamicMultiDsgIndex::SnapshotPoint> &snapshot,
    std::size_t dimension) {

    if (directory.empty()) {
        return;
    }

    if (snapshot.size() >
        std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error(
            "Snapshot contains too many points");
    }

    if (dimension >
        std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error(
            "Snapshot dimension is too large");
    }

    const fs::path root(directory);
    fs::create_directories(root);

    const std::uint32_t count =
        static_cast<std::uint32_t>(snapshot.size());

    const std::uint32_t dim =
        static_cast<std::uint32_t>(dimension);

    // Compact snapshot vectors. Row index is snapshot_local_id.
    {
        std::ofstream output(
            root / "base.snapshot.fbin",
            std::ios::binary | std::ios::trunc);

        if (!output.is_open()) {
            throw std::runtime_error(
                "Cannot write base.snapshot.fbin");
        }

        output.write(
            reinterpret_cast<const char *>(&count),
            sizeof(count));

        output.write(
            reinterpret_cast<const char *>(&dim),
            sizeof(dim));

        for (const auto &point : snapshot) {
            if (point.vector.size() != dimension) {
                throw std::runtime_error(
                    "Snapshot vector dimension mismatch");
            }

            output.write(
                reinterpret_cast<const char *>(
                    point.vector.data()),
                sizeof(float) * dimension);
        }

        if (!output) {
            throw std::runtime_error(
                "Failed while writing snapshot vectors");
        }
    }

    // Attributes use snapshot_local_id as the first column.
    {
        std::ofstream output(
            root / "attrs.snapshot.csv",
            std::ios::trunc);

        if (!output.is_open()) {
            throw std::runtime_error(
                "Cannot write attrs.snapshot.csv");
        }

        output << std::setprecision(
            std::numeric_limits<float>::max_digits10);

        for (std::size_t local_id = 0;
             local_id < snapshot.size();
             ++local_id) {
            output << local_id;

            for (const float value :
                 snapshot[local_id].attrs) {
                output << "," << value;
            }

            output << "\n";
        }
    }

    // snapshot_local_id -> stable original_id.
    {
        std::ofstream output(
            root / "snapshot_to_original.ibin",
            std::ios::binary | std::ios::trunc);

        if (!output.is_open()) {
            throw std::runtime_error(
                "Cannot write snapshot_to_original.ibin");
        }

        output.write(
            reinterpret_cast<const char *>(&count),
            sizeof(count));

        for (const auto &point : snapshot) {
            const std::uint32_t stable_id =
                static_cast<std::uint32_t>(
                    point.original_id);

            output.write(
                reinterpret_cast<const char *>(
                    &stable_id),
                sizeof(stable_id));
        }
    }

    // Human-readable rebuild metadata.
    {
        std::ofstream output(
            root / "snapshot.meta",
            std::ios::trunc);

        if (!output.is_open()) {
            throw std::runtime_error(
                "Cannot write snapshot.meta");
        }

        const std::size_t attr_count =
            snapshot.empty()
                ? 0
                : snapshot.front().attrs.size();

        output
            << "count=" << count << "\n"
            << "dimension=" << dim << "\n"
            << "attribute_count="
            << attr_count << "\n";
    }

    std::cout
        << "snapshot_exported"
        << " directory=" << root.string()
        << " points=" << count
        << " dimension=" << dim
        << "\n";
}

EvalResult evaluate(
    const std::string &phase,
    dsg::DynamicMultiDsgIndex &index,
    const DataWrapper &data,
    const std::vector<FilterCase> &filters,
    unsigned eval_queries,
    unsigned top_k,
    unsigned search_ef,
    bool audit_correctness,
    const std::unordered_set<unsigned> &inserted_ids,
    const std::unordered_set<unsigned> &updated_ids,
    const std::unordered_set<unsigned> &deleted_ids) {

    EvalResult result;
    std::vector<dsg::DynamicMultiDsgIndex::SnapshotPoint>
        committed_snapshot;
    std::unordered_map<
        unsigned,
        const dsg::DynamicMultiDsgIndex::SnapshotPoint *>
        committed_by_id;

    if (audit_correctness) {
        committed_snapshot = index.createSnapshot();
        committed_by_id.reserve(committed_snapshot.size());

        for (const auto &point : committed_snapshot) {
            const auto inserted =
                committed_by_id.emplace(
                    point.original_id, &point);

            if (!inserted.second) {
                ++result.duplicate_id_violations;
            }
        }

        for (const unsigned id : inserted_ids) {
            if (committed_by_id.find(id) ==
                committed_by_id.end()) {
                ++result.inserted_visibility_violations;
            }
        }

        for (const unsigned id : updated_ids) {
            const auto found = committed_by_id.find(id);

            if (found == committed_by_id.end() ||
                found->second->version == 0) {
                ++result.updated_visibility_violations;
            }
        }

        for (const unsigned id : deleted_ids) {
            if (committed_by_id.find(id) !=
                committed_by_id.end()) {
                ++result.deleted_visibility_violations;
            }
        }
    }

    const std::size_t count =
        std::min<std::size_t>(
            eval_queries, filters.size());

    for (std::size_t i = 0; i < count; ++i) {
        const auto &test = filters[i];

        if (test.query_idx >= data.querys.size()) {
            continue;
        }

        const float *query =
            data.querys[test.query_idx];

        const auto exact_start =
            std::chrono::steady_clock::now();

        const auto exact = index.searchExact(
            query, test.filter, top_k);

        const auto exact_end =
            std::chrono::steady_clock::now();

        const auto approximate_start =
            std::chrono::steady_clock::now();

        const auto actual = index.search(
            query,
            test.filter,
            top_k,
            search_ef);

        const auto approximate_end =
            std::chrono::steady_clock::now();

        if (audit_correctness) {
            std::unordered_set<unsigned> query_ids;
            const auto &audit = index.lastResultAudit();

            if (audit.size() != actual.size()) {
                ++result.invalid_id_violations;
            }

            for (std::size_t position = 0;
                 position < actual.size();
                 ++position) {
                const unsigned id = actual[position];
                ++result.audited_results;

                if (!query_ids.insert(id).second) {
                    ++result.duplicate_id_violations;
                }

                const auto found = committed_by_id.find(id);

                if (found == committed_by_id.end()) {
                    if (deleted_ids.find(id) !=
                        deleted_ids.end()) {
                        ++result.deleted_id_violations;
                    } else {
                        ++result.invalid_id_violations;
                    }
                    continue;
                }

                const auto &point = *found->second;

                if (position >= audit.size() ||
                    audit[position].original_id != id ||
                    audit[position].version != point.version) {
                    ++result.stale_version_violations;
                }

                if (point.attrs.size() !=
                    test.filter.bounds.size()) {
                    ++result.predicate_violations;
                    continue;
                }

                for (std::size_t attr = 0;
                     attr < point.attrs.size();
                     ++attr) {
                    const float value = point.attrs[attr];
                    const auto &bound =
                        test.filter.bounds[attr];

                    if (value < bound.low ||
                        value > bound.high) {
                        ++result.predicate_violations;
                        break;
                    }
                }
            }
        }

        result.recall +=
            recallAtK(exact, actual, top_k);

        result.exact_ms +=
            std::chrono::duration<double, std::milli>(
                exact_end - exact_start).count();

        result.approximate_ms +=
            std::chrono::duration<double, std::milli>(
                approximate_end -
                approximate_start).count();

        result.delta_scanned +=
            index.lastStats().delta_scanned;

        result.base_candidates +=
            index.lastStats().base_candidates;

        result.base_search_ms +=
            index.lastStats().base_search_ms;

        result.delta_scan_ms +=
            index.lastStats().delta_scan_ms;

        result.merge_ms +=
            index.lastStats().merge_ms;

        ++result.queries;
    }

    if (result.queries > 0) {
        const double denominator =
            static_cast<double>(result.queries);

        const double average_approximate_ms =
            result.approximate_ms / denominator;

        const double average_base_search_ms =
            result.base_search_ms / denominator;

        const double average_delta_scan_ms =
            result.delta_scan_ms / denominator;

        const double average_merge_ms =
            result.merge_ms / denominator;

        const double other_ms =
            average_approximate_ms -
            average_base_search_ms -
            average_delta_scan_ms -
            average_merge_ms;

        std::cout
            << std::left << std::setw(18) << phase
            << " queries=" << result.queries
            << " recall=" << std::fixed
            << std::setprecision(4)
            << result.recall / denominator
            << " approx_ms="
            << average_approximate_ms
            << " exact_ms="
            << result.exact_ms / denominator
            << " qps="
            << 1000.0 /
                average_approximate_ms
            << " base_search_ms="
            << average_base_search_ms
            << " delta_scan_ms="
            << average_delta_scan_ms
            << " merge_ms="
            << average_merge_ms
            << " other_ms="
            << other_ms
            << " base_candidates="
            << result.base_candidates / denominator
            << " delta_scanned="
            << result.delta_scanned / denominator
            << " delta_size=" << index.deltaSize()
            << " tombstones="
            << index.tombstoneCount()
            << " rebuild="
            << (index.needsRebuild() ? "yes" : "no")
            << "\n";
    }

    if (audit_correctness) {
        std::cout
            << "audit phase=" << phase
            << " audited_results=" << result.audited_results
            << " stale_version_violations="
            << result.stale_version_violations
            << " deleted_id_violations="
            << result.deleted_id_violations
            << " duplicate_id_violations="
            << result.duplicate_id_violations
            << " predicate_violations="
            << result.predicate_violations
            << " invalid_id_violations="
            << result.invalid_id_violations
            << " inserted_visibility_violations="
            << result.inserted_visibility_violations
            << " updated_visibility_violations="
            << result.updated_visibility_violations
            << " deleted_visibility_violations="
            << result.deleted_visibility_violations
            << "\n";
    }

    return result;
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

        std::string dataset_path =
            cfg.dataset_path;
        std::string query_path =
            cfg.query_path;

        data.readData(dataset_path, query_path);
        data.readAttributes(
            cfg.attr_path, cfg.attr_count);

        std::vector<std::unique_ptr<DataWrapper>>
            ranked_data;

        std::vector<std::unique_ptr<hnswlib::L2Space>>
            spaces;

        std::vector<std::unique_ptr<
            dsg::DynamicSegmentGraph>> owned_indexes;

        std::vector<dsg::DynamicSegmentGraph *>
            index_ptrs;

        std::vector<std::vector<unsigned>>
            rank_to_original;

        for (unsigned attr = 0;
             attr < cfg.attr_count;
             ++attr) {
            auto current_data =
                std::make_unique<DataWrapper>(
                    cfg.query_num,
                    cfg.query_k,
                    cfg.dataset,
                    cfg.data_size);

            std::string ranked_path =
                cfg.reordered_data_root +
                "/base.attr" +
                std::to_string(attr) +
                ".fbin";

            current_data->readData(
                ranked_path, query_path);

            auto space =
                std::make_unique<hnswlib::L2Space>(
                    current_data->data_dim);

            auto graph = std::make_unique<
                dsg::DynamicSegmentGraph>(
                    space.get(),
                    current_data.get());

            graph->load(
                cfg.index_root +
                "/attr" +
                std::to_string(attr) +
                ".dsg");

            index_ptrs.push_back(graph.get());

            rank_to_original.push_back(
                readRankMapping(
                    cfg.reordered_data_root +
                    "/rank_to_original.attr" +
                    std::to_string(attr) +
                    ".ibin"));

            ranked_data.push_back(
                std::move(current_data));

            spaces.push_back(std::move(space));
            owned_indexes.push_back(std::move(graph));
        }

        dsg::DynamicMultiDsgIndex dynamic_index(
            &data,
            index_ptrs,
            rank_to_original,
            {},
            cfg.rebuild_fraction);

        const auto filters =
            readFilters(
                cfg.filter_path,
                cfg.attr_count);

        std::unordered_set<unsigned> inserted_ids;
        std::unordered_set<unsigned> updated_ids;
        std::unordered_set<unsigned> deleted_ids;

        evaluate(
            "base",
            dynamic_index,
            data,
            filters,
            cfg.eval_queries,
            cfg.query_k,
            cfg.search_ef,
            cfg.audit_correctness,
            inserted_ids,
            updated_ids,
            deleted_ids);

        std::mt19937 random(cfg.seed);
        std::uniform_real_distribution<float>
            noise(-0.005F, 0.005F);

        // 插入新点。
        for (unsigned i = 0;
             i < cfg.insert_count;
             ++i) {
            const unsigned source =
                (i * 997U) %
                static_cast<unsigned>(data.data_size);

            std::vector<float> vector(data.data_dim);

            for (std::size_t dim = 0;
                 dim < data.data_dim;
                 ++dim) {
                vector[dim] =
                    data.nodes[source][dim] +
                    noise(random);
            }

            inserted_ids.insert(
                dynamic_index.insert(
                    vector.data(),
                    attributesOf(data, source)));
        }

        evaluate(
            "after_insert",
            dynamic_index,
            data,
            filters,
            cfg.eval_queries,
            cfg.query_k,
            cfg.search_ef,
            cfg.audit_correctness,
            inserted_ids,
            updated_ids,
            deleted_ids);

        // 修改Base点的属性。
        for (unsigned i = 0;
             i < cfg.update_count;
             ++i) {
            const unsigned target = i;
            const unsigned attr_source =
                (i + data.data_size / 2U) %
                static_cast<unsigned>(data.data_size);

            dynamic_index.updateAttributes(
                target,
                attributesOf(data, attr_source));
            updated_ids.insert(target);
        }

        evaluate(
            "after_update",
            dynamic_index,
            data,
            filters,
            cfg.eval_queries,
            cfg.query_k,
            cfg.search_ef,
            cfg.audit_correctness,
            inserted_ids,
            updated_ids,
            deleted_ids);

        // 删除Base尾部的点，避免与更新集合重叠。
        for (unsigned i = 0;
             i < cfg.delete_count;
             ++i) {
            const unsigned target =
                static_cast<unsigned>(
                    data.data_size - 1) - i;

            dynamic_index.erase(target);
            deleted_ids.insert(target);
        }

        evaluate(
            "after_delete",
            dynamic_index,
            data,
            filters,
            cfg.eval_queries,
            cfg.query_k,
            cfg.search_ef,
            cfg.audit_correctness,
            inserted_ids,
            updated_ids,
            deleted_ids);

        if (dynamic_index.needsRebuild() &&
            !cfg.snapshot_dir.empty()) {

            const auto snapshot =
                dynamic_index.createSnapshot();

            exportSnapshot(
                cfg.snapshot_dir,
                snapshot,
                data.data_dim);
        }

    } catch (const std::exception &error) {
        std::cerr
            << "update_and_query_multi_dsg failed: "
            << error.what() << "\n";
        return 1;
    }

    return 0;
}
