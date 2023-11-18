from testengine import engine

def main():
    sequence_engine = engine()
    sequence_engine.bun()
    # Now combination_map for the specific instance of engine is modified
    print(sequence_engine.combination_map)

if __name__ == "__main__":
    main()
