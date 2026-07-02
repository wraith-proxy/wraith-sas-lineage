proc sort data=work.orders out=work.orders_by_age; by cust_age; proc freq data=work.orders_by_age;
    tables cust_age * region /;
run;
