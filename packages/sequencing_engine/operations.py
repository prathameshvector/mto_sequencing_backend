import datetime
import time
import os
import openpyxl
import operator
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly
import os
from packages.sequencing_engine.orders import Order, bunchingCriteria
from xlwt import Workbook
import datetime as dt
import warnings

def createBunchingCriterias(INPUT_FILE_PATH):
    min_batch_masterfile = pd.read_excel(INPUT_FILE_PATH, sheet_name='Min Batch')
    max_batch_masterfile = pd.read_excel(INPUT_FILE_PATH, sheet_name='Max Batch')
    cycle_time_masterfile = pd.read_excel(INPUT_FILE_PATH,sheet_name='Cycle Time')
    group_mapping_masterfile = pd.read_excel(INPUT_FILE_PATH,sheet_name='Group Mapping')
    for i in range(len(min_batch_masterfile)):
        unit = min_batch_masterfile.iloc[i]['key']
        obj = bunchingCriteria(unit,group_mapping_masterfile.iloc[i]['grouped_key'],min_batch_masterfile.iloc[i]['Min batch Size'],float(max_batch_masterfile.iloc[i]['Max Batch Size']),cycle_time_masterfile.iloc[i]['Cycle Time'],0)

def createOrders(bunching_criteria_instances, file, CONFIG):
    # file = pd.read_excel(INPUT_FILE_PATH)
    file = file.sort_values(by='order due date')
    all_orders = []
    cnt = 0
    while cnt < len(file):
        sku_obj = bunching_criteria_instances[file[CONFIG['bunching_criteria']].iloc[cnt]]
        order_qty = file['qty'].iloc[cnt]
        billet_nos = file['Billet Nos.'].iloc[cnt]
        order_rd = str(file['order release date'].iloc[cnt])
        order_dd = str(file['order due date'].iloc[cnt])
        order_so = str(file['so'].iloc[cnt])
        order_machine = file['Machine'].iloc[cnt]
        all_orders.append(Order(order_so,sku_obj,order_qty, billet_nos, order_rd,order_dd, False, sku_obj.early_readiness_days, order_machine))
        cnt += 1
    return all_orders


def calcQuantity(bunch, quant_criteria, CONFIG):
    total_quantity = 0
    for order in bunch:
        total_quantity += order.__getattribute__(CONFIG[quant_criteria])
    return total_quantity

def calcRemSpace(sku, bunches, CONFIG):
    """This function takes sku object and list of bunches as input.
       The output that it generates is an integer value that tells the 
       total space(quantity) that the previous bunches can avail in order 
       to adjust some extra orders."""
    max_qty = sku.moq_ul
    rem_qty = 0
    for bunch in bunches:
        if bunch[0].order_sku.sku_name == sku.sku_name and calcQuantity(bunch,'bunching_max_cutoff_criteria', CONFIG) < max_qty:
            rem_qty += max_qty - calcQuantity(bunch,'bunching_max_cutoff_criteria', CONFIG)
            pass
    return rem_qty


def calcSeqScore(current_date,bunches,CONFIG):

    """This function will check the score of the bunch in
    terms of the number of orders missing their due dates."""

    current_date = datetime.datetime.strptime(current_date,'%Y-%m-%d %H:%M:%S')
    score = 0
    for index,bunch in enumerate(bunches):
        if index != 0 and bunch[0].order_sku.sku_name != bunches[index-1][0].order_sku.sku_name:
            map = switchMapGenerator(CONFIG=CONFIG)
            current_date += datetime.timedelta(minutes=map[bunches[index-1][0].order_sku.sku_name][bunch[0].order_sku.sku_name])

        for order in bunch:
            sku = order.order_sku.sku_name
            sku_ct = order.order_sku.cycle_time
            order_qty = order.order_qty
            try:
                order_dd = datetime.datetime.strptime(order.order_dd, '%Y-%m-%d %H:%M:%S')
            except:
                current_date += datetime.timedelta(minutes=int(order_qty*sku_ct))
                continue

            try:
                order_early_readiness_date = order.early_readiness_date
            except:
                current_date += datetime.timedelta(minutes=int(order_qty*sku_ct))
                continue
            
            order_fin_dt = current_date + datetime.timedelta(minutes=order_qty*sku_ct) 
            current_date = order_fin_dt
            delay = order_fin_dt - order_dd
            early_allocation = order_early_readiness_date - order_fin_dt

            if int(delay.days) > 0:
                # score -= delay.seconds/60
                score -= 4*delay.days + 4*delay.seconds/(3600 * 24)
            elif early_allocation.days > 0:
                score -= 1*early_allocation.days + 1*early_allocation.seconds/(3600 * 24)
                pass
  
    return score

def bunchingUnitBasedCycleTime(bunch, mts_order,CONFIG):
    return (sum(order.__getattribute__(CONFIG['cycle_time_criteria']) for order in bunch if order.__getattribute__(CONFIG['cycle_time_criteria'])!=None)/\
        sum(order.__getattribute__(CONFIG['bunching_unit']) for order in bunch if order.__getattribute__(CONFIG['cycle_time_criteria'])!=None))\
        *mts_order.__getattribute__(CONFIG['bunching_unit'])


def calcBunchExecTime(bunch,CONFIG):
    """This function will calculate the execution time of a bunch"""
    total_qty = 0
    for order in bunch:
        if order.__getattribute__(CONFIG['cycle_time_criteria']) == None:
            setattr(order,CONFIG['cycle_time_criteria'],bunchingUnitBasedCycleTime(bunch,order,CONFIG) )
        total_qty += order.__getattribute__(CONFIG['cycle_time_criteria'])
    return total_qty * order.order_sku.cycle_time


def displayBunches(all_bunches):
    for i,bunch in enumerate(all_bunches):
        print(f'Bunch {i+1}: ', end =' ')
        for order in bunch:
            if order.mts_bool == True:
                print(f' | MTS : {order.order_sku.sku_name}-{order.order_qty}', end=' ') 
            else:
                print(f'{order.so_no} :: {order.order_sku.sku_name}-{order.order_qty}', end=',')
        print('\n')
        print('- - - - - - - - - - - - - - - - - - - ')


def switchMapGenerator(CONFIG):
    """ This function generates the context witching dictionary based on the input file.
    """
    warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
    INPUT_FILE_PATH = f"{CONFIG['filepaths']['input_file_path']}\\{os.listdir(CONFIG['filepaths']['input_file_path'])[0]}"
    map = pd.read_excel(INPUT_FILE_PATH, sheet_name='Switching Cost Matrix', index_col=False)
    map.set_index('Unnamed: 0', inplace=True)
    map = map.to_dict(orient='index')
    return map

def calcBunchingCriteriaSwitchTime(prev_sku,next_sku,CONFIG):
    map = switchMapGenerator(CONFIG)
    return map[prev_sku][next_sku]

def nextSwitchbunchingCriteria(sku, map):
    for key,val in sorted(map[sku].items(), key = lambda item:(item[1])):
        yield (key,val)

def findBunchIdx(sku, bunches):
    """This function will return the index of the bunch which has the given sku"""
    for idx, bunch in enumerate(bunches):
        if bunch[0].order_sku.sku_name == sku:
            return idx
    return None


def execDateCalculator(current_date,order,CONFIG):
    order_exec_time = order.__getattribute__(CONFIG['cycle_time_criteria']) * order.order_sku.cycle_time
    return current_date + datetime.timedelta(minutes= int(order_exec_time)), datetime.timedelta(minutes= int(order_exec_time))

def consecutiveBunchValidator(bunches):
    consec_sku = bunches[0].order_sku.sku_name
    consec_sku_moq_ul = bunches[0].order_sku.moq_ul

def skuToBunchMap(bunch,bunch_idx,map):
    sku = bunch[0].order_sku.sku_name
    if sku not in map:
        map[sku] = [bunch_idx]
    else:
        map[sku].append(bunch_idx)
    return map
    
def adjustMTS(all_bunches):
    """This function will adjust the mts value of all the bunches"""
    for bunch in all_bunches:
        for i,order in enumerate(bunch):
            if order.mts_bool == True:
                if i != len(bunch) - 1 and (calcQuantity(bunch[:i],'bunching_max_cutoff_criteria') + calcQuantity(bunch[i+1:]), 'bunching_max_cutoff_criteria') < bunch[0].order_sku.moq_ll:
                    bunch[i].order_qty = bunch[0].order_sku.moq_ll - (calcQuantity(bunch[:i], 'bunching_max_cutoff_criteria') + calcQuantity(bunch[i+1:], 'bunching_max_cutoff_criteria'))
                elif i != len(bunch) - 1 and (calcQuantity(bunch[:i], 'bunching_max_cutoff_criteria') + calcQuantity(bunch[i+1:], 'bunching_max_cutoff_criteria')) > bunch[0].order_sku.moq_ll:
                    bunch.pop(i)

def sortBunch(order):
    # If due_date is None, return a special value (e.g., datetime.max)
    if order.order_dd is None:
        return datetime.datetime.max
    # Otherwise, return the actual due_date
    return datetime.datetime.strptime(order.order_dd,'%Y-%m-%d %H:%M:%S')

def boolAdjacentBunches(sku,final_seq):
    netAdjacentBunchSize = 0
    for bunch in final_seq[::-1]:
        if bunch[0].order_sku.sku_name == sku:
            netAdjacentBunchSize += calcQuantity(bunch=bunch,quant_criteria='bunching_max_cutoff_criteria')

def generateOutput(ol_no,fin_seq, current_date, CONFIG):
    wb = Workbook()
    sheet1 = wb.add_sheet('Sheet 1')
    row = 1
    sheet1.write(0, 0, 'so')
    sheet1.write(0, 1, 'sku')
    sheet1.write(0, 2, 'qty')
    sheet1.write(0, 3, 'Billet Nos.')
    sheet1.write(0, 4, 'order release date')
    sheet1.write(0, 5, 'order due date')
    sheet1.write(0, 6, 'actual order start date')
    sheet1.write(0, 7, 'actual order completion date')
    sheet1.write(0, 8, 'OTIF')
    sheet1.write(0, 9, 'Machine')
    for index,bunch in enumerate(fin_seq):
        if index != 0 and fin_seq[index-1][0].order_sku.sku_name != bunch[0].order_sku.sku_name:
            prev_sku = fin_seq[index-1][0].order_sku.sku_name
            next_sku = fin_seq[index][0].order_sku.sku_name
            current_date += datetime.timedelta(minutes=calcBunchingCriteriaSwitchTime(prev_sku, next_sku,CONFIG))
        for order in bunch:
            print(f'{order.order_sku.sku_name}, {order.order_rd}')
            sheet1.write(row, 0, order.so_no)
            sheet1.write(row, 1, order.order_sku.sku_name)
            sheet1.write(row, 2, str(order.order_qty))
            sheet1.write(row, 3, str(order.order_billet_nos))
            sheet1.write(row, 4, order.order_rd)
            sheet1.write(row, 5, order.order_dd)
            current_date, exec_time = execDateCalculator(current_date, order, CONFIG)
            sheet1.write(row, 6, str(current_date - exec_time))
            sheet1.write(row, 7, str(current_date))
            try:
                delay = current_date - dt.datetime.strptime(order.order_dd,'%Y-%m-%d %H:%M:%S')
            except:
                pass
            if int(delay.days) > 0:
                sheet1.write(row, 8,'FALSE')
            else:
                sheet1.write(row, 8, 'TRUE')
            sheet1.write(row, 9, order.order_machine)
            row += 1
        row += 1
    wb.save(f'./output/sequencing_output_{ol_no+1}.csv')
def skuToBunchMap(bunch,bunch_idx,map):
    sku = bunch[0].order_sku.sku_name
    if sku not in map:
        map[sku] = [bunch_idx]
    else:
        map[sku].append(bunch_idx)
    return map

def find_combinations(engine_instance,data, target, TIMER):
    """"This function takes the order book as input along with the moq of the first order
    as input, and finds the best combination of orders from the order book to form the bunch.
    """
    filtered_orders = [order for order in data if order.order_sku.sku_name == data[0].order_sku.sku_name]
    if calcQuantity(filtered_orders,'bunching_min_cutoff_criteria', engine_instance.CONFIG) < data[0].order_sku.moq_ll:
        engine_instance.combination_map.append({calcQuantity(filtered_orders, 'bunching_min_cutoff_criteria',engine_instance.CONFIG):filtered_orders})
        return None, True
    first_order_qty = float(data[0].__getattribute__(engine_instance.CONFIG['bunching_unit']))
    target_sum = target - float(data[0].__getattribute__(engine_instance.CONFIG['bunching_unit']))
    if target < data[0].__getattribute__(engine_instance.CONFIG['bunching_unit']):
        return [data[0]], False
    elif target_sum == 0:
        return [data[0]], False
    if target_sum > 0:
        key = data[0].order_sku.sku_name  # Assuming the first dictionary's key should be used
        return find_combinations_recursive(engine_instance,data[1:], key, target_sum, 0, [data[0]], target,first_order_qty, TIMER), False


def find_combinations_recursive(engine_instance,data, key, target_sum, current_sum, combination, target, first_obj_qty, TIMER):
    
    """"This function will recursively find the very first combination of orders that meets the 
    moq quantity for the bunch to be formed. If the current summation of the current state of
    bunch exceeds the moq, None will be returned. In the processs of finding the perfect combination
    we keep on saving the combinations in a combination map, and whenever we get a None, we will
    take the best combination from the combination map and add the MTS to it."""
    if time.perf_counter() - TIMER >60:
        return None


    if current_sum > target_sum or not data:
        if current_sum > target_sum:
            engine_instance.combination_map.append({current_sum:combination})
            return None
        return None

    for index, order in enumerate(data): # optimization needed, in every recursive call, data is parsed from index 0 which is not required
        if key == order.order_sku.sku_name:
            new_combination = combination + [order]
            new_sum = current_sum + order.__getattribute__(engine_instance.CONFIG['bunching_unit'])
            if new_sum == target_sum:
                return new_combination
            elif new_sum < target_sum:  
                # combination_map.append({new_sum:new_combination})
                result = find_combinations_recursive(engine_instance,data[index + 1:], key, target_sum, new_sum, new_combination, target, first_obj_qty, TIMER)
                if result:
                    return result
            elif new_sum > target_sum and calcQuantity(new_combination, 'bunching_max_cutoff_criteria', engine_instance.CONFIG) <= order.order_sku.moq_ul: 
                return new_combination

    ## alternate bunching logic

    if calcQuantity(combination, 'bunching_min_cutoff_criteria') ==  target_sum:
        return combination
    else:
        return None
    

def orderShifter(valid_mts_sku, all_bunches, CONFIG):
    """This function will shift the orders from the last mts bunch to the 
    previous bunches."""
    orders_to_be_shifted = []
    for sku in valid_mts_sku:
        for b in range(len(all_bunches),0,-1):
            bunch = all_bunches[b-1]
            if bunch[-1].order_sku.sku_name == sku:
                if bunch[-1].mts_bool == True and not orders_to_be_shifted:
                    orders_to_be_shifted = bunch
                elif len(orders_to_be_shifted)!= 0:
                    if orders_to_be_shifted[-1].mts_bool == True:
                        bunch += orders_to_be_shifted[:-1]
                    else:
                        bunch += orders_to_be_shifted
                    try:
                        all_bunches.remove(orders_to_be_shifted)
                        orders_to_be_shifted = []
                    except:
                        pass
                    total_bunch_qty = calcQuantity(bunch, 'bunching_min_cutoff_criteria', CONFIG)
                    
                    if total_bunch_qty > bunch[0].order_sku.moq_ul:
                        ## calc the orders that need to be shifted leftward
                        orders_to_be_shifted = []
                        for i in range(len(bunch)):
                            if calcQuantity(bunch, 'bunching_max_cutoff_criteria') - calcQuantity(orders_to_be_shifted, 'bunching_max_cutoff_criteria', CONFIG) <= bunch[0].order_sku.moq_ul:
                                break
                            else:
                                orders_to_be_shifted.append(bunch[i])
                    all_bunches[b-1]=[ele for ele in bunch if ele not in orders_to_be_shifted]
    return all_bunches



def alter_sequence_bunches_by_grouped_criteria(sequence, CONFIG):
    def adjust_subsequence(previous_criteria_group, previous_bunch_index, required_amt, sequence):
        target_bunches = []
        if required_amt > 0:   # 
            for i in range(previous_bunch_index + 1,len(sequence[previous_bunch_index:])):
                if sequence[i][0].order_sku.criteria_group == previous_criteria_group:
                    target_bunches.append(sequence[i])
            target_bunches = sorted(target_bunches, key = lambda inner_list: calcQuantity(inner_list, 'bunching_min_cutoff_criteria', CONFIG))
            cumulative_size = 0
            new_subsequence = []
            for bunch in target_bunches:
                cumulative_size += calcQuantity(bunch, 'bunching_min_cutoff_criteria', CONFIG)
                new_subsequence.append(bunch)
                sequence.remove(bunch)
                if cumulative_size >= required_amt:
                    sequence[previous_bunch_index+1:previous_bunch_index+1] = new_subsequence
                    return sequence
            return None
        elif required_amt < 0:
            pass
    operator_mapping = {
    '>=': operator.ge,
    '<=': operator.le,
    '==': operator.eq,
    '!=': operator.ne,
    '<': operator.lt,
    '>': operator.gt,
    }
    order_book_path = f"{CONFIG.get('filepaths').get('input_file_path')}\\{os.listdir(CONFIG.get('filepaths').get('input_file_path'))[0]}"
    grouped_criteria_masterfile = pd.read_excel(order_book_path,sheet_name='Grouped Criteria')
    for bunch_index,(previous_bunch,current_bunch) in enumerate(zip(sequence, sequence[1:])):
        previous_criteria_group = previous_bunch[0].order_sku.criteria_group
        current_criteria_group = current_bunch[0].order_sku.criteria_group
        required_conditions_df = grouped_criteria_masterfile[(grouped_criteria_masterfile['Previous_Group_Key'] == previous_criteria_group) & \
        (grouped_criteria_masterfile['Current_Group_Key'] == current_criteria_group)]
        for index, row in required_conditions_df.iterrows():
            condition = operator_mapping.get(row['Comparison_Method'])
            if condition(calcQuantity(previous_bunch, 'bunching_max_cutoff_criteria',CONFIG),row['Criteria_On_Current_Group_Key']) == True:
                pass
            else:
                #check if any more bunches with same group are present.If they are present,
                #bring the smallest of them all in between the conflicting subsequence.
                required_amt = row['Criteria_On_Current_Group_Key'] - calcQuantity(previous_bunch, 'bunching_max_cutoff_criteria',CONFIG)
                altered_sequence = adjust_subsequence(previous_criteria_group, bunch_index, required_amt, sequence)
                if altered_sequence != None:  # if we get bunches to 
                    sequence = altered_sequence
                    return sequence
                else:
                    setattr(sequence[bunch_index][-1],CONFIG['bunching_max_cutoff_criteria'],row['Criteria_On_Current_Group_Key'])
                    return sequence


def order_to_machine_assigner():
    #load config
    with open('config.json', 'r') as config_file:
        CONFIG = json.load(config_file)
    # Load order book from the specified file path
    order_book_path = f"{CONFIG.get('filepaths').get('input_file_path')}\\{os.listdir(CONFIG.get('filepaths').get('input_file_path'))[0]}"
    order_book = pd.read_excel(order_book_path)
    unique_values = order_book['Machine'].unique()
    list_of_dfs = [order_book[order_book['Machine'] == value].reset_index(drop=True) for value in unique_values]
    return list_of_dfs

def output_plotter():
    with open('config.json', 'r') as config_file:
        CONFIG = json.load(config_file)
    output_files_path = CONFIG.get('filepaths').get('output_file_path')
    combined_output = []
    for fname in os.listdir(output_files_path):
        if fname.endswith('.csv'):
            file_path = os.path.join(output_files_path, fname)
            current_data = pd.read_excel(file_path)
            combined_output.append(current_data)
    combined_data = pd.concat(combined_output, ignore_index=True)

    combined_data = combined_data.sort_values(by='actual order start date')
    task = combined_data['sku']
    start = combined_data['actual order start date']
    finish = combined_data['actual order completion date']


    fig = px.timeline(combined_data, x_start='actual order start date', x_end='actual order completion date', y='Machine', color='sku',
                    title='Task overview', labels={'sku': 'SKU'})
    fig.update_yaxes(autorange='reversed')
    fig.update_layout(
        title_font_size=42,
        font_size=18,
        title_font_family='Arial'
    )

    plotly.offline.plot(fig, filename=f"{CONFIG.get('filepaths').get('output_file_path')}\\output.html")