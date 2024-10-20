import importlib
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import reloaded


class ReloadingWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("/reloaded.py"):
            print()
            print(f"reloading {event=}")
            with open(event.src_path, "r") as f:
                try:
                    # TODO(miikka) How to reload `reloaded2` if it changes?
                    importlib.reload(reloaded)
                    # Reload using exec:
                    # exec(f.read(), globals=globals(), locals=reloaded.__dict__)
                except Exception:
                    traceback.print_exc()


def main():
    event_handler = ReloadingWatcher()
    observer = Observer()
    observer.schedule(event_handler, ".")
    observer.start()
    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
