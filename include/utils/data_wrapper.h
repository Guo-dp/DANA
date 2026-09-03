/**
 * @file data_vecs.h
 * @brief Manage raw data vectors and query metadata.
 *
 * This class encapsulates dataset metadata, nodes, queries, precomputed ranges,
 * and groundtruth vectors for benchmarking range filters. We assume the dataset
 * vectors are pre-sorted and each vector receives a deterministic attribute id
 * equal to its index in [0, data_size - 1].
 *
 */



#pragma once

#include <array>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

#include "flat_vectors.h"

#include "filter_query.h"

// 使用标准库中的pair、string和vector类型
using std::pair;
using std::string;
using std::vector;

class DataWrapper {
public:
    static constexpr size_t kStaticRangeCount = 7;
    inline static constexpr std::array<double, kStaticRangeCount> kRangeRatios{
        0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64};
    static constexpr int kStaticTopK = 10;
    static constexpr int kStaticQueryNum = 1000;

    /**
     * Constructor initializes dataset name, size, query count, and top-k target.
     */
    DataWrapper(int num, int k_, string dataset_name, int data_size_)
        : dataset(dataset_name),   // Dataset name (constant).
          data_size(data_size_),   // Dataset size (constant).
          query_num(num),          // Query count (constant).
          query_k(k_),             // Target top-k (constant).
          rank_to_label_by_attr(rank_to_original) {
        labels.resize(static_cast<size_t>(data_size));
        std::iota(labels.begin(), labels.end(), 0U);
    }

    // Dataset name (constant).
    const string dataset;
    
    // Total number of vectors (constant).
    const int data_size;
    
    // Number of queries (constant).
    const int query_num;
    
    // Target top-k (constant).
    const int query_k;
    
    // Dimensionality of the dataset vectors.
    size_t data_dim;
    
    // Deterministic labels/attributes for each vector (0..data_size-1). Files are
    // assumed pre-sorted, so label i always maps to nodes[i] without extra I/O.
    vector<unsigned> labels;

    // attrs[attr][original_id]
    std::vector<std::vector<float>> attrs;

    // attr_rank[attr][original_id] -> rank
    std::vector<std::vector<unsigned>> attr_rank;

    // rank_to_original[attr][rank] -> original_id
    std::vector<std::vector<unsigned>> rank_to_original;

    unsigned attr_count = 0;

    // Legacy alias for dsg.cc (same storage as rank_to_original).
    std::vector<std::vector<unsigned>> &rank_to_label_by_attr;

    // Legacy primary navigation attribute for dsg.cc.
    unsigned primary_attr_id = 0;

    // Stored dataset vectors.
    FlatVectors<float> nodes;

    // Raw query vectors.
    FlatVectors<float> querys;
    
    // Range bounds for static queries.
    std::array<vector<pair<int, int>>, kStaticRangeCount> static_query_ranges;
    
    // Groundtruth per static range bucket.
    std::array<FlatVectors<int>, kStaticRangeCount> static_groundtruth;


    /**
     * Load dataset and query files from disk.
     */
    void readData(string &dataset_path, string &query_path);

    /**
     * Load groundtruth from persistent storage.
     */
    void LoadGroundtruth(const string &gt_root);

    void readAttributes(const std::string &path, unsigned count);

    void setPrimaryAttribute(unsigned attr_id) {
        if (attr_id >= attr_count) {
            throw std::runtime_error("primary_attr out of range.");
        }
        primary_attr_id = attr_id;
    }

    bool hasAttributes() const { return attr_count > 0; }

    bool passFilter(unsigned original_id,
                    const MultiRangeQuery &query) const;

    std::pair<unsigned, unsigned>
    valueRangeToRankRange(unsigned attr,
                          float low,
                          float high) const;

    unsigned chooseNavigationAttribute(
        const MultiRangeQuery &query) const;

    unsigned originalToRank(unsigned attr,
                            unsigned original_id) const {
        return attr_rank.at(attr).at(original_id);
    }

    unsigned rankToOriginal(unsigned attr,
                            unsigned rank) const {
        return rank_to_original.at(attr).at(rank);
    }

    unsigned rankOf(unsigned attr_id, unsigned label) const {
        return originalToRank(attr_id, label);
    }

    /**
     * Generate range-filtering queries and matching groundtruth (benchmark edition).
     */
    void generateRangeFilteringQueriesAndGroundtruthBenchmark(const string &save_root = "./groundtruth/static");

    void generateIncrementalInsertionGroundtruth(int num_parts, const string &save_dir);

    size_t range_count() const { return kStaticRangeCount; }
    const FlatVectors<int> &groundtruth_by_range(size_t range_id) const {
        return static_groundtruth.at(range_id);
    }
    const vector<pair<int, int>> &query_bounds_by_range(size_t range_id) const {
        return static_query_ranges.at(range_id);
    }


};
