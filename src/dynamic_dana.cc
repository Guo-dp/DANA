#include "dynamic_dana.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>

namespace dsg {

DynamicDanaIndex::DynamicDanaIndex(
    const DataWrapper *base_data,
    std::vector<DynamicSegmentGraph *> indexes,
    std::vector<std::vector<unsigned>> rank_to_base_local,
    std::vector<unsigned> base_local_to_original,
    double rebuild_fraction,
    std::uint64_t next_original_id,
    std::vector<unsigned> indexed_attributes)
    : base_data_(base_data),
      indexes_(std::move(indexes)),
      rank_to_base_local_(std::move(rank_to_base_local)),
      base_local_to_original_(
          std::move(base_local_to_original)),
      rebuild_fraction_(rebuild_fraction) {

    if (base_data_ == nullptr) {
        throw std::runtime_error(
            "DynamicDanaIndex requires base data");
    }

    if (indexes_.size() != rank_to_base_local_.size()) {
        throw std::runtime_error(
            "Index and rank-mapping counts do not match");
    }

    if (!indexed_attributes.empty()) {
        if (indexed_attributes.size() != indexes_.size())
            throw std::runtime_error("Deployment attribute/index count mismatch");
        std::vector<DynamicSegmentGraph *> deployed(base_data_->attr_count, nullptr);
        std::vector<std::vector<unsigned>> mappings(base_data_->attr_count);
        std::unordered_set<unsigned> seen;
        for (std::size_t slot = 0; slot < indexes_.size(); ++slot) {
            const unsigned attr = indexed_attributes[slot];
            if (attr >= base_data_->attr_count || !seen.insert(attr).second || !indexes_[slot])
                throw std::runtime_error("Invalid deployed attribute");
            deployed[attr] = indexes_[slot];
            mappings[attr] = std::move(rank_to_base_local_[slot]);
        }
        indexes_ = std::move(deployed);
        rank_to_base_local_ = std::move(mappings);
    } else if (indexes_.empty()) {
        indexes_.resize(base_data_->attr_count, nullptr);
        rank_to_base_local_.resize(base_data_->attr_count);
    } else if (indexes_.size() != base_data_->attr_count) {
        throw std::runtime_error("Partial deployment requires explicit attribute IDs");
    }
    for (unsigned attr = 0; attr < indexes_.size(); ++attr)
        if (indexes_[attr] && rank_to_base_local_[attr].size() != static_cast<std::size_t>(base_data_->data_size))
            throw std::runtime_error("Deployed rank mapping size mismatch");

    if (rebuild_fraction_ <= 0.0) {
        throw std::runtime_error(
            "rebuild_fraction must be positive");
    }

    allocator_history_known_ = base_local_to_original_.empty() ||
                               next_original_id != 0;
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

    original_to_base_local_.reserve(base_local_to_original_.size());
    for (unsigned local_id = 0;
         local_id < base_local_to_original_.size(); ++local_id) {
        const unsigned stable_id = base_local_to_original_[local_id];
        if (!original_to_base_local_.emplace(stable_id, local_id).second) {
            throw std::runtime_error("Duplicate Base stable ID");
        }
        next_original_id_ = std::max(
            next_original_id_, static_cast<std::uint64_t>(stable_id) + 1);
    }
    if (next_original_id != 0 && next_original_id < next_original_id_) {
        throw std::runtime_error("Snapshot ID high-water mark precedes Base IDs");
    }
    const std::uint64_t exhausted =
        static_cast<std::uint64_t>(std::numeric_limits<unsigned>::max()) + 1;
    if (next_original_id > exhausted) {
        throw std::runtime_error("Snapshot ID high-water mark is out of range");
    }
    next_original_id_ = std::max(next_original_id_, next_original_id);
}

unsigned DynamicDanaIndex::insert(
    const float *vector,
    const std::vector<float> &attrs) {

    if (!allocator_history_known_) {
        throw std::runtime_error(
            "Automatic insertion requires the snapshot ID high-water mark");
    }
    if (next_original_id_ > std::numeric_limits<unsigned>::max()) {
        throw std::runtime_error("Stable ID space is exhausted");
    }
    const unsigned original_id = static_cast<unsigned>(next_original_id_);

    insertWithId(original_id, vector, attrs);
    return original_id;
}

void DynamicDanaIndex::insertWithId(
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

    DeltaPoint point;
    point.original_id = original_id;
    point.vector.assign(
        vector,
        vector + base_data_->data_dim);
    point.attrs = attrs;
    prepareMutation();
    if (next_version_ == std::numeric_limits<std::uint64_t>::max())
        throw std::runtime_error("Version space is exhausted");
    point.version = next_version_;
    Mutation operation;
    if (active_capture_token_) {
        operation.sequence = committed_sequence_ + 1;
        operation.original_id = original_id;
        operation.vector = point.vector;
        operation.attrs = point.attrs;
        operation.version = point.version;
    }
    if (original_to_base_local_.find(original_id) != original_to_base_local_.end())
        base_tombstones_.insert(original_id);

    delta_[original_id] = std::move(point);

    next_original_id_ =
        std::max(next_original_id_,
                 static_cast<std::uint64_t>(original_id) + 1);
    ++next_version_;
    ++committed_sequence_;
    if (active_capture_token_) journal_.push_back(std::move(operation));
}

void DynamicDanaIndex::update(
    unsigned original_id,
    const float *vector,
    const std::vector<float> &attrs) {

    const bool live_base =
        original_to_base_local_.find(original_id) != original_to_base_local_.end() &&
        base_tombstones_.find(original_id) == base_tombstones_.end();
    if (!live_base && delta_.find(original_id) == delta_.end()) {
        throw std::runtime_error(
            "Cannot update an unknown ID");
    }

    insertWithId(original_id, vector, attrs);
}

void DynamicDanaIndex::updateAttributes(
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

    const auto base_it = original_to_base_local_.find(original_id);
    if (base_it == original_to_base_local_.end() ||
        base_tombstones_.find(original_id) != base_tombstones_.end()) {
        throw std::runtime_error(
            "Cannot update attributes of an unknown ID");
    }

    insertWithId(
        original_id,
        base_data_->nodes[base_it->second],
        attrs);
}

void DynamicDanaIndex::erase(unsigned original_id) {
    prepareMutation();
    Mutation operation;
    operation.sequence = committed_sequence_ + 1;
    operation.original_id = original_id;
    operation.erased = true;
    if (original_to_base_local_.find(original_id) != original_to_base_local_.end())
        base_tombstones_.insert(original_id);
    delta_.erase(original_id);
    ++committed_sequence_;
    if (active_capture_token_) journal_.push_back(std::move(operation));
}

void DynamicDanaIndex::updateFields(
    unsigned original_id, const float *vector,
    const std::vector<std::pair<unsigned, float>> &attributes) {
    std::vector<float> values;
    const float *previous = nullptr;
    const auto delta = delta_.find(original_id);
    if (delta != delta_.end()) {
        values = delta->second.attrs;
        previous = delta->second.vector.data();
    } else {
        const auto base = original_to_base_local_.find(original_id);
        if (base == original_to_base_local_.end() || base_tombstones_.count(original_id))
            throw std::runtime_error("Cannot update fields of an unknown ID");
        previous = base_data_->nodes[base->second];
        for (unsigned attr = 0; attr < base_data_->attr_count; ++attr)
            values.push_back(base_data_->attrs[attr][base->second]);
    }
    std::unordered_set<unsigned> seen;
    for (const auto &entry : attributes) {
        if (entry.first >= values.size() || !seen.insert(entry.first).second)
            throw std::runtime_error("Invalid or duplicate updated attribute");
        values[entry.first] = entry.second;
    }
    update(original_id, vector ? vector : previous, values);
}

void DynamicDanaIndex::prepareMutation() {
    if (committed_sequence_ == std::numeric_limits<std::uint64_t>::max())
        throw std::runtime_error("Operation sequence is exhausted");
    if (active_capture_token_ && journal_.size() == journal_.capacity())
        journal_.reserve(std::max<std::size_t>(16, journal_.capacity() * 2));
}

DynamicDanaIndex::RebuildCapture DynamicDanaIndex::captureForRebuild() {
    if (active_capture_token_ || !allocator_history_known_)
        throw std::runtime_error("Capture requires known allocator history and no active capture");
    if (capture_generation_ == std::numeric_limits<std::uint64_t>::max())
        throw std::runtime_error("Capture token space is exhausted");
    RebuildCapture capture;
    capture.points = createSnapshot();
    capture.sequence = committed_sequence_;
    capture.next_original_id = next_original_id_;
    capture.next_version = next_version_;
    capture.token = ++capture_generation_;
    journal_.clear();
    capture_sequence_ = committed_sequence_;
    active_capture_token_ = capture.token;
    return capture;
}

void DynamicDanaIndex::requireActiveCapture(const RebuildCapture &capture) const {
    if (!active_capture_token_ || capture.token != active_capture_token_ ||
        capture.sequence != capture_sequence_)
        throw std::runtime_error("Unknown or finished capture");
}

DynamicDanaIndex::RebuildJournal DynamicDanaIndex::journalSince(
    const RebuildCapture &capture) const {
    requireActiveCapture(capture);
    RebuildJournal result;
    result.operations = journal_;
    result.token = active_capture_token_;
    result.end_sequence = committed_sequence_;
    result.next_original_id = next_original_id_;
    result.next_version = next_version_;
    return result;
}

void DynamicDanaIndex::finishCapture(const RebuildCapture &capture,
                                    const RebuildJournal &acknowledged) {
    requireActiveCapture(capture);
    if (acknowledged.token != active_capture_token_ ||
        acknowledged.end_sequence != committed_sequence_ ||
        acknowledged.operations.size() != journal_.size() ||
        acknowledged.next_original_id != next_original_id_ ||
        acknowledged.next_version != next_version_)
        throw std::runtime_error("Capture has unacknowledged operations");
    active_capture_token_ = 0;
    std::vector<Mutation>().swap(journal_);
}

void DynamicDanaIndex::replayAfterCapture(const RebuildCapture &capture,
                                        const RebuildJournal &journal) {
    if (active_capture_token_ || replay_installed_ || committed_sequence_ ||
        !delta_.empty() || !base_tombstones_.empty() ||
        !allocator_history_known_ || !capture.token || journal.token != capture.token)
        throw std::runtime_error("Replay requires a fresh matching snapshot Base");
    const auto base = createSnapshot();
    if (base.size() != capture.points.size() || next_original_id_ != capture.next_original_id)
        throw std::runtime_error("Captured Base or allocator mismatch");
    for (std::size_t i = 0; i < base.size(); ++i)
        if (base[i].original_id != capture.points[i].original_id ||
            base[i].vector != capture.points[i].vector || base[i].attrs != capture.points[i].attrs)
            throw std::runtime_error("Captured Base content mismatch");
    if (!capture.next_version || journal.end_sequence < capture.sequence ||
        journal.end_sequence - capture.sequence != journal.operations.size())
        throw std::runtime_error("Incomplete journal");
    // Check the complete ordered batch before mutating the replacement instance.
    auto sequence = capture.sequence;
    auto version = capture.next_version;
    auto watermark = capture.next_original_id;
    for (const auto &operation : journal.operations) {
        if (sequence == std::numeric_limits<std::uint64_t>::max() ||
            operation.sequence != ++sequence)
            throw std::runtime_error("Noncontiguous journal sequence");
        if (operation.erased) {
            if (!operation.vector.empty() || !operation.attrs.empty() || operation.version)
                throw std::runtime_error("Invalid erase record");
        } else {
            if (operation.vector.size() != static_cast<std::size_t>(base_data_->data_dim) ||
                operation.attrs.size() != base_data_->attr_count ||
                version == std::numeric_limits<std::uint64_t>::max() ||
                operation.version != version++)
                throw std::runtime_error("Invalid upsert record");
            watermark = std::max(watermark, static_cast<std::uint64_t>(operation.original_id) + 1);
        }
    }
    if (watermark != journal.next_original_id || version != journal.next_version)
        throw std::runtime_error("Journal allocator/version mismatch");
    committed_sequence_ = capture.sequence;
    next_version_ = capture.next_version;
    for (const auto &operation : journal.operations) {
        if (operation.erased) erase(operation.original_id);
        else insertWithId(operation.original_id, operation.vector.data(), operation.attrs);
    }
    replay_installed_ = true;
}

unsigned DynamicDanaIndex::stableIdOfBaseLocal(
    unsigned base_local_id) const {

    if (base_local_id >=
        base_local_to_original_.size()) {
        throw std::runtime_error(
            "Base local ID is out of range");
    }

    return base_local_to_original_[base_local_id];
}

bool DynamicDanaIndex::deltaPassesFilter(
    const DeltaPoint &point,
    const MultiRangeQuery &filter) const {

    if (point.attrs.size() != filter.bounds.size()) {
        return false;
    }

    for (std::size_t attr = 0;
         attr < point.attrs.size();
         ++attr) {
        if (!filter.constrains(static_cast<unsigned>(attr))) continue;
        const float value = point.attrs[attr];

        if (value < filter.bounds[attr].low ||
            value > filter.bounds[attr].high) {
            return false;
        }
    }

    return true;
}

float DynamicDanaIndex::squaredL2(
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

unsigned DynamicDanaIndex::chooseNavigationAttribute(
    const MultiRangeQuery &filter) const {

    unsigned best_attr = std::numeric_limits<unsigned>::max();
    std::size_t best_span =
        std::numeric_limits<std::size_t>::max();

    for (unsigned attr = 0;
         attr < indexes_.size();
         ++attr) {
        if (!indexes_[attr] || !filter.constrains(attr)) continue;
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

std::vector<unsigned> DynamicDanaIndex::search(
    const float *query,
    const MultiRangeQuery &filter,
    unsigned top_k,
    unsigned search_ef) {

    last_result_audit_.clear();

    if (query == nullptr || top_k == 0) {
        return {};
    }

    filter.validate(base_data_->attr_count);

    last_stats_ = SearchStats{};
    last_stats_.tombstones =
        base_tombstones_.size();

    const auto base_start =
        std::chrono::steady_clock::now();

    const unsigned navigation_attr =
        chooseNavigationAttribute(filter);

    last_stats_.navigation_attr =
        navigation_attr;

    const bool fallback = navigation_attr == std::numeric_limits<unsigned>::max();
    last_stats_.exact_fallback = fallback;
    const auto rank_bound = fallback ? std::make_pair(1U, 0U) :
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
    const auto better = [](const Candidate &left, const Candidate &right) {
        return left.distance < right.distance ||
               (left.distance == right.distance && left.original_id < right.original_id);
    };
    std::priority_queue<Candidate, std::vector<Candidate>, decltype(better)> best_base(better);
    if (fallback) {
        for (unsigned local = 0; local < base_local_to_original_.size(); ++local) {
            const unsigned id = stableIdOfBaseLocal(local);
            if (base_tombstones_.count(id) || !base_data_->passFilter(local, filter)) continue;
            best_base.push({squaredL2(query, base_data_->nodes[local]), id, 0, false});
            ++last_stats_.base_rerank_distance_evaluations;
            if (best_base.size() > top_k) best_base.pop();
        }
        last_stats_.base_candidates = best_base.size();
        while (!best_base.empty()) { merged.push_back(best_base.top()); best_base.pop(); }
    }

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

            index->rangeSearchDana(
                query,
                {static_cast<int>(rank_bound.first),
                 static_cast<int>(rank_bound.second)},
                filter,
                base_data_,
                rank_to_base_local_.at(navigation_attr));
            last_stats_.graph_distance_evaluations +=
                index->last_distance_eval_count();

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
                ++last_stats_.base_rerank_distance_evaluations;
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
    std::priority_queue<Candidate, std::vector<Candidate>, decltype(better)> best_delta(better);

    for (const auto &entry : delta_) {
        const DeltaPoint &point = entry.second;

        if (!deltaPassesFilter(point, filter)) {
            continue;
        }

        best_delta.push({
            squaredL2(query, point.vector.data()),
            point.original_id,
            point.version,
            true});
        ++last_stats_.delta_distance_evaluations;
        if (best_delta.size() > top_k) best_delta.pop();
    }
    last_stats_.delta_candidates_retained = best_delta.size();
    while (!best_delta.empty()) { merged.push_back(best_delta.top()); best_delta.pop(); }
    last_stats_.merge_candidates = merged.size();

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

bool DynamicDanaIndex::needsRebuild() const {
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


std::vector<unsigned> DynamicDanaIndex::searchExact(
    const float *query,
    const MultiRangeQuery &filter,
    unsigned top_k) const {
    filter.validate(base_data_->attr_count);

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



std::vector<DynamicDanaIndex::SnapshotPoint>
DynamicDanaIndex::createSnapshot() const {

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
