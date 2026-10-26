"""Run a supplied study script with Python network connections disabled."""
from pathlib import Path
import runpy
import sys

def block_network(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto"}:
        raise RuntimeError("Network access is disabled during archive reproduction")

if __name__ == "__main__":
    script = Path(sys.argv[1]).resolve()
    sys.argv = [str(script), *sys.argv[2:]]
    sys.path.insert(0, str(script.parent))
    sys.addaudithook(block_network)
    runpy.run_path(str(script), run_name="__main__")
