import copy
import time
import datetime as dt
from packages.sequencing_engine.engine import sequencingEngine
from packages.sequencing_engine.operations import switchMapGenerator, order_to_machine_assigner, output_plotter


sequence_engine = None
def main():
    multi_machine_sequence = []
    ## for now we will create multiple instances based on no. of machines  using a for loop
    machinewise_orders = order_to_machine_assigner()
    for ol_no,order_book in enumerate(machinewise_orders):
        sequence_engine = sequencingEngine("config.json")    # here we are creating an instance of the engine
        CONFIG = sequence_engine.CONFIG
        sequence_engine.current_date = dt.datetime.strptime(CONFIG['current_datetime'],'%Y-%m-%d %H:%M:%S')
        switch_map = switchMapGenerator(CONFIG)
        # sequence_engine.load_order_book()
        sequence_engine.order_book = order_book
        sequence_engine.load_orders()
        sequence_engine.run_bunching()
        sequence_engine.run_order_shifting()
        #logic to call call sequencing
        sequence_engine.total_bunches = sequence_engine.all_bunches.__len__()
        sequence_engine.total_orders = sum(len(sl) for sl in sequence_engine.all_bunches)
        sequence_engine.relax_days = CONFIG['relax_days']
        sequence_engine.fin_seq = []
        sequence_engine.copy1 =copy.deepcopy(sequence_engine.all_bunches)
        sequence_engine.best_seq = []
        sequence_engine.fin_seq = sequence_engine.run_sequencing(bunches=sequence_engine.copy1,best_seq=sequence_engine.best_seq,\
                        sku=CONFIG['last_executed_criteria'],function_call_time=time.perf_counter(),\
                        TIMER=100000000,relax_days=0, current_time=sequence_engine.current_date,final_seq=[],\
                        final_seq_bool=False,seq_score_map={}, call_ct=0,switch_map=switch_map,CONFIG=CONFIG)
        while sum(len(sl) for sl in sequence_engine.fin_seq) != sequence_engine.total_orders:
            sequence_engine.copy2 =copy.deepcopy(sequence_engine.all_bunches)
            timer = int(input('enter wait time'))
            sequence_engine.fin_seq = sequence_engine.run_sequencing(bunches=sequence_engine.copy2,best_seq=[],sku=CONFIG['last_executed_criteria'],function_call_time=time.perf_counter()\
                                ,TIMER=timer,relax_days=sequence_engine.relax_days, current_time=sequence_engine.current_date, final_seq=[],\
                                    final_seq_bool=False, seq_score_map={},call_ct=0,switch_map=switch_map,CONFIG=CONFIG)
            sequence_engine.relax_days += 1
        ##Save the output
        sequence_engine.save_output(ol_no,sequence_engine.fin_seq,sequence_engine.current_date,CONFIG)
    output_plotter()
if __name__ == "__main__":
    main()