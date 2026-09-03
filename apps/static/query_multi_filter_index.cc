#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "base_hnsw/hnswlib.h"
#include "data_wrapper.h"
#include "dsg.h"
#include "filter_query.h"

struct Config {
    std::string dataset = "multiattr_smoke";
    int data_size = 32;
    int query_num = 4;
    int query_k = 3;
    unsigned search_ef = 32;
    unsigned attr_count = 3;
    std::string dataset_path;
    std::string query_path;
    std::string index_path;
    std::string attr_path;
    std::string filter_path;
};

struct FilterCase {
    unsigned query_idx = 0;
    MultiRangeQuery filter;
    std::vector<unsigned> expected;
};

static std::vector<std::string> splitComma(const std::string &line) {
    std::vector<std::string> out;
    std::stringstream ss(line);
    std::string item;
    while (std::getline(ss, item, ',')) {
        out.push_back(item);
    }
    return out;
}

static std::vector<unsigned> parseExpected(const std::string &s) {
    std::vector<unsigned> out;
    std::stringstream ss(s);
    unsigned x = 0;
    while (ss >> x) {
        out.push_back(x);
    }
    return out;
}

static std::vector<FilterCase> readFilters(const std::string &path, unsigned attr_count) {
    std::ifstream in(path);
    if (!in.is_open()) {
        throw std::runtime_error("Cannot open filter_path: " + path);
    }

    std::vector<FilterCase> cases;
    std::string line;
    bool first = true;
    while (std::getline(in, line)) {
        if (line.empty()) {
            continue;
        }
        if (first) {
            first = false;
            if (line.find("query_idx") != std::string::npos) {
                continue;
            }
        }

        auto cols = splitComma(line);
        const size_t need = 2 + static_cast<size_t>(attr_count) * 2 + 1;
        if (cols.size() < need) {
            throw std::runtime_error("Bad filter row: " + line);
        }

        FilterCase fc;
        fc.query_idx = static_cast<unsigned>(std::stoul(cols[0]));
        fc.filter.primary_attr = static_cast<unsigned>(std::stoul(cols[1]));
        fc.filter.bounds.resize(attr_count);

        size_t pos = 2;
        for (unsigned a = 0; a < attr_count; ++a) {
            fc.filter.bounds[a].low = std::stof(cols[pos++]);
            fc.filter.bounds[a].high = std::stof(cols[pos++]);
        }
        fc.expected = parseExpected(cols[pos]);
        cases.push_back(fc);
    }
    return cases;
}

static void printList(const std::vector<unsigned> &xs, std::size_t limit) {
    for (std::size_t i = 0; i < xs.size() && i < limit; ++i) {
        std::cout << " " << xs[i];
    }
}

static Config parseArgs(int argc, char **argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto val = [&](const char *flag) -> const char * {
            if (i + 1 >= argc) {
                throw std::runtime_error(std::string("Missing value for ") + flag);
            }
            return argv[++i];
        };

        if (arg == "-dataset") cfg.dataset = val("-dataset");
        else if (arg == "-N") cfg.data_size = std::stoi(val("-N"));
        else if (arg == "-dataset_path") cfg.dataset_path = val("-dataset_path");
        else if (arg == "-query_path") cfg.query_path = val("-query_path");
        else if (arg == "-index_path") cfg.index_path = val("-index_path");
        else if (arg == "-attr_path") cfg.attr_path = val("-attr_path");
        else if (arg == "-attr_count") cfg.attr_count = static_cast<unsigned>(std::stoul(val("-attr_count")));
        else if (arg == "-filter_path") cfg.filter_path = val("-filter_path");
        else if (arg == "-query_num") cfg.query_num = std::stoi(val("-query_num"));
        else if (arg == "-query_k") cfg.query_k = std::stoi(val("-query_k"));
        else if (arg == "-search_ef") cfg.search_ef = static_cast<unsigned>(std::stoul(val("-search_ef")));
    }

    if (cfg.dataset_path.empty() || cfg.query_path.empty() || cfg.index_path.empty() ||
        cfg.attr_path.empty() || cfg.filter_path.empty()) {
        throw std::runtime_error("Missing required paths.");
    }
    return cfg;
}

int main(int argc, char **argv) {
    try {
        Config cfg = parseArgs(argc, argv);

        DataWrapper data_wrapper(cfg.query_num, cfg.query_k, cfg.dataset, cfg.data_size);
        data_wrapper.readData(cfg.dataset_path, cfg.query_path);
        data_wrapper.readAttributes(cfg.attr_path, cfg.attr_count);
        data_wrapper.setPrimaryAttribute(0);

        hnswlib::L2Space space(data_wrapper.data_dim);
        dsg::DynamicSegmentGraph index(&space, &data_wrapper);
        index.setQueryTopK(static_cast<unsigned>(cfg.query_k));
        index.setSearchEf(cfg.search_ef);
        index.load(cfg.index_path);

        auto cases = readFilters(cfg.filter_path, cfg.attr_count);

        for (const auto &fc : cases) {
            if (fc.query_idx >= data_wrapper.querys.size()) {
                continue;
            }

            index.setQueryTopK(static_cast<unsigned>(cfg.query_k));
            index.rangeSearchMultiExact(data_wrapper.querys.at(fc.query_idx), fc.filter);
            const auto exact = index.returned_nns;

            index.setQueryTopK(static_cast<unsigned>(cfg.query_k));
            index.setSearchEf(cfg.search_ef);
            index.rangeSearch(data_wrapper.querys.at(fc.query_idx), fc.filter);
            const auto graph = index.returned_nns;

            std::cout << "q" << fc.query_idx << " expected:";
            printList(fc.expected, cfg.query_k);
            std::cout << " exact:";
            printList(exact, cfg.query_k);
            std::cout << " graph:";
            printList(graph, cfg.query_k);
            std::cout << " hops=" << index.last_hop_count()
                      << " dist=" << index.last_distance_eval_count()
                      << "\n";
        }
    } catch (const std::exception &ex) {
        std::cerr << "query_multi_filter_index failed: " << ex.what() << "\n";
        return 1;
    }

    return 0;
}
