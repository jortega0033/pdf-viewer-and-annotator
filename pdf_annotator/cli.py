"""Command line entry point."""

import argparse
import pathlib
import sys
import time

from .server import create_server
from .storage import StorageError


def _port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer from 0 to 65535")
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer from 0 to 65535")
    return port


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m pdf_annotator",
        description="Local PDF viewer and annotator (binds 127.0.0.1 only).",
    )
    parser.add_argument("--data-dir", required=True,
                        help="directory for the notes database")
    parser.add_argument("--port", required=True, type=_port,
                        help="TCP port, 0 for an ephemeral port")
    return parser


def _one_line(text):
    return " ".join(str(text).split())


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        app = create_server(pathlib.Path(args.data_dir), args.port)
    except StorageError as exc:
        sys.stderr.write("error: %s\n" % _one_line(exc))
        return 2
    except OSError as exc:
        sys.stderr.write("error: cannot listen on port: %s\n" % _one_line(exc))
        return 1
    try:
        app.start()
        print("Serving on http://127.0.0.1:%d/" % app.port, flush=True)
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
    return 0
