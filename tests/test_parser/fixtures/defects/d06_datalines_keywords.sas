data work.manual_orders;
    input order_id qty;
datalines;
101 5
102 9
;
run;

data work.parser_bait;
    input note $char60.;
datalines4;
data work.bogus; set work.nothing;
proc freq data=work.bogus; tables note;
run;
;;;;
run;

data work.card_data;
    input value;
cards;
1
2
run;
