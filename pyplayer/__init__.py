from pyplayer.cli import main
import sys
import io

if __name__ == "__main__":
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
