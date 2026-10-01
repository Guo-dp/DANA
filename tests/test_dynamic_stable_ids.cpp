#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <set>
#include <stdexcept>
#include <vector>

#include "base_hnsw/hnswlib.h"
#include "dana_snapshot_metadata.h"
#include "dynamic_dana.h"

namespace fs = std::filesystem;
using Index = dsg::DynamicDanaIndex;

struct Point {
    std::vector<float> vector;
    std::vector<float> attrs;
};

// The reference owns independent state and replays operations without consulting DANA.
struct Reference {
    std::map<unsigned, Point> live;
    std::set<unsigned> delta_ids;
    std::uint64_t next_id = 0;

    void put(unsigned id, Point point) {
        live[id] = std::move(point);
        delta_ids.insert(id);
        next_id = std::max(next_id, static_cast<std::uint64_t>(id) + 1);
    }
    void erase(unsigned id) {
        live.erase(id);
        delta_ids.erase(id);
    }
    void attributes(unsigned id, const std::vector<float> &attrs) {
        live.at(id).attrs = attrs;
        delta_ids.insert(id);
    }
    void installed() { delta_ids.clear(); }
};

void require(bool condition, const std::string &message) {
    if (!condition) throw std::runtime_error(message);
}

template <class Function>
void mustThrow(Function action, const std::string &message) {
    bool threw = false;
    try { action(); } catch (const std::exception &) { threw = true; }
    require(threw, message);
}

Point generated(unsigned id) {
    Point point;
    for (unsigned dim = 0; dim < 8; ++dim)
        point.vector.push_back(static_cast<float>((id * (dim * 4 + 7) + dim) % 101));
    point.attrs = {static_cast<float>(id % 17),
                   static_cast<float>((id * 7) % 23),
                   static_cast<float>((id * 13) % 31)};
    return point;
}

bool passes(const Point &point, const MultiRangeQuery &filter) {
    for (unsigned attr = 0; attr < point.attrs.size(); ++attr)
        if (point.attrs[attr] < filter.bounds[attr].low ||
            point.attrs[attr] > filter.bounds[attr].high) return false;
    return true;
}

float distance(const std::vector<float> &query, const Point &point) {
    float sum = 0;
    for (unsigned dim = 0; dim < query.size(); ++dim) {
        const float d = query[dim] - point.vector[dim];
        sum += d * d;
    }
    return sum;
}

std::vector<unsigned> referenceQuery(const Reference &reference,
                                     const std::vector<float> &query,
                                     const MultiRangeQuery &filter, unsigned k) {
    std::vector<std::pair<float, unsigned>> candidates;
    for (const auto &entry : reference.live)
        if (passes(entry.second, filter))
            candidates.emplace_back(distance(query, entry.second), entry.first);
    std::sort(candidates.begin(), candidates.end());
    std::vector<unsigned> result;
    for (unsigned i = 0; i < std::min<std::size_t>(k, candidates.size()); ++i)
        result.push_back(candidates[i].second);
    return result;
}

void checkSnapshot(const Index &index, const Reference &reference,
                   const std::string &phase) {
    const auto snapshot = index.createSnapshot();
    require(snapshot.size() == reference.live.size(), phase + ": snapshot count");
    std::set<unsigned> seen;
    for (const auto &point : snapshot) {
        require(seen.insert(point.original_id).second, phase + ": duplicate ID");
        const auto found = reference.live.find(point.original_id);
        require(found != reference.live.end(), phase + ": deleted or unknown ID");
        require(point.vector == found->second.vector, phase + ": stale/misread vector");
        require(point.attrs == found->second.attrs, phase + ": stale attributes");
    }
    require(index.nextOriginalId() == reference.next_id, phase + ": allocator history");
    std::cout << "STATE PASS phase=" << phase << " points=" << snapshot.size()
              << " next_id=" << index.nextOriginalId() << '\n';
}

// Own all objects referenced by DSG and DANA. Each rebuild writes and reloads real DSGs.
struct Bundle {
    std::unique_ptr<DataWrapper> base;
    std::vector<unsigned> stable_ids;
    std::vector<std::vector<unsigned>> ranks;
    std::vector<std::unique_ptr<DataWrapper>> ordered;
    std::vector<std::unique_ptr<hnswlib::L2Space>> spaces;
    std::vector<std::unique_ptr<dsg::DynamicSegmentGraph>> graphs;
    std::unique_ptr<Index> index;

    Bundle(const std::map<unsigned, Point> &points, std::uint64_t next_id,
           const fs::path &directory = {}, bool build_graphs = false) {
        require(!points.empty(), "nonempty fixture required");
        const unsigned n = points.size();
        const unsigned dimensions = points.begin()->second.vector.size();
        base = std::make_unique<DataWrapper>(1, 10, "stable_id_regression", n);
        base->data_dim = dimensions;
        base->nodes.resize(n, dimensions);
        base->attr_count = 3;
        base->attrs.assign(3, std::vector<float>(n));
        unsigned row = 0;
        for (const auto &entry : points) {
            stable_ids.push_back(entry.first);
            base->nodes.assign_row(row, entry.second.vector.data());
            for (unsigned attr = 0; attr < 3; ++attr)
                base->attrs[attr][row] = entry.second.attrs[attr];
            ++row;
        }
        ranks.resize(3);
        base->attr_rank.assign(3, std::vector<unsigned>(n));
        for (unsigned attr = 0; attr < 3; ++attr) {
            ranks[attr].resize(n);
            std::iota(ranks[attr].begin(), ranks[attr].end(), 0U);
            std::stable_sort(ranks[attr].begin(), ranks[attr].end(),
                [&](unsigned a, unsigned b) { return base->attrs[attr][a] < base->attrs[attr][b]; });
            for (unsigned rank = 0; rank < n; ++rank)
                base->attr_rank[attr][ranks[attr][rank]] = rank;
        }
        base->rank_to_original = ranks;
        std::vector<dsg::DynamicSegmentGraph *> pointers(3, nullptr);
        if (build_graphs) {
            fs::create_directories(directory);
            for (unsigned attr = 0; attr < 3; ++attr) {
                auto data = std::make_unique<DataWrapper>(1, 10, "ranked", n);
                data->data_dim = dimensions;
                data->nodes.resize(n, dimensions);
                for (unsigned rank = 0; rank < n; ++rank)
                    data->nodes.assign_row(rank, base->nodes[ranks[attr][rank]]);
                auto space = std::make_unique<hnswlib::L2Space>(dimensions);
                auto graph = std::make_unique<dsg::DynamicSegmentGraph>(space.get(), data.get());
                graph->M = 8;
                graph->ef_construction = 40;
                graph->ef_max = 48;
                graph->random_seed = 2051;
                graph->build(data->labels);
                const auto path = (directory / ("attr" + std::to_string(attr) + ".dsg")).string();
                graph->save(path);
                graph = std::make_unique<dsg::DynamicSegmentGraph>(space.get(), data.get());
                graph->load(path);
                pointers[attr] = graph.get();
                ordered.push_back(std::move(data));
                spaces.push_back(std::move(space));
                graphs.push_back(std::move(graph));
            }
        }
        index = std::make_unique<Index>(base.get(), pointers, ranks, stable_ids, 0.05, next_id);
    }
};

void checkQueries(Index &index, const Reference &reference,
                  const std::string &phase, bool approximate) {
    double recall = 0;
    unsigned query_count = 0;
    for (unsigned q = 0; q < 40; ++q) {
        const auto query = generated(q * 19).vector;
        MultiRangeQuery filter;
        filter.bounds.resize(3);
        for (auto &bound : filter.bounds) { bound.low = -1000; bound.high = 1000; }
        if (q % 3 != 0) {
            const unsigned attr = q % 3;
            filter.bounds[attr].low = q % 7;
            filter.bounds[attr].high = q % 7 + 5;
        }
        const auto expected = referenceQuery(reference, query, filter, 10);
        require(index.searchExact(query.data(), filter, 10) == expected,
                phase + ": exact result disagrees with operation replay");
        if (approximate) {
            const auto actual = index.search(query.data(), filter, 10, 128);
            std::set<unsigned> seen;
            const auto &audit = index.lastResultAudit();
            require(audit.size() == actual.size(), phase + ": audit count");
            unsigned hits = 0;
            for (unsigned i = 0; i < actual.size(); ++i) {
                const auto found = reference.live.find(actual[i]);
                require(found != reference.live.end(), phase + ": ANN deleted/invalid ID");
                require(seen.insert(actual[i]).second, phase + ": ANN duplicate ID");
                require(passes(found->second, filter), phase + ": ANN predicate violation");
                require(audit[i].from_delta == (reference.delta_ids.count(actual[i]) != 0),
                        phase + ": ANN stale source version");
                if (std::find(expected.begin(), expected.end(), actual[i]) != expected.end()) ++hits;
            }
            recall += expected.empty() ? 1.0 : static_cast<double>(hits) / expected.size();
        }
        ++query_count;
    }
    std::cout << "QUERY PASS phase=" << phase << " exact_queries=" << query_count;
    if (approximate) std::cout << " ann_recall=" << std::fixed << std::setprecision(6)
                               << recall / query_count << " state_violations=0";
    std::cout << '\n';
}

void put(Index &index, Reference &reference, unsigned id, const Point &point) {
    index.update(id, point.vector.data(), point.attrs);
    reference.put(id, point);
}

unsigned insert(Index &index, Reference &reference, const Point &point) {
    const auto expected = reference.next_id;
    const auto actual = index.insert(point.vector.data(), point.attrs);
    require(actual == expected, "insert reused or skipped an allocated ID");
    reference.put(actual, point);
    return actual;
}

void erase(Index &index, Reference &reference, unsigned id) {
    index.erase(id);
    reference.erase(id);
}

void unitCases() {
    Reference reference;
    for (unsigned id : {0U, 2U, 3U}) reference.live[id] = generated(id);
    reference.next_id = 4;
    Bundle bundle(reference.live, reference.next_id);
    auto &index = *bundle.index;
    erase(index, reference, 3);
    checkSnapshot(index, reference, "sparse_base_delete_id3");
    checkQueries(index, reference, "sparse_base_delete_id3", false);
    mustThrow([&] { index.updateAttributes(3, {1, 2, 3}); }, "deleted ID attributes resurrected");
    mustThrow([&] { index.update(1, generated(1).vector.data(), {1, 2, 3}); }, "gap ID accepted");
    put(index, reference, 2, generated(22));
    put(index, reference, 2, generated(23));
    index.updateAttributes(2, {8, 9, 10}); reference.attributes(2, {8, 9, 10});
    checkSnapshot(index, reference, "repeated_update_latest_only");
    erase(index, reference, 2);
    const auto id = insert(index, reference, generated(90));
    erase(index, reference, id);
    checkSnapshot(index, reference, "updated_and_inserted_deleted");

    Reference high;
    high.live = {{0, generated(0)}, {2, generated(2)}, {9000, generated(90)}};
    high.next_id = 9001;
    Bundle high_bundle(high.live, high.next_id);
    high_bundle.index->updateAttributes(9000, {70, 80, 90});
    high.attributes(9000, {70, 80, 90});
    checkSnapshot(*high_bundle.index, high, "high_stable_id_attributes_preserve_vector");
    checkQueries(*high_bundle.index, high, "high_stable_id_attributes", false);
    put(*high_bundle.index, high, 9000, generated(99));
    erase(*high_bundle.index, high, 9000);
    checkSnapshot(*high_bundle.index, high, "high_base_update_then_delete");
    high.installed();
    Bundle restored(high.live, high.next_id);
    insert(*restored.index, high, generated(100));
    checkSnapshot(*restored.index, high, "deleted_max_id_not_reused");
    const auto before = restored.index->nextOriginalId();
    mustThrow([&] { restored.index->insert(nullptr, {1, 2, 3}); }, "null vector accepted");
    require(restored.index->nextOriginalId() == before, "failed insert consumed ID");
    Index legacy(restored.base.get(), {nullptr, nullptr, nullptr}, restored.ranks,
                 restored.stable_ids, 0.05);
    mustThrow([&] { legacy.insert(generated(3).vector.data(), {1, 2, 3}); },
              "legacy snapshot silently reused allocation history");
    mustThrow([&] {
        Index duplicate(restored.base.get(), {nullptr, nullptr, nullptr}, restored.ranks,
                        {1, 1}, 0.05);
    }, "duplicate stable mapping accepted");
    const unsigned max_id = std::numeric_limits<unsigned>::max();
    Reference edge;
    edge.live = {{max_id, generated(1)}};
    edge.next_id = static_cast<std::uint64_t>(max_id) + 1;
    Bundle exhausted(edge.live, edge.next_id);
    mustThrow([&] { exhausted.index->insert(generated(2).vector.data(), {1, 2, 3}); },
              "ID overflow wrapped allocator");
    std::cout << "UNIT PASS sparse/delete/update/attributes/repeated/allocator/overflow\n";
}

void writeSnapshot(const fs::path &root, const Index &index) {
    fs::create_directories(root);
    const auto snapshot = index.createSnapshot();
    const std::uint32_t count = snapshot.size(), dim = snapshot.front().vector.size();
    std::ofstream vectors(root / "base.snapshot.fbin", std::ios::binary);
    vectors.write(reinterpret_cast<const char *>(&count), 4);
    vectors.write(reinterpret_cast<const char *>(&dim), 4);
    std::ofstream mapping(root / "snapshot_to_original.ibin", std::ios::binary);
    mapping.write(reinterpret_cast<const char *>(&count), 4);
    std::ofstream attrs(root / "attrs.snapshot.csv");
    attrs << std::setprecision(std::numeric_limits<float>::max_digits10);
    for (unsigned row = 0; row < count; ++row) {
        const auto &point = snapshot[row];
        vectors.write(reinterpret_cast<const char *>(point.vector.data()), dim * 4);
        mapping.write(reinterpret_cast<const char *>(&point.original_id), 4);
        attrs << row;
        for (float value : point.attrs) attrs << ',' << value;
        attrs << '\n';
    }
    std::ofstream meta(root / "snapshot.meta");
    meta << "count=" << count << "\ndimension=" << dim
         << "\nattribute_count=3\nnext_original_id=" << index.nextOriginalId() << '\n';
    require(vectors.good() && mapping.good() && attrs.good() && meta.good(), "snapshot write failed");
}

std::unique_ptr<Bundle> reload(const fs::path &root, Reference &reference) {
    const auto next_id = dsg::readSnapshotNextOriginalId((root / "snapshot.meta").string());
    std::ifstream mapping(root / "snapshot_to_original.ibin", std::ios::binary);
    std::uint32_t count = 0;
    mapping.read(reinterpret_cast<char *>(&count), 4);
    DataWrapper data(0, 10, "snapshot_reload", count);
    std::string vectors = (root / "base.snapshot.fbin").string(), queries;
    data.readData(vectors, queries);
    data.readAttributes((root / "attrs.snapshot.csv").string(), 3);
    std::map<unsigned, Point> actual;
    for (unsigned row = 0; row < count; ++row) {
        unsigned id = 0;
        mapping.read(reinterpret_cast<char *>(&id), 4);
        Point point;
        point.vector.assign(data.nodes[row], data.nodes[row] + data.data_dim);
        for (unsigned attr = 0; attr < 3; ++attr) point.attrs.push_back(data.attrs[attr][row]);
        require(actual.emplace(id, point).second, "duplicate serialized ID");
        const auto &expected = reference.live.at(id);
        require(point.vector == expected.vector && point.attrs == expected.attrs,
                "serialized state differs from operation replay");
    }
    require(mapping.good() && actual.size() == reference.live.size(), "mapping/state load mismatch");
    require(next_id == reference.next_id, "serialized allocator differs from operation replay");
    reference.installed();
    return std::make_unique<Bundle>(actual, next_id, root / "indexes", true);
}

void twoRebuilds(const fs::path &root) {
    Reference reference;
    for (unsigned id = 0; id < 1000; ++id) reference.live[id] = generated(id);
    reference.next_id = 1000;
    auto bundle = std::make_unique<Bundle>(reference.live, reference.next_id, root / "initial", true);
    checkQueries(*bundle->index, reference, "initial_1000", true);
    for (unsigned i = 0; i < 12; ++i) insert(*bundle->index, reference, generated(2000 + i));
    for (unsigned id = 0; id < 24; ++id) put(*bundle->index, reference, id, generated(3000 + id));
    for (unsigned id = 24; id < 124; ++id) erase(*bundle->index, reference, id);
    erase(*bundle->index, reference, 7);       // Updated Base object.
    erase(*bundle->index, reference, 1011);    // Largest allocated ID.
    checkSnapshot(*bundle->index, reference, "round1_mutations");
    checkQueries(*bundle->index, reference, "round1_mutations", true);
    writeSnapshot(root / "round1", *bundle->index);
    bundle = reload(root / "round1", reference);
    checkSnapshot(*bundle->index, reference, "round1_reloaded");
    checkQueries(*bundle->index, reference, "round1_reloaded", true);

    auto &index = *bundle->index;
    insert(index, reference, generated(4000)); // Must allocate 1012, not deleted 1011.
    index.updateAttributes(1005, {70, 80, 90});
    reference.attributes(1005, {70, 80, 90});
    put(index, reference, 1006, generated(5000));
    put(index, reference, 1006, generated(5001));
    put(index, reference, 1007, generated(5002));
    erase(index, reference, 1007);
    erase(index, reference, 999);             // stable ID exceeds compact Base count.
    erase(index, reference, 1012);            // New Delta object removed.
    checkSnapshot(index, reference, "round2_mutations");
    checkQueries(index, reference, "round2_mutations", true);
    writeSnapshot(root / "round2", index);
    bundle = reload(root / "round2", reference);
    checkSnapshot(*bundle->index, reference, "round2_reloaded");
    checkQueries(*bundle->index, reference, "round2_reloaded", true);
    const auto id = insert(*bundle->index, reference, generated(6000));
    require(id == 1013, "allocator lost history after second rebuild");
    checkSnapshot(*bundle->index, reference, "post_second_rebuild_insert");
    checkQueries(*bundle->index, reference, "post_second_rebuild_insert", true);
    std::cout << "REBUILD PASS initial=1000 attributes=3 rounds=2 state_violations=0\n";
}

int main(int argc, char **argv) {
    try {
        unitCases();
        if (argc > 1) twoRebuilds(fs::path(argv[1]));
        std::cout << "ALL PASS independent_operation_replay\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
