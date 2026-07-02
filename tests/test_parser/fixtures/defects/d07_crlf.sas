data work.crlf_orders;
    set work.orders;
    qty2 = qty;
run;

proc sort data=work.crlf_orders;
    by order_id;
run;
