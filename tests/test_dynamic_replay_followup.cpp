#define DANA_STABLE_ID_HELPERS_ONLY
#include "test_dynamic_stable_ids.cpp"
#include <chrono>
#include <random>

using Clock = std::chrono::steady_clock;

struct Operation {
    enum Kind { Insert, VectorUpdate, AttributeUpdate, Delete } kind;
    unsigned id;
    Point image;
    std::uint64_t version = 0;
};

Reference initialReference() {
    Reference reference;
    for (unsigned id = 0; id < 1000; ++id) reference.live.emplace(id, generated(id));
    reference.next_id = 1000;
    return reference;
}

void applyReference(Reference &reference, const Operation &op) {
    if (op.kind == Operation::Delete) {
        require(reference.live.count(op.id) != 0, "oracle deleted absent ID");
        reference.erase(op.id);
    } else if (op.kind == Operation::Insert) {
        require(reference.next_id == op.id && !reference.live.count(op.id), "oracle reused ID");
        reference.put(op.id, op.image);
    } else if (op.kind == Operation::VectorUpdate) {
        require(reference.live.count(op.id) != 0, "oracle updated absent ID");
        require(reference.live.at(op.id).attrs == op.image.attrs, "vector update changed attributes");
        reference.put(op.id, op.image);
    } else {
        require(reference.live.count(op.id) != 0, "oracle updated absent ID");
        require(reference.live.at(op.id).vector == op.image.vector, "attribute update changed vector");
        reference.attributes(op.id, op.image.attrs);
    }
}

void applyIndex(Index &index, const Operation &op) {
    switch (op.kind) {
    case Operation::Insert:
        require(index.insert(op.image.vector.data(), op.image.attrs) == op.id,
                "automatic insertion did not use oracle stable ID");
        break;
    case Operation::VectorUpdate:
        index.update(op.id, op.image.vector.data(), op.image.attrs);
        break;
    case Operation::AttributeUpdate:
        index.updateAttributes(op.id, op.image.attrs);
        break;
    case Operation::Delete:
        index.erase(op.id);
        break;
    }
}

void checkImages(const Index &index, const Reference &reference,
                 const std::map<unsigned, std::uint64_t> &delta_versions,
                 const std::string &phase) {
    const auto snapshot = index.createSnapshot();
    require(snapshot.size() == reference.live.size(), phase + ": live count");
    for (const auto &point : snapshot) {
        const auto it = reference.live.find(point.original_id);
        require(it != reference.live.end(), phase + ": deleted/invalid ID");
        require(point.vector == it->second.vector, phase + ": stale vector");
        require(point.attrs == it->second.attrs, phase + ": stale attributes");
        const auto v = delta_versions.find(point.original_id);
        require(point.version == (v == delta_versions.end() ? 0 : v->second),
                phase + ": stale version");
    }
    require(index.nextOriginalId() == reference.next_id, phase + ": allocator watermark");
}

unsigned chooseLive(const Reference &reference, const std::vector<unsigned> &hot,
                    std::mt19937 &rng) {
    require(!reference.live.empty(), "no live object for mutation");
    if (!hot.empty() && rng() % 100 < 70) {
        for (unsigned attempts = 0; attempts < 12; ++attempts) {
            const auto id = hot[rng() % hot.size()];
            if (reference.live.count(id)) return id;
        }
    }
    auto it = reference.live.begin();
    std::advance(it, rng() % reference.live.size());
    return it->first;
}

Operation makeOperation(const Reference &reference, const std::vector<unsigned> &hot,
                        std::mt19937 &rng, unsigned step, unsigned &forced_delete,
                        bool &forced_insert) {
    if (forced_delete != std::numeric_limits<unsigned>::max()) {
        const unsigned id = forced_delete;
        forced_delete = std::numeric_limits<unsigned>::max();
        if (reference.live.count(id)) return {Operation::Delete, id, {}, 0};
    }
    if (!forced_insert && step % 101 == 0 && reference.next_id > 0 &&
        reference.live.count(static_cast<unsigned>(reference.next_id - 1))) {
        forced_insert = true;
        return {Operation::Delete, static_cast<unsigned>(reference.next_id - 1), {}, 0};
    }
    const unsigned roll = forced_insert ? 0 : rng() % 100;
    forced_insert = false;
    if (roll < 25 || reference.live.empty()) {
        const unsigned id = static_cast<unsigned>(reference.next_id);
        auto image = generated(rng());
        if (step % 11 == 0) forced_delete = id;
        return {Operation::Insert, id, std::move(image), 0};
    }
    const unsigned id = chooseLive(reference, hot, rng);
    if (roll >= 80) return {Operation::Delete, id, {}, 0};
    auto image = reference.live.at(id);
    if (roll < 55) {
        image.vector = generated(rng()).vector;
        return {Operation::VectorUpdate, id, std::move(image), 0};
    }
    image.attrs = generated(rng()).attrs;
    return {Operation::AttributeUpdate, id, std::move(image), 0};
}

void checkOracleAgreement(const Reference &left, const Reference &right) {
    require(left.live.size() == right.live.size() && left.next_id == right.next_id,
            "old and independently replayed oracle diverged");
    for (const auto &entry : left.live) {
        const auto found = right.live.find(entry.first);
        require(found != right.live.end() && entry.second.vector == found->second.vector &&
                entry.second.attrs == found->second.attrs, "oracle replay content diverged");
    }
}

void randomCampaign(const fs::path &root) {
    fs::create_directories(root);
    std::ofstream csv(root / "random_rounds.csv");
    require(csv.good(), "cannot open random results");
    csv << "seed,round,insert,vector_update,attribute_update,delete,live,next_id,"
           "exact_queries_old,exact_queries_replayed,state_violations\n";
    for (unsigned seed = 1; seed <= 5; ++seed) {
        std::mt19937 rng(20261003 + seed);
        auto reference = initialReference();
        auto bundle = std::make_unique<Bundle>(reference.live, reference.next_id,
                                                root / ("seed" + std::to_string(seed)) / "initial",
                                                true, 2050 + seed);
        std::map<unsigned, std::uint64_t> versions;
        std::uint64_t next_version = 1, next_sequence = 0;
        for (unsigned round = 1; round <= 5; ++round) {
            auto &old = *bundle->index;
            const auto phase = "seed" + std::to_string(seed) + "_round" + std::to_string(round);
            checkImages(old, reference, versions, phase + "_before_capture");
            const auto cut_reference = reference;
            const auto capture = old.captureForRebuild();
            require(capture.sequence == next_sequence && capture.next_version == next_version &&
                    capture.next_original_id == reference.next_id, phase + ": cut metadata");
            const fs::path snapshot_dir = root / phase;
            writeSnapshot(snapshot_dir, old);
            std::vector<Operation> operations;
            operations.reserve(1000);
            std::vector<unsigned> hot;
            unsigned forced_delete = std::numeric_limits<unsigned>::max();
            bool forced_insert = false;
            unsigned counts[4] = {};
            for (unsigned step = 0; step < 1000; ++step) {
                auto op = makeOperation(reference, hot, rng, step, forced_delete, forced_insert);
                if (op.kind != Operation::Delete) op.version = next_version++;
                applyIndex(old, op);
                applyReference(reference, op);
                if (op.kind == Operation::Delete) versions.erase(op.id);
                else versions[op.id] = op.version;
                ++counts[op.kind];
                if (op.kind != Operation::Delete) {
                    hot.push_back(op.id);
                    if (hot.size() > 64) hot.erase(hot.begin());
                }
                operations.push_back(std::move(op));
                ++next_sequence;
                if (step % 200 == 199)
                    checkImages(old, reference, versions, phase + "_checkpoint");
            }
            const auto journal = old.journalSince(capture);
            require(journal.operations.size() == operations.size() &&
                    journal.end_sequence == next_sequence &&
                    journal.next_version == next_version &&
                    journal.next_original_id == reference.next_id, phase + ": journal metadata");
            for (std::size_t i = 0; i < operations.size(); ++i) {
                const auto &actual = journal.operations[i];
                const auto &expected = operations[i];
                require(actual.sequence == capture.sequence + i + 1 &&
                        actual.original_id == expected.id &&
                        actual.erased == (expected.kind == Operation::Delete) &&
                        actual.version == expected.version &&
                        actual.vector == expected.image.vector &&
                        actual.attrs == expected.image.attrs,
                        phase + ": journal differs from generated raw operation");
            }
            checkImages(old, reference, versions, phase + "_old_final");
            checkQueries(old, reference, phase + "_old", true);
            auto replay_reference = cut_reference;
            replay_reference.installed();
            std::map<unsigned, std::uint64_t> replay_versions;
            for (const auto &op : operations) {
                applyReference(replay_reference, op);
                if (op.kind == Operation::Delete) replay_versions.erase(op.id);
                else replay_versions[op.id] = op.version;
            }
            checkOracleAgreement(reference, replay_reference);
            auto disk_reference = cut_reference;
            auto replacement = reload(snapshot_dir, disk_reference, 2050 + seed);
            replacement->index->replayAfterCapture(capture, journal);
            checkImages(*replacement->index, replay_reference, replay_versions,
                        phase + "_replayed_final");
            checkQueries(*replacement->index, replay_reference, phase + "_replayed", true);
            old.finishCapture(capture, journal);
            reference = std::move(replay_reference);
            versions = std::move(replay_versions);
            bundle = std::move(replacement);
            csv << seed << ',' << round;
            for (unsigned count : counts) csv << ',' << count;
            csv << ',' << reference.live.size() << ',' << reference.next_id
                << ",40,40,0\n";
            std::cout << "RANDOM PASS seed=" << seed << " round=" << round
                      << " operations=1000 live=" << reference.live.size()
                      << " next_id=" << reference.next_id << " state_violations=0\n";
        }
    }
    require(csv.good(), "random results write failed");
    std::cout << "ALL PASS randomized_sequential_replay seeds=5 rounds=25 operations=25000\n";
}

void fixtureMutations(Index &index, Reference &reference, unsigned round) {
    erase(index, reference, round);
    put(index, reference, 10, generated(8000 + round));
    index.updateAttributes(11, {70, 80, 90});
    reference.attributes(11, {70, 80, 90});
    const auto temporary = insert(index, reference, generated(8100 + round));
    erase(index, reference, temporary);
    require(insert(index, reference, generated(8200 + round)) > temporary, "highest ID reused");
    put(index, reference, 12 + round, generated(8300 + round));
    put(index, reference, 12 + round, generated(8400 + round));
    erase(index, reference, 12 + round);
    for (unsigned id = 30; id < 50; ++id)
        put(index, reference, id, generated(9000 + round * 100 + id));
    for (unsigned id = 50; id < 60; ++id) erase(index, reference, id);
    put(index, reference, 20, generated(9500 + round));
}

void measureQuality(Index &index, const Reference &reference, unsigned graph_seed,
                    const std::string &phase, unsigned ef, std::ofstream &csv) {
    double recall = 0, tie_recall = 0, total_ms = 0;
    std::size_t graph_dist = 0, rerank_dist = 0, delta_dist = 0, delta_scanned = 0;
    unsigned insufficient = 0;
    for (unsigned q = 0; q < 40; ++q) {
        const auto query = generated(q * 19).vector;
        MultiRangeQuery filter;
        filter.bounds.resize(3);
        for (auto &bound : filter.bounds) { bound.low = -1000; bound.high = 1000; }
        if (q % 3) {
            filter.bounds[q % 3].low = q % 7;
            filter.bounds[q % 3].high = q % 7 + 5;
        }
        const auto expected = referenceQuery(reference, query, filter, 10);
        require(index.searchExact(query.data(), filter, 10) == expected,
                phase + ": exact query disagreed with reference");
        const auto start = Clock::now();
        const auto actual = index.search(query.data(), filter, 10, ef);
        total_ms += std::chrono::duration<double, std::milli>(Clock::now() - start).count();
        const auto &stats = index.lastStats();
        graph_dist += stats.graph_distance_evaluations;
        rerank_dist += stats.base_rerank_distance_evaluations;
        delta_dist += stats.delta_distance_evaluations;
        delta_scanned += stats.delta_scanned;
        if (actual.size() < expected.size()) ++insufficient;
        std::set<unsigned> seen;
        unsigned hits = 0, closer_hits = 0, boundary_hits = 0, closer_total = 0;
        const float boundary = expected.empty() ? 0 : distance(query, reference.live.at(expected.back()));
        for (const auto &entry : reference.live)
            if (passes(entry.second, filter) && distance(query, entry.second) < boundary) ++closer_total;
        require(index.lastResultAudit().size() == actual.size(), "audit/result count mismatch");
        for (std::size_t i = 0; i < actual.size(); ++i) {
            const auto found = reference.live.find(actual[i]);
            require(found != reference.live.end() && seen.insert(actual[i]).second &&
                    passes(found->second, filter), phase + ": ANN state violation");
            require(index.lastResultAudit()[i].from_delta ==
                    (reference.delta_ids.count(actual[i]) != 0), phase + ": stale source");
            if (std::find(expected.begin(), expected.end(), actual[i]) != expected.end()) ++hits;
            const float value = distance(query, found->second);
            if (value < boundary) ++closer_hits;
            else if (value == boundary) ++boundary_hits;
        }
        recall += expected.empty() ? 1 : static_cast<double>(hits) / expected.size();
        tie_recall += expected.empty() ? 1 :
            static_cast<double>(closer_hits +
              std::min<unsigned>(boundary_hits, expected.size() - closer_total)) / expected.size();
    }
    csv << graph_seed << ',' << phase << ',' << ef << ",40," << recall / 40 << ','
        << tie_recall / 40 << ',' << total_ms / 40 << ',' << graph_dist / 40.0 << ','
        << rerank_dist / 40.0 << ',' << delta_dist / 40.0 << ','
        << (graph_dist + rerank_dist + delta_dist) / 40.0 << ','
        << delta_scanned / 40.0 << ',' << insufficient << ",0\n";
}

void qualityCampaign(const fs::path &root) {
    fs::create_directories(root);
    std::ofstream csv(root / "quality_curve.csv");
    require(csv.good(), "cannot open quality results");
    csv << std::setprecision(10)
        << "graph_seed,phase,ef,queries,strict_recall,tie_recall,mean_ms,graph_dist,"
           "base_rerank_dist,delta_dist,total_dist,delta_scanned,insufficient,state_violations\n";
    for (unsigned graph_seed : {2051U, 2052U, 2053U}) {
        const auto run_root = root / ("graph_seed" + std::to_string(graph_seed));
        auto reference = initialReference();
        auto bundle = std::make_unique<Bundle>(reference.live, reference.next_id,
                                                run_root / "initial", true, graph_seed);
        for (unsigned round = 1; round <= 2; ++round) {
            auto &old = *bundle->index;
            put(old, reference, 0, generated(7000 + round));
            const auto cut_reference = reference;
            const auto capture = old.captureForRebuild();
            const auto dir = run_root / ("round" + std::to_string(round));
            writeSnapshot(dir, old);
            fixtureMutations(old, reference, round);
            const auto journal = old.journalSince(capture);
            if (round == 2) for (unsigned ef : {128U, 256U, 512U})
                measureQuality(old, reference, graph_seed, "old_active", ef, csv);
            auto disk_reference = cut_reference;
            auto replacement = reload(dir, disk_reference, graph_seed);
            replacement->index->replayAfterCapture(capture, journal);
            reference.delta_ids.clear();
            for (const auto &op : journal.operations) {
                if (op.erased) reference.delta_ids.erase(op.original_id);
                else reference.delta_ids.insert(op.original_id);
            }
            checkSnapshot(*replacement->index, reference, "quality_replayed");
            if (round == 2) for (unsigned ef : {128U, 256U, 512U})
                measureQuality(*replacement->index, reference, graph_seed,
                               "rebuilt_plus_replay", ef, csv);
            old.finishCapture(capture, journal);
            bundle = std::move(replacement);
        }
        const auto compact_dir = run_root / "compacted";
        writeSnapshot(compact_dir, *bundle->index);
        auto compacted = reload(compact_dir, reference, graph_seed);
        checkSnapshot(*compacted->index, reference, "quality_compacted");
        for (unsigned ef : {128U, 256U, 512U})
            measureQuality(*compacted->index, reference, graph_seed, "compacted", ef, csv);
        std::cout << "QUALITY PASS graph_seed=" << graph_seed << " phases=3 budgets=3 state_violations=0\n";
    }
    require(csv.good(), "quality CSV write failed");
    std::cout << "ALL PASS replay_quality_curve graph_seeds=3 rows=27\n";
}

void contractCampaign(const fs::path &root) {
    fs::create_directories(root);
    Reference reference;
    for (unsigned i = 0; i < 64; ++i) reference.live[i * 7 + 2] = generated(i);
    reference.next_id = 500;
    Bundle bundle(reference.live, reference.next_id, root / "graphs", true);
    Index none(bundle.base.get(), {}, {}, bundle.stable_ids, 0.05, 500);
    Index subset(bundle.base.get(), {bundle.graphs[2].get()}, {bundle.ranks[2]},
                 bundle.stable_ids, 0.05, 500, {2});
    const auto query = generated(17).vector;
    const unsigned changed = reference.live.begin()->first;
    auto expected_point = reference.live.at(changed);
    none.updateFields(changed, nullptr, {{1, 77}});
    subset.updateFields(changed, nullptr, {{1, 77}});
    expected_point.attrs[1] = 77;
    reference.put(changed, expected_point);
    const auto replacement_vector = generated(901).vector;
    none.updateFields(changed, replacement_vector.data(), {{2, 88}});
    subset.updateFields(changed, replacement_vector.data(), {{2, 88}});
    expected_point.vector = replacement_vector;
    expected_point.attrs[2] = 88;
    reference.put(changed, expected_point);
    mustThrow([&] { none.updateFields(changed, nullptr, {{0, 1}, {0, 2}}); }, "duplicate field accepted");
    mustThrow([&] { none.updateFields(changed, nullptr, {{3, 1}}); }, "invalid field accepted");
    for (unsigned i = 0; i < 200; ++i) {
        Point point{query, {1, 1, 1}};
        const auto id = none.insert(point.vector.data(), point.attrs);
        require(subset.insert(point.vector.data(), point.attrs) == id, "subset allocator mismatch");
        reference.put(id, point);
        if (i % 7 == 0) { none.erase(id); subset.erase(id); reference.erase(id); }
    }
    checkSnapshot(none, reference, "contract_fields");
    checkSnapshot(subset, reference, "contract_subset");
    std::ofstream csv(root / "contracts.csv");
    csv << "case,queries,state_violations\n";
    unsigned queries = 0;
    for (const auto &selection : {"none", "0", "0 1", "all"}) {
        MultiRangeQuery filter;
        filter.bounds.resize(3);
        for (auto &bound : filter.bounds) { bound.low = 0; bound.high = 12; }
        filter.selectAttributes(selection);
        for (unsigned k : {1U, 3U, 10U, 1000U}) {
            auto materialized = filter;
            materialized.active_attributes.clear();
            for (unsigned attr = 0; attr < 3; ++attr) if (!filter.constrains(attr)) {
                materialized.bounds[attr].low = -10000;
                materialized.bounds[attr].high = 10000;
            }
            const auto expected = referenceQuery(reference, query, materialized, k);
            require(none.search(query.data(), filter, k, 128) == expected,
                    "empty deployment differs from independent full sort");
            require(none.lastStats().exact_fallback && none.lastStats().delta_candidates_retained <= k &&
                    none.lastStats().merge_candidates <= none.lastStats().base_candidates + k,
                    "fallback/Delta heap bound violated");
            const auto actual = subset.search(query.data(), filter, k, 128);
            if (!filter.constrains(2)) require(actual == expected && subset.lastStats().exact_fallback,
                                             "disjoint deployment did not fall back exactly");
            else require(!subset.lastStats().exact_fallback && subset.lastStats().navigation_attr == 2,
                         "attribute ID confused with subset slot");
            for (auto id : actual) require(reference.live.count(id) && passes(reference.live.at(id), materialized),
                                          "subset result violates committed state");
            queries += 2;
        }
    }
    csv << "deployment_fields_ties_and_heap," << queries << ",0\n";
    // Capture a partially deployed instance, then replay a field-only update.
    const auto captured_reference = reference;
    const auto capture = subset.captureForRebuild();
    subset.updateFields(changed, nullptr, {{0, 999}});
    reference.live.at(changed).attrs[0] = 999;
    reference.delta_ids.insert(changed);
    const auto journal = subset.journalSince(capture);
    Bundle replacement(captured_reference.live, capture.next_original_id);
    replacement.index->replayAfterCapture(capture, journal);
    checkSnapshot(*replacement.index, reference, "contract_subset_replay");
    require(csv.good(), "contract CSV write failed");
    std::cout << "ALL PASS deployment_fields_ties_and_heap queries=" << queries << " state_violations=0\n";
}

int main(int argc, char **argv) {
    try {
        require(argc == 3, "Usage: test_dynamic_replay_followup random|quality|contracts OUTPUT_DIR");
        const fs::path root(argv[2]);
        if (std::string(argv[1]) == "random") randomCampaign(root);
        else if (std::string(argv[1]) == "quality") qualityCampaign(root);
        else if (std::string(argv[1]) == "contracts") contractCampaign(root);
        else throw std::runtime_error("unknown test mode");
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
