data work.audit_msg;
    set work.orders;
    put 'Unexpected order state.'/
'run; is not a terminator inside this string';
    msg = "data work.fake; set work.nothing;
run;";
run;

data work.after;
    set work.audit_msg;
run;
