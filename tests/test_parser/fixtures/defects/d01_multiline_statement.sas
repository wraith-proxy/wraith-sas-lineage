data work.orders_combined;
    set work.orders_a( keep = order_id qty )
        work.orders_b(keep=order_id qty price)
        work.orders_c
        ;
    total = qty * price;
run;
