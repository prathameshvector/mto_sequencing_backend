from packages.sequencing_engine.engine import sequencingEngine
from packages.sequencing_engine.operations import switchMapGenerator


sequence_engine = None
def main():
    sequence_engine = sequencingEngine("config.json")    # here we are creating an instance of the engine
    CONFIG = sequence_engine.CONFIG
    switch_map = switchMapGenerator(CONFIG)
    sequence_engine.load_order_book()
    sequence_engine.run_bunching()
    sequence_engine.run_sequencing()
    sequence_engine.save_output()

if __name__ == "__main__":
    main()