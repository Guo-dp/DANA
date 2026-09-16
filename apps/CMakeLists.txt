set(CMAKE_CXX_STANDARD 17)

function(add_dsg_app TARGET_NAME SOURCE_FILE)
    add_executable(${TARGET_NAME} ${SOURCE_FILE})
    target_include_directories(${TARGET_NAME} PRIVATE
        ${PROJECT_SOURCE_DIR}/include
        ${PROJECT_SOURCE_DIR}/include/utils
        ${PROJECT_SOURCE_DIR}/src
    )
    target_link_libraries(${TARGET_NAME} PRIVATE dsg_core UTIL OpenMP::OpenMP_CXX)
    dsg_apply_common_compile_options(${TARGET_NAME})
endfunction()

add_dsg_app(generate_groundtruth_static static/generate_groundtruth_static.cc)
add_dsg_app(build_static_index static/build_static_index.cc)
add_dsg_app(query_static_index static/query_static_index.cc)
add_dsg_app(query_multi_filter_benchmark static/query_multi_filter_benchmark.cc)
add_dsg_app(query_multi_dsg_benchmark static/query_multi_dsg_benchmark.cc)

# JSONL adapter used by the paper's DANA/EMA comparison. The adapter includes
# the deployed benchmark parser so its input semantics stay identical.
add_dsg_app(dana_external ${PROJECT_SOURCE_DIR}/scripts/baselines/dana_external.cpp)
target_include_directories(dana_external PRIVATE ${PROJECT_SOURCE_DIR}/apps/static)

add_dsg_app(build_dynamic_index dynamic/build_dynamic_index.cc)
add_dsg_app(insert_and_query_dynamic_index dynamic/insert_and_query_dynamic_index.cc)

if(DSG_BUILD_INDEX_DEBUG)
    add_dsg_app(build_static_index_debug static/build_static_index.cc)
    target_compile_definitions(build_static_index_debug PRIVATE DSG_DEBUG_BUILD)
    target_compile_options(build_static_index_debug PRIVATE -O0 -g)
endif()

add_dsg_app(build_hnsw_index
            static/build_hnsw_index.cc)

add_dsg_app(query_hnsw_postfilter_benchmark
            static/query_hnsw_postfilter_benchmark.cc)

add_dsg_app(query_hnsw_insearch_benchmark
            static/query_hnsw_insearch_benchmark.cc)

add_dsg_app(update_and_query_multi_dsg
            dynamic/update_and_query_multi_dsg.cc)

add_dsg_app(query_rebuilt_multi_dsg
            dynamic/query_rebuilt_multi_dsg.cc)
