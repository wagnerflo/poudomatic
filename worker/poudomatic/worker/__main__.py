import argparse
import logging
import sys
import time

from .environment import Environment
from .storage import Storage

def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "dataset", metavar="DATASET", help=(
                "ZFS dataset to use as Poudomatic's enviroment root."
            )
        )

        logging.basicConfig(level=logging.DEBUG)

        args = parser.parse_args()
        env = Environment(args.dataset)

        with Storage(env.etc_path / "taskdb" / "taskdb.sqlite") as stor:
            while True:
                if task := stor.start_next_task():
                    task_id,task = task
                    logging.info(f"Starting task {task_id}.")
                    try:
                        res = {
                            "status": "success",
                            "result": task.run(env, task_id),
                        }
                        logging.info(f"Task {task_id} completed successfully.")
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        logging.exception(f"Task {task_id} died with exception.")
                        res = { "status": "error", "detail": str(e) }
                    finally:
                       stor.end_task(task_id, res)
                else:
                    time.sleep(5)

    except KeyboardInterrupt:
        return

if __name__ == "__main__":
    sys.exit(main() or 0)
