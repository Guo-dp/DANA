#pragma once

#include <cstddef>
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

class DynamicMultiDsgIndex {
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
        unsigned navigation_attr = 0;
        double base_search_ms = 0.0;
        double delta_scan_ms = 0.0;
        double merge_ms = 0.0;
    };

    struct SnapshotPoint {
        unsigned original_id = 0;
        std::vector<float> vector;
        std::vector<float> attrs;
    };

    DynamicMultiDsgIndex(
        const DataWrapper *base_data,
        std::vector<DynamicSegmentGraph *> indexes,
        std::vector<std::vector<unsigned>> rank_to_base_local,
        std::vector<unsigned> base_local_to_original = {},
        double rebuild_fraction = 0.05);

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

    unsigned nextOriginalId() const {
        return next_original_id_;
    }

    const SearchStats &lastStats() const {
        return last_stats_;
    }

private:
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

    std::unordered_map<unsigned, DeltaPoint> delta_;
    std::unordered_set<unsigned> base_tombstones_;

    unsigned next_original_id_ = 0;
    std::uint64_t next_version_ = 1;
    double rebuild_fraction_ = 0.05;

    SearchStats last_stats_;
};

} // namespace dsg
