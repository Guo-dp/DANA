// Reuse the deployed parser and search implementation without changing it.
#define main historical_benchmark_main
#include "query_dana_benchmark.cc"
#undef main
#include <filesystem>

int main(int argc, char** argv) {
    try {
        const auto cfg = parseArgs(argc, argv);
        if (cfg.per_query_path.empty() || std::filesystem::exists(cfg.per_query_path))
            throw std::runtime_error("A new -per_query_path JSONL output is required");
        DataWrapper data(cfg.query_num, cfg.query_k, cfg.dataset, cfg.data_size);
        auto base = cfg.dataset_path, qp = cfg.query_path;
        data.readData(base, qp);
        data.readAttributes(cfg.attr_path, cfg.attr_count);
        const auto attrs = parseIndexedAttrs(cfg.indexed_attrs_arg, cfg.attr_count);
        std::vector<std::unique_ptr<DataWrapper>> ranked;
        std::vector<std::unique_ptr<hnswlib::L2Space>> spaces;
        std::vector<std::unique_ptr<dsg::DynamicSegmentGraph>> indexes;
        std::vector<std::vector<unsigned>> maps;
        for (auto a : attrs) {
            auto d = std::make_unique<DataWrapper>(cfg.query_num, cfg.query_k, cfg.dataset, cfg.data_size);
            std::string path = cfg.reordered_data_root + "/base.attr" + std::to_string(a) + ".fbin";
            d->readData(path, qp);
            auto s = std::make_unique<hnswlib::L2Space>(d->data_dim);
            auto g = std::make_unique<dsg::DynamicSegmentGraph>(s.get(), d.get());
            g->load(cfg.index_root + "/attr" + std::to_string(a) + ".dsg");
            g->setSearchEf(cfg.search_ef);
            g->setQueryTopK(cfg.query_k);
            auto mapping = readRankMapping(cfg.reordered_data_root + "/rank_to_original.attr" + std::to_string(a) + ".ibin");
            if (mapping.size() != static_cast<size_t>(cfg.data_size))
                throw std::runtime_error("Mapping size mismatch");
            for (size_t r = 0; r < mapping.size(); ++r) {
                if (mapping[r] != data.rankToOriginal(a, r))
                    throw std::runtime_error("Mapping/attribute order mismatch");
                for (size_t j = 0; j < static_cast<size_t>(data.data_dim); ++j)
                    if (d->nodes[r][j] != data.nodes[mapping[r]][j])
                        throw std::runtime_error("Reordered vector mismatch");
            }
            maps.push_back(std::move(mapping)); ranked.push_back(std::move(d));
            spaces.push_back(std::move(s)); indexes.push_back(std::move(g));
        }
        auto cases = readFilters(cfg.filter_path, cfg.attr_count);
        auto search = [&](const FilterCase& t, double& hops, double& dist) {
            size_t slot = 0;
            if (cfg.nav_mode == "fixed") {
                auto it = std::find(attrs.begin(), attrs.end(), cfg.fixed_attr);
                if (it == attrs.end()) throw std::runtime_error("Unindexed fixed attr");
                slot = it - attrs.begin();
            } else {
                auto best = rankRangeWidth(data, t.filter, attrs[0]);
                for (size_t s = 1; s < attrs.size(); ++s) {
                    auto width = rankRangeWidth(data, t.filter, attrs[s]);
                    if (width < best) { best = width; slot = s; }
                }
            }
            auto bound = data.valueRangeToRankRange(attrs[slot], t.filter.bounds[attrs[slot]].low, t.filter.bounds[attrs[slot]].high);
            hops = dist = 0;
            if (bound.first > bound.second) return std::vector<unsigned>{};
            auto& g = *indexes[slot];
            g.rangeSearchDana(data.querys.at(t.query_idx),
                {static_cast<int>(bound.first), static_cast<int>(bound.second)},
                t.filter, &data, maps[slot]);
            hops = g.last_hop_count(); dist = g.last_distance_eval_count();
            return g.returned_nns;
        };
        for (const auto& t : cases)
            if (t.query_idx >= data.querys.size()) throw std::runtime_error("Query ID out of bounds");
        for (size_t i = 0; i < std::min<size_t>(10, cases.size()); ++i) {
            double h, d; search(cases[i], h, d);
        }
        std::ofstream out(cfg.per_query_path);
        if (!out) throw std::runtime_error("Cannot open output");
        out << std::setprecision(17);
        for (size_t i = 0; i < cases.size(); ++i) {
            double hops, dist;
            auto start = std::chrono::steady_clock::now();
            auto ids = search(cases[i], hops, dist);
            auto ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
            out << "{\"q\":" << i << ",\"ms\":" << ms << ",\"dist\":" << dist << ",\"hops\":" << hops << ",\"ids\":[";
            for (size_t j = 0; j < ids.size(); ++j) { if (j) out << ','; out << ids[j]; }
            out << "],\"distances\":[";
            for (size_t j = 0; j < ids.size(); ++j) {
                if (ids[j] >= static_cast<unsigned>(cfg.data_size)) throw std::runtime_error("Invalid returned ID");
                double distance = 0;
                for (size_t z = 0; z < static_cast<size_t>(data.data_dim); ++z) {
                    double v = static_cast<double>(data.nodes[ids[j]][z]) - data.querys[cases[i].query_idx][z];
                    distance += v*v;
                }
                if (j) out << ','; out << distance;
            }
            out << "]}\n";
        }
        if (!out) throw std::runtime_error("Output write failed");
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
