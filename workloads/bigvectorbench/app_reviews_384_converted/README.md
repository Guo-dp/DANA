# BigVectorBench app_reviews converted dataset

- base: 277936 x 384
- query: 10000 x 384
- attrs: id,text_length,unixtime,star
- filters: text_length +/- 30, unixtime previous 30 days, star range from BigVectorBench filter_expr_func
- expected_top10: copied from /neighbors
