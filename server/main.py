from gabriel_server import local_engine
from ikea_engine import IkeaEngine
import logging


logging.basicConfig(level=logging.INFO)


def main():
    def engine_factory():
        return IkeaEngine()

    local_engine.run(engine_factory, 'ikea', 60, 9099, 2)


if __name__ == '__main__':
    main()
