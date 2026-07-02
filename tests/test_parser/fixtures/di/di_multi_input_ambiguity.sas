/*============================================================================*
 * Step:         Join ORDERS and CUSTOMERS                                    *
 * Transform:    SQL Join                                                     *
 * Source Table: ODSLIB.ORDERS - Order detail      (A5CGXK2Q.BE0004YB)        *
 * Source Table: ODSLIB.CUSTOMERS - Customer dim   (A5CGXK2Q.BE0005YC)        *
 * Target Table: work.W91FGHIJ - Join output       (A5CGXK2Q.BE0006YD)        *
 *============================================================================*/
%let transformID = %quote(A5CGXK2Q.BE0006YD);
%let etls_stepStartTime = %sysfunc(datetime(), datetime20.);

/* Both inputs carry a STATUS column. DI emits the input reference and the
   expression unqualified: no _input_table variable exists. */
%let _OUTPUT1 = work.W91FGHIJ;
%let _OUTPUT1_col0_name = ORDER_ID;
%let _OUTPUT1_col0_input = ORDER_ID;
%let _OUTPUT1_col0_input_count = 1;
%let _OUTPUT1_col0_exp = ORDER_ID;
%let _OUTPUT1_col1_name = STATUS;
%let _OUTPUT1_col1_input = STATUS;
%let _OUTPUT1_col1_input_count = 1;
%let _OUTPUT1_col1_exp = STATUS;
%let _OUTPUT1_col_count = 2;

/* The generated SQL is the only place the reference is qualified. */
proc sql;
    create table work.W91FGHIJ as
    select o.ORDER_ID,
           o.STATUS
    from ODSLIB.ORDERS as o
    inner join ODSLIB.CUSTOMERS as c
        on o.CUST_ID = c.CUST_ID;
quit;

%let SYSLAST = work.W91FGHIJ;
%rcSet(&sqlrc);
