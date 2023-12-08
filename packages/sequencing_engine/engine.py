import json
import time
import os
import datetime
import pandas as pd
from packages.sequencing_engine.order_management_objects import Order, bunchingCriteria
from packages.sequencing_engine.operations import generateOutput, calcSeqScore, calcBunchExecTime, findBunchIdx,\
      nextSwitchbunchingCriteria, switchMapGenerator, find_combinations, skuToBunchMap, createOrders, createBunchingCriterias,\
        calcRemSpace, calcQuantity, sortBunch,orderShifter, alter_sequence_bunches_by_grouped_criteria

class sequencingEngine:
    def __init__(self, config_path):
        self.config_path = config_path
        self.load_config()

    def load_config(self):
        # Load configuration from the config file
        with open(self.config_path, 'r') as config_file:
            self.CONFIG = json.load(config_file)

    def load_orders(self):
        #here we create orders
        createBunchingCriterias(f"{self.CONFIG.get('filepaths').get('input_file_path')}\\{os.listdir(self.CONFIG.get('filepaths').get('input_file_path'))[0]}")
        self.orders = createOrders(bunchingCriteria.instances,self.order_book, self.CONFIG)
    def run_bunching(self):
        self.all_bunches = []
        self.sku_to_bunch = {}
        default_mts_attributes = self.CONFIG['default_mts_attributes']
        while self.orders:
            self.combination_map = []
            input_value = float(self.orders[0].order_sku.moq_ll)
            bunch, lessthan_moq = find_combinations(self,self.orders, input_value, time.perf_counter())
            if bunch is not None:
                self.all_bunches.append(bunch)
                skuToBunchMap(bunch, self.all_bunches.index(bunch), self.sku_to_bunch)
                for order in bunch:
                    self.orders.remove(order)
            else:
                if self.combination_map:
                    bunch = list(max(self.combination_map, key=lambda x: max(x.keys())).values())[0]
                    
                    if lessthan_moq:
                        val = bunch[0].order_sku.moq_ll - list(max(self.combination_map, key=lambda x: max(x.keys())).keys())[0]
                    else:
                        val = bunch[0].order_sku.moq_ll - bunch[0].__getattribute__(self.CONFIG['bunching_min_cutoff_criteria']) - list(max(self.combination_map, key=lambda x: max(x.keys())).keys())[0]

                    attributes = default_mts_attributes.copy()
                    attributes[self.CONFIG['bunching_unit']] = val

                    mts_order = Order(so_no='mts',order_sku=bunch[0].order_sku, order_qty=attributes['order_qty'], order_billet_nos=attributes['order_billet_nos'], order_rd= attributes['order_rd'], mts_bool=True,order_dd=attributes['order_dd'], early_readiness_days=bunch[0].order_sku.early_readiness_days, order_machine = bunch[0].order_machine)
                    bunch.append(mts_order)
                    self.all_bunches.append(bunch)
                    skuToBunchMap(bunch, self.all_bunches.index(bunch), self.sku_to_bunch)
                    for order in bunch:
                        if order.order_rd != None:
                            self.orders.remove(order)
                else:
                    bunch = self.orders[0:1]

                    attributes = default_mts_attributes.copy()
                    attributes[self.CONFIG['bunching_unit']] = bunch[0].order_sku.moq_ll - bunch[0].__getattribute__(self.CONFIG['bunching_min_cutoff_criteria'])
                    mts_order = Order(so_no='mts',order_sku=bunch[0].order_sku,order_qty=attributes['order_qty'],order_billet_nos = attributes['order_billet_nos'],mts_bool=True, early_readiness_days=bunch[0].order_sku.early_readiness_days)
                    bunch.append(mts_order)
                    self.all_bunches.append(bunch)
                    skuToBunchMap(bunch, self.all_bunches.index(bunch), self.sku_to_bunch)
                    for order in bunch:
                        if order.order_rd != None:
                            self.orders.remove(order)
    def run_order_shifting(self):
        #This for loop counts the number of mts bunches each sku has
        self.mts_count = {}
        self.valid_mts_sku = []
        self.sku_bunch_count_map = {}
        for bunch in self.all_bunches:
            if bunch[-1].order_sku.sku_name not in self.mts_count:
                self.mts_count[bunch[-1].order_sku.sku_name] = 0
            if bunch[-1].mts_bool == True:
                self.mts_count[bunch[-1].order_sku.sku_name] += 1


        #This for loop maintains a key value pair for count of bunches each sku has
        for sku in list(bunchingCriteria.instances.keys()):
            if sku not in self.sku_bunch_count_map:
                self.sku_bunch_count_map[sku] = 0
            for bunch in self.all_bunches:
                if bunch[0].order_sku.sku_name == sku:
                    self.sku_bunch_count_map[sku] += 1


        #This for loop is used to find out the skus whose bunches can be shifted
        for sku in list(bunchingCriteria.instances.keys()):
            for b in range(len(self.all_bunches), 0, -1):
                if self.all_bunches[b-1][-1].order_sku.sku_name == sku:
                    if self.all_bunches[b-1][-1].mts_bool == True and self.sku_bunch_count_map[sku] != 1:
                        if calcRemSpace(bunchingCriteria.instances[sku],self.all_bunches[:b-1], self.CONFIG) > calcQuantity(self.all_bunches[b-1][:-1], 'bunching_max_cutoff_criteria', self.CONFIG):
                            self.valid_mts_sku.append(sku)
                    else:
                        break
        self.all_bunches = orderShifter(self.valid_mts_sku, self.all_bunches, self.CONFIG)
        self.all_bunches = [sorted(bunch, key=sortBunch) for bunch in self.all_bunches]
    def run_sequencing(self,best_seq,bunches, sku, function_call_time,TIMER, relax_days, current_time, final_seq, final_seq_bool, seq_score_map, call_ct, switch_map,CONFIG):
        if len(bunches) == 0:
            """GC code here"""
            final_seq = alter_sequence_bunches_by_grouped_criteria(final_seq, CONFIG)
            score = calcSeqScore(CONFIG['current_datetime'],final_seq, CONFIG)
            seq_score_map[score] = final_seq
            if (len(seq_score_map) > 50 and best_seq == []) or score == 0:
                best_seq = seq_score_map[max(seq_score_map)] if seq_score_map else final_seq
                final_seq_bool = True
                return best_seq
            else:
                return
        """

        This function will create a sequence of bunches based on factors like
        due date of the first order of each bunch, early allocation date of each bunch
        and switching time between different skus
        
        """

        while len(bunches) != 0:

            idx = findBunchIdx(sku, bunches)    
            if idx != None:
                bunch = bunches[idx]
            else:
                return
            early_rd = bunch[0].early_readiness_date
            bunch_dd = datetime.datetime.strptime(bunch[0].order_dd,'%Y-%m-%d %H:%M:%S')

            #check if order_dd or order_rd is affected if this bunch is added to the sequence
            if current_time + datetime.timedelta(minutes= int(calcBunchExecTime(bunch,CONFIG))) < bunch_dd + datetime.timedelta(days=relax_days) and\
                current_time + datetime.timedelta(minutes= int(calcBunchExecTime(bunch,CONFIG))) >= early_rd:

                new_current_time = current_time + datetime.timedelta(minutes= int(calcBunchExecTime(bunch,CONFIG)))
                new_sequence = final_seq + [bunch]

                next_switch_sku = nextSwitchbunchingCriteria(new_sequence[-1][0].order_sku.sku_name, switch_map)
                test = 0
                for _ in next_switch_sku:
                    sku = _[0]
                    cost = _[1]
                    # find the very first bunch with the given sku
                    idx = findBunchIdx(sku, bunches)
                    
                    if idx is not None:
                        # logic to recursively call the next bunches
                        # first place the bunch in the first position
                        new_current_time = new_current_time + datetime.timedelta(minutes=cost) 
                        if final_seq_bool == False:
                            new_call_ct = call_ct + 1
                            new_bunches = [bnch  for bnch in bunches if bnch != bunch]
                            self.run_sequencing(bunches=new_bunches,best_seq=best_seq,sku=sku,function_call_time=function_call_time,TIMER=TIMER, relax_days=relax_days, current_time=new_current_time, final_seq=new_sequence, final_seq_bool = final_seq_bool, seq_score_map=seq_score_map, call_ct=new_call_ct,switch_map=switch_map,CONFIG=CONFIG)
                        else:
                            return
                    else:
                        pass
                    if best_seq:
                        return best_seq
                    if time.perf_counter() - function_call_time > TIMER:
                        final_seq_bool = True
                        return seq_score_map[max(seq_score_map)] if seq_score_map else new_sequence
                    test += 1

                return seq_score_map[max(seq_score_map)] if seq_score_map else new_sequence
            else:
                if final_seq:
                    return final_seq
                else:
                    return []
        return

    def save_output(self,ol_no,fin_seq,current_date,CONFIG):
        # Save sequencing output to the specified file path
        # You might adjust this based on how your output is generated
        generateOutput(ol_no,fin_seq,current_date,CONFIG)