data work.order_report;
    merge work.orders_current(in=cur) work.orders_prior(in=pri);
    by order_id;
    if cur = 1;
    source_flag = cur;
run;

data work.stock_master;
    modify work.stock_master work.stock_updates;
    by part_no;
    if _iorc_ = 0 then replace;
    else output;
run;

data work.orders_all;
    set work.orders_q1 work.orders_q2 work.orders_q3 indsname=src_ds;
    quarter = scan(src_ds, 2, '._');
run;
