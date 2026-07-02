proc sql;
    create table work.order_totals as
    select a.order_id, a.qty
    from /* data work.ghost; run; commented-out step */ work.orders as a
    left join work.customers as b
        on a.cust_id = b.cust_id;
quit;
/* proc sort data=work.ghost; by x; run; */
* data work.also_ghost; ;
