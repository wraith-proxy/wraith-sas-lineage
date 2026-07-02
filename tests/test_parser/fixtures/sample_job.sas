/* SALES_ODS_LOAD_DAILY — sample fixture for parser tests */

libname SALESODS BASE '/data/ods/sales';
libname RAWDATA BASE '/data/raw';

%let run_dt = 20260620;

proc sql noprint;
    create table SALESODS.ALL_EMP as
        select a.ACCOUNT_NO,
               a.QTY,
               CASE WHEN a.QTY < 0 THEN 0 ELSE a.QTY END AS ORDER_AMT,
               b.CUST_NAME
        from RAWDATA.ACCOUNTS as a
        left join RAWDATA.CUSTOMERS as b
            on a.CUST_ID = b.CUST_ID
        where a.ACTIVE_FLG = 1;
quit;

data SALESODS.ALL_EMP_CLEAN;
    set SALESODS.ALL_EMP;
    if ORDER_AMT = . then ORDER_AMT = 0;
run;

rsubmit PROD_SERVER;
    libname REMOTE_LIB slibref=SALESODS server=PROD_SERVER;
    proc sort data=REMOTE_LIB.ALL_EMP_CLEAN out=REMOTE_LIB.ALL_EMP_SORTED;
        by ACCOUNT_NO;
    run;
endrsubmit;
