data work.derived;
    set work.orders;
    a = 1;
    b = a + 2;
    if qty > 10 then band = 'HIGH';
    else band = 'LOW';
    label qty = 'Order Quantity = units';
run;
