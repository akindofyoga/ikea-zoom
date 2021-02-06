from gabriel_server import local_engine
from sandwich_engine import SandwichEngine
import logging


logging.basicConfig(level=logging.INFO)


def main():
    def engine_factory():
        return SandwichEngine()

    local_engine.run(engine_factory, 'sandwich', 60, 9099, 2)


if __name__ == '__main__':
    main()
