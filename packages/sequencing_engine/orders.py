import datetime as dt
class bunchingCriteria:
    instances = {}
    def __init__(self,sku_name, moq_ll, moq_ul, cycle_time, early_readiness_days):
        self.sku_name = sku_name
        self.moq_ll = moq_ll
        self.moq_ul = moq_ul
        
        self.cycle_time= cycle_time
        self.early_readiness_days = early_readiness_days
        self.__class__.instances[sku_name] = self

class Order:
    def __init__(self, so_no,order_sku, order_qty, order_billet_nos, order_rd, order_dd, mts_bool, early_readiness_days,order_machine):

        if isinstance(order_sku, bunchingCriteria) == True:
            self.order_sku = order_sku
        else:
            raise Exception('Sku doesnt exist')
        try:
            if order_rd == None or dt.datetime.strptime(order_rd,'%d/%m/%Y %H:%M:%S'):
                self.order_rd = order_rd
        except:
            pass

        try:
            if order_rd == None or dt.datetime.strptime(order_rd,'%Y-%m-%d %H:%M:%S'):
                self.order_rd = order_rd
        except:
            pass

        try:
            if order_dd == None or dt.datetime.strptime(order_dd,'%d/%m/%Y %H:%M:%S'):
                self.order_dd = order_dd
        except:
            pass

        try:
            if order_dd == None or dt.datetime.strptime(order_dd,'%Y-%m-%d %H:%M:%S'):
                self.order_dd = order_dd
        except:
            pass
        
        self.order_qty = order_qty
        self.order_billet_nos = order_billet_nos
        self.mts_bool = mts_bool
        self.early_readiness_days = early_readiness_days
        self.so_no = so_no
        self.order_machine = order_machine
        if order_dd != None:
            self.early_readiness_date = dt.datetime.strptime(self.order_rd,'%Y-%m-%d %H:%M:%S') - dt.timedelta(days=self.early_readiness_days)
        else:
            pass