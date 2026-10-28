import os
from pathlib import Path
import threading
import webbrowser

os.chdir(Path(__file__).parent)
if __name__ == "__main__":
    import uvicorn
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    uvicorn.run("server:app", host="127.0.0.1", port=8765, log_level="warning")
