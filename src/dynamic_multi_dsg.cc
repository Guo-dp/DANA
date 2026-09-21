#include "dynamic_multi_dsg.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>

namespace dsg {

DynamicMultiDsgIndex::DynamicMultiDsgIndex(
    const DataWrapper *base_data,
    std::vector<DynamicSegmentGraph *> indexes,
    std::vector<std::vector<unsigned>> rank_to_base_local,
    std::vector<unsigned> base_local_to_original,
    double rebuild_fraction)
    : base_data_(base_data),
      indexes_(std::move(indexes)),
      rank_to_base_local_(std::move(rank_to_base_local)),
      base_local_to_original_(
          std::move(base_local_to_original)),
      rebuild_fraction_(rebuild_fraction) {

    if (base_data_ == nullptr) {
        throw std::runtime_error(
            "DynamicMultiDsgIndex requires base data");
    }

    if (indexes_.empty() ||
        indexes_.size() != rank_to_base_local_.size()) {
        throw std::runtime_error(
            "Index and rank-mapping counts do not match");
    }

    if (indexes_.size() != base_data_->attr_count) {
        throw std::runtime_error(
            "One DSG is required for each attribute");
    }

    if (rebuild_fraction_ <= 0.0) {
        throw std::runtime_error(
            "rebuild_fraction must be positive");
    }

    if (base_local_to_original_.empty()) {
        base_local_to_original_.resize(
            static_cast<std::size_t>(
                base_data_->data_size));

        for (unsigned local_id = 0;
             local_id <
                 static_cast<unsigned>(
                     base_data_->data_size);
             ++local_id) {
            base_local_to_original_[local_id] =
                local_id;
        }
    }

    if (base_local_to_original_.size() !=
        static_cast<std::size_t>(
            base_data_->data_size)) {
        throw std::runtime_error(
            "Base stable-ID mapping size mismatch");
    }

    unsigned maximum_stable_id = 0;

    for (const unsigned stable_id :
         base_local_to_original_) {
        maximum_stable_id =
            std::max(maximum_stable_id, stable_id);
    }

    next_original_id_ =
        base_local_to_original_.empty()
            ? 0
            : maximum_stable_id + 1;
}

unsigned DynamicMultiDsgIndex::insert(
    const float *vector,
    const std::vector<float> &attrs) {

    const unsigned original_id = next_original_id_++;

    insertWithId(original_id, vector, attrs);
    return original_id;
}

void DynamicMultiDsgIndex::insertWithId(
    unsigned original_id,
    const float *vector,
    const std::vector<float> &attrs) {

    if (vector == nullptr) {
        throw std::runtime_error(
            "Cannot insert a null vector");
    }

    if (attrs.size() != base_data_->attr_count) {
        throw std::runtime_error(
            "Inserted attribute count mismatch");
    }

    if (original_id <
        static_cast<unsigned>(base_data_->data_size)) {
        base_tombstones_.insert(original_id);
    }

    DeltaPoint point;
    point.original_id = original_id;
    point.vector.assign(
        vector,
        vector + base_data_->data_dim);
    point.attrs = attrs;
    point.version = next_version_++;

    delta_[original_id] = std::move(point);

    next_original_id_ =
        std::max(next_original_id_, original_id + 1);
}

void DynamicMultiDsgIndex::update(
    unsigned original_id,
    const float *vector,
    const std::vector<float> &attrs) {

    if (original_id >= next_original_id_ &&
        delta_.find(original_id) == delta_.end()) {
        throw std::runtime_error(
            "Cannot update an unknown ID");
    }

    insertWithId(original_id, vector, attrs);
}

void DynamicMultiDsgIndex::updateAttributes(
    unsigned original_id,
    const std::vector<float> &attrs) {

    auto delta_it = delta_.find(original_id);

    if (delta_it != delta_.end()) {
        insertWithId(
            original_id,
            delta_it->second.vector.data(),
            attrs);
        return;
    }

    if (original_id >=
        static_cast<unsigned>(base_data_->data_size)) {
        throw std::runtime_error(
            "Cannot update attributes of an unknown ID");
    }

    insertWithId(
        original_id,
        base_data_->nodes[original_id],
        attrs);
}

void DynamicMultiDsgIndex::erase(unsigned original_id) {
    delta_.erase(original_id);

    if (original_id <
        static_cast<unsigned>(base_data_->data_size)) {
        base_tombstones_.insert(original_id);
    }
}

unsigned DynamicMultiDsgIndex::stableIdOfBaseLocal(
    unsigned base_local_id) const {

    if (base_local_id >=
        base_local_to_original_.size()) {
        throw std::runtime_error(
            "Base local ID is out of range");
    }

    return base_local_to_original_[base_local_id];
}

bool DynamicMultiDsgIndex::deltaPassesFilter(
    const DeltaPoint &point,
    const MultiRangeQuery &filter) const {

    if (point.attrs.size() != filter.bounds.size()) {
        return false;
    }

    for (std::size_t attr = 0;
         attr < point.attrs.size();
         ++attr) {
        const float value = point.attrs[attr];

        if (value < filter.bounds[attr].low ||
            value > filter.bounds[attr].high) {
            return false;
        }
    }

    return true;
}

float DynamicMultiDsgIndex::squaredL2(
    const float *left,
    const float *right) const {

    float distance = 0.0F;

    for (std::size_t dim = 0;
         dim < base_data_->data_dim;
         ++dim) {
        const float difference =
            left[dim] - right[dim];

        distance += difference * difference;
    }

    return distance;
}

unsigned DynamicMultiDsgIndex::chooseNavigationAttribute(
    const MultiRangeQuery &filter) const {

    unsigned best_attr = 0;
    std::size_t best_span =
        std::numeric_limits<std::size_t>::max();

    for (unsigned attr = 0;
         attr < indexes_.size();
         ++attr) {
        const auto range =
            base_data_->valueRangeToRankRange(
                attr,
                filter.bounds[attr].low,
                filter.bounds[attr].high);

        if (range.first > range.second) {
            return attr;
        }

        const std::size_t span =
            static_cast<std::size_t>(
                range.second - range.first + 1);

        if (span < best_span) {
            best_span = span;
            best_attr = attr;
        }
    }

    return best_attr;
}

std::vector<unsigned> DynamicMultiDsgIndex::search(
    const float *query,
    const MultiRangeQuery &filter,
    unsigned top_k,
    unsigned search_ef) {

    last_result_audit_.clear();

    if (query == nullptr || top_k == 0) {
        return {};
    }

    if (filter.bounds.size() !=
        base_data_->attr_count) {
        throw std::runtime_error(
            "Query attribute count mismatch");
    }

    last_stats_ = SearchStats{};
    last_stats_.tombstones =
        base_tombstones_.size();

    const auto base_start =
        std::chrono::steady_clock::now();

    const unsigned navigation_attr =
        chooseNavigationAttribute(filter);

    last_stats_.navigation_attr =
        navigation_attr;

    const auto rank_bound =
        base_data_->valueRangeToRankRange(
            navigation_attr,
            filter.bounds[navigation_attr].low,
            filter.bounds[navigation_attr].high);

    struct Candidate {
        float distance = 0.0F;
        unsigned original_id = 0;
        std::uint64_t version = 0;
        bool from_delta = false;
    };

    std::vector<Candidate> merged;

    if (rank_bound.first <= rank_bound.second) {
        DynamicSegmentGraph *index =
            indexes_.at(navigation_attr);

        // Start with K candidates. Retry only when tombstones
        // remove too many results from this specific query.
        unsigned requested = top_k;
        const unsigned maximum_requested =
            static_cast<unsigned>(base_data_->data_size);

        while (true) {
            index->setQueryTopK(requested);
            index->setSearchEf(
                std::max(search_ef, requested));

            index->rangeSearchMultiDsg(
                query,
                {static_cast<int>(rank_bound.first),
                 static_cast<int>(rank_bound.second)},
                filter,
                base_data_,
                rank_to_base_local_.at(navigation_attr));

            std::vector<Candidate> valid_base;

            valid_base.reserve(
                index->returned_nns.size());

            for (const unsigned base_local_id :
                 index->returned_nns) {
                const unsigned stable_id =
                    stableIdOfBaseLocal(base_local_id);

                if (base_tombstones_.find(stable_id) !=
                    base_tombstones_.end()) {
                    continue;
                }

                valid_base.push_back({
                    squaredL2(
                        query,
                        base_data_->nodes[base_local_id]),
                    stable_id,
                    0,
                    false});
            }

            last_stats_.base_candidates =
                index->returned_nns.size();

            if (valid_base.size() >= top_k ||
                requested >= maximum_requested ||
                index->returned_nns.size() < requested) {
                merged.insert(
                    merged.end(),
                    valid_base.begin(),
                    valid_base.end());
                break;
            }

            const unsigned next_requested =
                std::min(
                    maximum_requested,
                    std::max(
                        requested + 1,
                        requested * 2));

            if (next_requested == requested) {
                merged.insert(
                    merged.end(),
                    valid_base.begin(),
                    valid_base.end());
                break;
            }

            requested = next_requested;
        }
    }

    const auto base_end =
        std::chrono::steady_clock::now();

    last_stats_.base_search_ms =
        std::chrono::duration<double, std::milli>(
            base_end - base_start).count();

    const auto delta_start = base_end;

    last_stats_.delta_scanned = delta_.size();

    for (const auto &entry : delta_) {
        const DeltaPoint &point = entry.second;

        if (!deltaPassesFilter(point, filter)) {
            continue;
        }

        merged.push_back({
            squaredL2(query, point.vector.data()),
            point.original_id,
            point.version,
            true});
    }

    const auto delta_end =
        std::chrono::steady_clock::now();

    last_stats_.delta_scan_ms =
        std::chrono::duration<double, std::milli>(
            delta_end - delta_start).count();

    const auto merge_start = delta_end;

    std::sort(
        merged.begin(),
        merged.end(),
        [](const Candidate &left, const Candidate &right) {
            if (left.distance != right.distance) {
                return left.distance < right.distance;
            }
            return left.original_id < right.original_id;
        });

    std::vector<unsigned> result;
    result.reserve(
        std::min<std::size_t>(top_k, merged.size()));

    std::unordered_set<unsigned> emitted;

    for (const auto &candidate : merged) {
        if (!emitted.insert(candidate.original_id).second) {
            continue;
        }

        result.push_back(candidate.original_id);
        last_result_audit_.push_back({
            candidate.original_id,
            candidate.version,
            candidate.from_delta});

        if (result.size() == top_k) {
            break;
        }
    }

    const auto merge_end =
        std::chrono::steady_clock::now();

    last_stats_.merge_ms =
        std::chrono::duration<double, std::milli>(
            merge_end - merge_start).count();

    return result;
}

bool DynamicMultiDsgIndex::needsRebuild() const {
    // Count each changed original ID only once.
    std::size_t changed = base_tombstones_.size();

    for (const auto &entry : delta_) {
        if (base_tombstones_.find(entry.first) ==
            base_tombstones_.end()) {
            ++changed;
        }
    }

    const double threshold =
        static_cast<double>(base_data_->data_size) *
        rebuild_fraction_;

    return static_cast<double>(changed) >=
           std::max(1.0, threshold);
}


std::vector<unsigned> DynamicMultiDsgIndex::searchExact(
    const float *query,
    const MultiRangeQuery &filter,
    unsigned top_k) const {

    if (query == nullptr || top_k == 0) {
        return {};
    }

    std::vector<std::pair<float, unsigned>> candidates;

    // Base中仍然有效的版本。
    for (unsigned base_local_id = 0;
         base_local_id <
             static_cast<unsigned>(base_data_->data_size);
         ++base_local_id) {

        const unsigned stable_id =
            stableIdOfBaseLocal(base_local_id);

        if (base_tombstones_.find(stable_id) !=
            base_tombstones_.end()) {
            continue;
        }

        if (!base_data_->passFilter(
                base_local_id, filter)) {
            continue;
        }

        candidates.emplace_back(
            squaredL2(
                query,
                base_data_->nodes[base_local_id]),
            stable_id);
    }

    // Delta中的插入或最新更新版本。
    for (const auto &entry : delta_) {
        const DeltaPoint &point = entry.second;

        if (!deltaPassesFilter(point, filter)) {
            continue;
        }

        candidates.emplace_back(
            squaredL2(query, point.vector.data()),
            point.original_id);
    }

    std::sort(
        candidates.begin(),
        candidates.end(),
        [](const auto &left, const auto &right) {
            if (left.first != right.first) {
                return left.first < right.first;
            }
            return left.second < right.second;
        });

    std::vector<unsigned> result;
    result.reserve(
        std::min<std::size_t>(
            top_k, candidates.size()));

    std::unordered_set<unsigned> emitted;

    for (const auto &candidate : candidates) {
        if (!emitted.insert(candidate.second).second) {
            continue;
        }

        result.push_back(candidate.second);

        if (result.size() == top_k) {
            break;
        }
    }

    return result;
}



std::vector<DynamicMultiDsgIndex::SnapshotPoint>
DynamicMultiDsgIndex::createSnapshot() const {

    std::vector<SnapshotPoint> snapshot;

    snapshot.reserve(
        static_cast<std::size_t>(base_data_->data_size) +
        delta_.size());

    // Base中仍然有效且没有被Delta覆盖的版本。
    for (unsigned base_local_id = 0;
         base_local_id <
             static_cast<unsigned>(base_data_->data_size);
         ++base_local_id) {

        const unsigned stable_id =
            stableIdOfBaseLocal(base_local_id);

        if (base_tombstones_.find(stable_id) !=
            base_tombstones_.end()) {
            continue;
        }

        SnapshotPoint point;
        point.original_id = stable_id;
        point.version = 0;

        point.vector.assign(
            base_data_->nodes[base_local_id],
            base_data_->nodes[base_local_id] +
                base_data_->data_dim);

        point.attrs.resize(base_data_->attr_count);

        for (unsigned attr = 0;
             attr < base_data_->attr_count;
             ++attr) {
            point.attrs[attr] =
                base_data_->attrs[attr][base_local_id];
        }

        snapshot.push_back(std::move(point));
    }

    // Delta保存所有新点和更新后的最新版本。
    for (const auto &entry : delta_) {
        const DeltaPoint &delta_point = entry.second;

        SnapshotPoint point;
        point.original_id =
            delta_point.original_id;
        point.vector =
            delta_point.vector;
        point.attrs =
            delta_point.attrs;
        point.version =
            delta_point.version;

        snapshot.push_back(std::move(point));
    }

    std::sort(
        snapshot.begin(),
        snapshot.end(),
        [](const SnapshotPoint &left,
           const SnapshotPoint &right) {
            return left.original_id <
                   right.original_id;
        });

    return snapshot;
}


} // namespace dsg
