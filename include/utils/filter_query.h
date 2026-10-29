#pragma once

#include <cstddef>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <string>

struct RangeBound {
    float low = 0.0F;
    float high = 0.0F;
};

struct MultiRangeQuery {
    std::vector<RangeBound> bounds;
    unsigned primary_attr = 0;
    // Empty preserves the legacy all-attributes query representation.
    std::vector<bool> active_attributes;
    bool constrains(unsigned attr) const {
        return active_attributes.empty() || active_attributes.at(attr);
    }
    void validate(unsigned count) const {
        if (bounds.size() != count ||
            (!active_attributes.empty() && active_attributes.size() != count))
            throw std::runtime_error("Query attribute count mismatch");
    }
    void selectAttributes(const std::string &selection) {
        if (selection.empty() || selection == "all") { active_attributes.clear(); return; }
        active_attributes.assign(bounds.size(), false);
        if (selection == "none") return;
        std::istringstream input(selection);
        std::string token;
        while (input >> token) {
            std::size_t used = 0;
            const auto attr = std::stoul(token, &used);
            if (used != token.size() || attr >= bounds.size() || active_attributes[attr])
                throw std::runtime_error("Invalid query attribute selection");
            active_attributes[attr] = true;
        }
    }
};
