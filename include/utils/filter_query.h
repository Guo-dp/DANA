#pragma once

#include <cstddef>
#include <vector>

struct RangeBound {
    float low = 0.0F;
    float high = 0.0F;
};

struct MultiRangeQuery {
    std::vector<RangeBound> bounds;
    unsigned primary_attr = 0;
};
