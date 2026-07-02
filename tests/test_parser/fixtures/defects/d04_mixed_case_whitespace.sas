DATA    Work.Mixed_Case ;
    SET
        WORK.ORDERS ;
    Qty2 = QTY ;
RUN ;

pRoC sOrT dAtA=work.mixed_case OUT = work.sorted_orders;
    bY order_id;
rUn;
