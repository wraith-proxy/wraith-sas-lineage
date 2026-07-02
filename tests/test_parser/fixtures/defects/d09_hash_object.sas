data work.orders_matched;
    set work.orders;
    if _n_ = 1 then do;
        declare hash h(dataset:"work.dim_customer");
        h.definekey('cust_id');
        h.definedata('cust_id');
        h.definedone();
    end;
    rc = h.find();
    if rc = 0;
    drop rc;
run;

data work.orders_windowed;
    set work.orders;
    if region = 'NORTH';
    set work.order_totals point=_n_;
run;
