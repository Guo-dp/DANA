#define DANA_STABLE_ID_HELPERS_ONLY
#include "test_dynamic_stable_ids.cpp"
#include <chrono>
#include <sstream>
#include <malloc.h>

using Clock = std::chrono::steady_clock;
double elapsed(Clock::time_point t) {
    return std::chrono::duration<double, std::milli>(Clock::now() - t).count();
}
Reference initialReference() {
    Reference r;
    for (unsigned id = 0; id < 1000; ++id) r.live[id] = generated(id);
    r.next_id = 1000;
    return r;
}
std::size_t rssKiB() {
    std::ifstream input("/proc/self/status");
    std::string line;
    while (std::getline(input, line)) if (line.rfind("VmRSS:", 0) == 0) {
        std::size_t value = 0;
        std::istringstream(line.substr(6)) >> value;
        return value;
    }
    return 0;
}
std::size_t heapBytes() {
#if defined(__GLIBC__) && __GLIBC_PREREQ(2, 33)
    return mallinfo2().uordblks;
#else
    return 0;
#endif
}

#ifndef DANA_REPLAY_PERF_BASELINE
void correctness(const fs::path &root) {
    auto reference = initialReference();
    auto bundle = std::make_unique<Bundle>(reference.live, reference.next_id, root / "initial", true);
    unsigned total = 0, visibility = 0;
    for (unsigned round = 1; round <= 2; ++round) {
        auto &old = *bundle->index;
        const auto phase = "round" + std::to_string(round);
        put(old, reference, 0, generated(7000 + round));
        checkSnapshot(old, reference, phase + "_cut");
        const auto cut_reference = reference;
        const auto capture = old.captureForRebuild();
        mustThrow([&] { old.captureForRebuild(); }, "overlapping capture accepted");
        writeSnapshot(root / phase, old);
        erase(old, reference, round);
        put(old, reference, 10, generated(8000 + round));
        old.updateAttributes(11, {70, 80, 90});
        reference.attributes(11, {70, 80, 90});
        const auto temporary = insert(old, reference, generated(8100 + round));
        erase(old, reference, temporary);
        require(insert(old, reference, generated(8200 + round)) > temporary, "maximum ID reused");
        put(old, reference, 12 + round, generated(8300 + round));
        put(old, reference, 12 + round, generated(8400 + round));
        erase(old, reference, 12 + round);
        for (unsigned id = 30; id < 50; ++id) put(old, reference, id, generated(9000 + round * 100 + id));
        for (unsigned id = 50; id < 60; ++id) erase(old, reference, id);
        const auto before = old.journalSince(capture).end_sequence;
        mustThrow([&] { old.updateAttributes(round, {1, 2, 3}); }, "deleted ID revived");
        mustThrow([&] { old.insert(nullptr, {1, 2, 3}); }, "invalid insert logged");
        require(old.journalSince(capture).end_sequence == before, "failed operation advanced sequence");
        const auto earlier_batch = old.journalSince(capture);
        put(old, reference, 20, generated(9500 + round));
        mustThrow([&] { old.finishCapture(capture, earlier_batch); }, "unacknowledged writes discarded");
        const auto journal = old.journalSince(capture);
        total += journal.operations.size();
        std::ofstream trace(root / (phase + "_operations.csv"));
        trace << "sequence,id,kind,version,vector,attributes\n";
        for (const auto &op : journal.operations) {
            trace << op.sequence << ',' << op.original_id << ',' << (op.erased ? "erase" : "upsert")
                  << ',' << op.version << ',';
            for (float v : op.vector) trace << v << ' ';
            trace << ',';
            for (float v : op.attrs) trace << v << ' ';
            trace << '\n';
        }
        checkSnapshot(old, reference, phase + "_old_committed");
        checkQueries(old, reference, phase + "_old_committed", true);
        auto disk_reference = cut_reference;
        auto replacement = reload(root / phase, disk_reference);
        auto &fresh = *replacement->index;
        auto broken = journal;
        broken.operations.pop_back();
        mustThrow([&] { fresh.replayAfterCapture(capture, broken); }, "truncated suffix accepted");
        broken = journal; ++broken.operations.front().sequence;
        mustThrow([&] { fresh.replayAfterCapture(capture, broken); }, "out of order accepted");
        broken = journal; broken.operations[1].vector.pop_back();
        mustThrow([&] { fresh.replayAfterCapture(capture, broken); }, "malformed image accepted");
        broken = journal; --broken.next_original_id;
        mustThrow([&] { fresh.replayAfterCapture(capture, broken); }, "bad watermark accepted");
        broken = journal; ++broken.token;
        mustThrow([&] { fresh.replayAfterCapture(capture, broken); }, "foreign token accepted");
        auto bad_capture = capture;
        bad_capture.points.front().vector.front() += 1;
        mustThrow([&] { fresh.replayAfterCapture(bad_capture, journal); }, "different captured state accepted");
        checkSnapshot(fresh, disk_reference, phase + "_invalid_batches_unchanged");
        fresh.replayAfterCapture(capture, journal);
        reference.delta_ids.clear();
        std::map<unsigned, std::uint64_t> versions;
        for (const auto &op : journal.operations) {
            if (op.erased) { reference.delta_ids.erase(op.original_id); versions.erase(op.original_id); }
            else { reference.delta_ids.insert(op.original_id); versions[op.original_id] = op.version; }
        }
        checkSnapshot(fresh, reference, phase + "_replayed");
        checkQueries(fresh, reference, phase + "_replayed", true);
        MultiRangeQuery filter;
        filter.bounds.resize(3);
        for (auto &b : filter.bounds) { b.low = -1000; b.high = 1000; }
        for (const auto &entry : versions) {
            const auto &point = reference.live.at(entry.first);
            const auto exact = fresh.searchExact(point.vector.data(), filter, reference.live.size());
            require(std::find(exact.begin(), exact.end(), entry.first) != exact.end(), "visibility violation");
            ++visibility;
            fresh.search(point.vector.data(), filter, 10, 128);
            for (const auto &audit : fresh.lastResultAudit()) if (audit.original_id == entry.first)
                require(audit.from_delta && audit.version == entry.second, "stale version number");
        }
        mustThrow([&] { fresh.replayAfterCapture(capture, journal); }, "duplicate replay accepted");
        old.finishCapture(capture, journal);
        mustThrow([&] { old.journalSince(capture); }, "finished capture usable");
        bundle = std::move(replacement);
    }
    insert(*bundle->index, reference, generated(9900));
    checkSnapshot(*bundle->index, reference, "after_two_replays_insert");
    checkQueries(*bundle->index, reference, "after_two_replays_insert", true);
    Bundle empty_source(reference.live, reference.next_id), empty_target(reference.live, reference.next_id);
    const auto empty_capture = empty_source.index->captureForRebuild();
    const auto empty_journal = empty_source.index->journalSince(empty_capture);
    empty_target.index->replayAfterCapture(empty_capture, empty_journal);
    checkSnapshot(*empty_target.index, reference, "empty_journal");
    mustThrow([&] { empty_target.index->replayAfterCapture(empty_capture, empty_journal); }, "empty journal replayed twice");
    empty_source.index->finishCapture(empty_capture, empty_journal);
    std::cout << "CAPTURE REPLAY PASS rounds=2 operations=" << total << " visibility_checks=" << visibility
              << " deleted_id_violations=0 duplicate_id_violations=0 predicate_violations=0"
              << " invalid_id_violations=0 stale_version_violations=0 visibility_violations=0"
              << " allocator_violations=0\nALL PASS sequential_capture_replay\n";
}
#endif

void performance(const fs::path &root, unsigned run, bool logging) {
#ifdef DANA_REPLAY_PERF_BASELINE
    const std::string variant = "v3_baseline";
#else
    const std::string variant = logging ? "journal_on" : "journal_off";
#endif
    std::ofstream csv(root / "performance.csv");
    csv << std::setprecision(10)
        << "variant,run,metric,operations,total_ms,per_op_us,rss_delta_kib,heap_delta_bytes,recall\n";
    auto row = [&](const std::string &metric, unsigned count, double ms,
                   std::size_t rss_before, std::size_t heap_before, double recall = -1) {
        csv << variant << ',' << run << ',' << metric << ',' << count << ',' << ms << ','
            << (count ? ms * 1000 / count : 0) << ','
            << static_cast<long long>(rssKiB()) - static_cast<long long>(rss_before) << ','
            << static_cast<long long>(heapBytes()) - static_cast<long long>(heap_before) << ',' << recall << '\n';
    };
    auto reference = initialReference();
    Bundle bundle(reference.live, reference.next_id, root / "initial", true);
    auto &index = *bundle.index;
    std::vector<dsg::DynamicSegmentGraph *> graphs;
    for (auto &g : bundle.graphs) graphs.push_back(g.get());
    auto rss = rssKiB(), heap = heapBytes();
    std::vector<std::unique_ptr<Index>> replicas;
    replicas.reserve(64);
    auto start = Clock::now();
    for (unsigned i = 0; i < 64; ++i)
        replicas.push_back(std::make_unique<Index>(bundle.base.get(), graphs, bundle.ranks,
                                                 bundle.stable_ids, 0.05, reference.next_id));
    const auto init_ms = elapsed(start);
    row("initialize_64", 64, init_ms, rss, heap);
    replicas.clear();
    auto queries = [&](Index &target, const std::string &phase) {
        checkQueries(target, reference, phase, true);
        std::vector<std::vector<float>> probes;
        std::vector<MultiRangeQuery> filters;
        std::vector<std::vector<unsigned>> expected;
        for (unsigned q = 0; q < 40; ++q) {
            probes.push_back(generated(q * 19).vector);
            MultiRangeQuery f; f.bounds.resize(3);
            for (auto &b : f.bounds) { b.low = -1000; b.high = 1000; }
            if (q % 3) { f.bounds[q % 3].low = q % 7; f.bounds[q % 3].high = q % 7 + 5; }
            filters.push_back(f);
            expected.push_back(referenceQuery(reference, probes.back(), f, 10));
        }
        for (unsigned q = 0; q < 40; ++q) target.search(probes[q].data(), filters[q], 10, 128);
        double total_ms = 0, recall = 0;
        for (unsigned r = 0; r < 10; ++r) for (unsigned q = 0; q < 40; ++q) {
            auto t = Clock::now();
            const auto actual = target.search(probes[q].data(), filters[q], 10, 128);
            total_ms += elapsed(t);
            unsigned hits = 0;
            for (auto id : actual) if (std::find(expected[q].begin(), expected[q].end(), id) != expected[q].end()) ++hits;
            recall += expected[q].empty() ? 1.0 : static_cast<double>(hits) / expected[q].size();
        }
        row(phase, 400, total_ms, rssKiB(), heapBytes(), recall / 400);
    };
    queries(index, "query_base");
#ifndef DANA_REPLAY_PERF_BASELINE
    Index::RebuildCapture capture;
    if (logging) {
        rss = rssKiB(); heap = heapBytes(); start = Clock::now();
        capture = index.captureForRebuild();
        row("capture", 1, elapsed(start), rss, heap);
    }
#endif
    std::vector<Point> inserted, updated;
    for (unsigned i = 0; i < 100; ++i) { inserted.push_back(generated(10000 + i)); updated.push_back(generated(11000 + i)); }
    rss = rssKiB(); heap = heapBytes(); start = Clock::now();
    for (unsigned i = 0; i < 100; ++i) index.insert(inserted[i].vector.data(), inserted[i].attrs);
    row("insert", 100, elapsed(start), rss, heap);
    for (unsigned i = 0; i < 100; ++i) reference.put(1000 + i, inserted[i]);
    rss = rssKiB(); heap = heapBytes(); start = Clock::now();
    for (unsigned i = 0; i < 100; ++i) index.update(i, updated[i].vector.data(), updated[i].attrs);
    row("update", 100, elapsed(start), rss, heap);
    for (unsigned i = 0; i < 100; ++i) reference.put(i, updated[i]);
    rss = rssKiB(); heap = heapBytes(); start = Clock::now();
    for (unsigned i = 100; i < 200; ++i) index.erase(i);
    row("erase", 100, elapsed(start), rss, heap);
    for (unsigned i = 100; i < 200; ++i) reference.erase(i);
    checkSnapshot(index, reference, variant + "_mutated");
    queries(index, "query_mutated");
#ifndef DANA_REPLAY_PERF_BASELINE
    if (logging) {
        rss = rssKiB(); heap = heapBytes(); start = Clock::now();
        const auto journal = index.journalSince(capture);
        row("journal_copy", journal.operations.size(), elapsed(start), rss, heap);
        auto captured_reference = initialReference();
        Bundle cut(captured_reference.live, capture.next_original_id);
        start = Clock::now(); writeSnapshot(root / "captured", *cut.index);
        row("snapshot_write", 1, elapsed(start), rssKiB(), heapBytes());
        start = Clock::now(); auto rebuilt = reload(root / "captured", captured_reference);
        row("rebuild_and_reload", 1, elapsed(start), rssKiB(), heapBytes());
        rss = rssKiB(); heap = heapBytes(); start = Clock::now();
        rebuilt->index->replayAfterCapture(capture, journal);
        row("replay", journal.operations.size(), elapsed(start), rss, heap);
        checkSnapshot(*rebuilt->index, reference, "perf_replayed");
        queries(*rebuilt->index, "query_replayed");
        index.finishCapture(capture, journal);
        start = Clock::now(); writeSnapshot(root / "compacted", *rebuilt->index);
        auto compacted = reload(root / "compacted", reference);
        row("compaction_and_reload", 1, elapsed(start), rssKiB(), heapBytes());
        checkSnapshot(*compacted->index, reference, "perf_compacted");
        queries(*compacted->index, "query_compacted");
    }
#endif
    require(csv.good(), "CSV write failed");
    std::cout << "ALL PASS light_performance_regression\n";
}

int main(int argc, char **argv) {
    try {
        require(argc >= 3, "Usage: test_dynamic_capture_replay correctness|perf ROOT [RUN] [logging]");
        const fs::path root(argv[2]); fs::create_directories(root);
#ifndef DANA_REPLAY_PERF_BASELINE
        if (std::string(argv[1]) == "correctness") { correctness(root); return 0; }
#endif
        require(std::string(argv[1]) == "perf", "Unknown mode");
        performance(root, argc > 3 ? std::stoul(argv[3]) : 1, argc > 4 && std::string(argv[4]) == "logging");
        return 0;
    } catch (const std::exception &error) { std::cerr << "FAIL " << error.what() << '\n'; return 1; }
}
