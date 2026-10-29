#pragma once

#include <cstddef>
#include <cstdint>
#include <queue>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "data_wrapper.h"
#include "dsg.h"
#include "filter_query.h"

namespace dsg {

class DynamicDanaIndex {
public:
    struct DeltaPoint {
        unsigned original_id = 0;
        std::vector<float> vector;
        std::vector<float> attrs;
        std::uint64_t version = 0;
    };

    struct SearchStats {
        std::size_t base_candidates = 0;
        std::size_t delta_scanned = 0;
        std::size_t tombstones = 0;
        std::size_t graph_distance_evaluations = 0;
        std::size_t base_rerank_distance_evaluations = 0;
        std::size_t delta_distance_evaluations = 0;
        std::size_t delta_candidates_retained = 0;
        std::size_t merge_candidates = 0;
        bool exact_fallback = false;
        unsigned navigation_attr = 0;
        double base_search_ms = 0.0;
        double delta_scan_ms = 0.0;
        double merge_ms = 0.0;
    };

    struct SnapshotPoint {
        unsigned original_id = 0;
        std::vector<float> vector;
        std::vector<float> attrs;
        std::uint64_t version = 0;
    };

    struct ResultAudit {
        unsigned original_id = 0;
        std::uint64_t version = 0;
        bool from_delta = false;
    };

    // Sequential, in-memory rebuild handoff. Upserts store complete point images,
    // including attribute-only updates; this is not a durable write-ahead log.
    struct Mutation {
        std::uint64_t sequence = 0;
        unsigned original_id = 0;
        bool erased = false;
        std::vector<float> vector;
        std::vector<float> attrs;
        std::uint64_t version = 0;
    };
    struct RebuildCapture {
        std::vector<SnapshotPoint> points;
        std::uint64_t sequence = 0;
        std::uint64_t next_original_id = 0;
        std::uint64_t next_version = 1;
        std::uint64_t token = 0;
    };
    struct RebuildJournal {
        std::vector<Mutation> operations;
        std::uint64_t token = 0;
        std::uint64_t end_sequence = 0;
        std::uint64_t next_original_id = 0;
        std::uint64_t next_version = 1;
    };

    RebuildCapture captureForRebuild();
    RebuildJournal journalSince(const RebuildCapture &capture) const;
    // Retire only the acknowledged batch; reject writes after its exported cut.
    void finishCapture(const RebuildCapture &capture,
                       const RebuildJournal &acknowledged);
    void replayAfterCapture(const RebuildCapture &capture,
                            const RebuildJournal &journal);

    DynamicDanaIndex(
        const DataWrapper *base_data,
        std::vector<DynamicSegmentGraph *> indexes,
        std::vector<std::vector<unsigned>> rank_to_base_local,
        std::vector<unsigned> base_local_to_original = {},
        double rebuild_fraction = 0.05,
        std::uint64_t next_original_id = 0,
        std::vector<unsigned> indexed_attributes = {});

    unsigned insert(const float *vector,
                    const std::vector<float> &attrs);

    void insertWithId(unsigned original_id,
                      const float *vector,
                      const std::vector<float> &attrs);

    void update(unsigned original_id,
                const float *vector,
                const std::vector<float> &attrs);

    void updateAttributes(unsigned original_id,
                          const std::vector<float> &attrs);

    void updateFields(unsigned original_id, const float *vector,
                      const std::vector<std::pair<unsigned, float>> &attributes);

    void erase(unsigned original_id);

    std::vector<unsigned> search(
        const float *query,
        const MultiRangeQuery &filter,
        unsigned top_k,
        unsigned search_ef);

    std::vector<unsigned> searchExact(
        const float *query,
        const MultiRangeQuery &filter,
        unsigned top_k) const;

    bool needsRebuild() const;

    std::vector<SnapshotPoint> createSnapshot() const;

    std::size_t deltaSize() const {
        return delta_.size();
    }

    std::size_t tombstoneCount() const {
        return base_tombstones_.size();
    }

    std::uint64_t nextOriginalId() const {
        return next_original_id_;
    }

    const SearchStats &lastStats() const {
        return last_stats_;
    }

    const std::vector<ResultAudit> &lastResultAudit() const {
        return last_result_audit_;
    }

private:
    void prepareMutation();
    void requireActiveCapture(const RebuildCapture &capture) const;
    bool deltaPassesFilter(
        const DeltaPoint &point,
        const MultiRangeQuery &filter) const;

    unsigned stableIdOfBaseLocal(
        unsigned base_local_id) const;

    float squaredL2(const float *left,
                    const float *right) const;

    unsigned chooseNavigationAttribute(
        const MultiRangeQuery &filter) const;

    const DataWrapper *base_data_ = nullptr;
    std::vector<DynamicSegmentGraph *> indexes_;
    // Attribute rank -> current Base snapshot local ID.
    std::vector<std::vector<unsigned>> rank_to_base_local_;

    // Current Base snapshot local ID -> stable original ID.
    std::vector<unsigned> base_local_to_original_;
    std::unordered_map<unsigned, unsigned> original_to_base_local_;

    std::unordered_map<unsigned, DeltaPoint> delta_;
    std::unordered_set<unsigned> base_tombstones_;

    // Persist this high-water mark even when the largest allocated ID is deleted.
    std::uint64_t next_original_id_ = 0;
    bool allocator_history_known_ = true;
    std::uint64_t next_version_ = 1;
    double rebuild_fraction_ = 0.05;

    std::uint64_t committed_sequence_ = 0;
    std::uint64_t capture_generation_ = 0;
    std::uint64_t active_capture_token_ = 0;
    std::uint64_t capture_sequence_ = 0;
    bool replay_installed_ = false;
    std::vector<Mutation> journal_;

    SearchStats last_stats_;
    std::vector<ResultAudit> last_result_audit_;
};

} // namespace dsg
