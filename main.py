from packages.sequencing_engine.engine import sequencingEngine
sequenceEngine = None
def main():
    sequence_engine = sequenceEngine("config.json")
    CONFIG = sequence_engine.CONFIG
    sequence_engine.load_orderbook()
    sequence_engine.run_bunching()
    sequence_engine.run_sequence()
    sequence_engine.save_output()

if __name__ == "main":
    main()