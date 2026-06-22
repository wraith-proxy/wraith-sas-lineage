/* RISK_ODS_LOAD_DAILY — sample fixture for parser tests */

libname RISKODS BASE '/data/ods/risk';
libname RAWDATA BASE '/data/raw';

%let run_dt = 20260620;

proc sql noprint;
    create table RISKODS.ALL_EMP as
        select a.ACCOUNT_NO,
               a.BAL,
               CASE WHEN a.BAL < 0 THEN 0 ELSE a.BAL END AS EXPOSURE_AMT,
               b.CUST_NAME
        from RAWDATA.ACCOUNTS as a
        left join RAWDATA.CUSTOMERS as b
            on a.CUST_ID = b.CUST_ID
        where a.ACTIVE_FLG = 1;
quit;

data RISKODS.ALL_EMP_CLEAN;
    set RISKODS.ALL_EMP;
    if EXPOSURE_AMT = . then EXPOSURE_AMT = 0;
run;

rsubmit PROD_SERVER;
    libname REMOTE_LIB slibref=RISKODS server=PROD_SERVER;
    proc sort data=REMOTE_LIB.ALL_EMP_CLEAN out=REMOTE_LIB.ALL_EMP_SORTED;
        by ACCOUNT_NO;
    run;
endrsubmit;
