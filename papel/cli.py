"""Linea de comandos: encode imprime, decode lee escaneos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from papel.constants import DEFAULT_MODULE_MM, LASER_MODE
from papel.document import available_modes, decode_paths, encode_pdf
from papel.errors import PapelError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="papel")
    sub = parser.add_subparsers(dest="command", required=True)

    encode = sub.add_parser("encode", help="armar un PDF para imprimir")
    encode.add_argument("archivo")
    encode.add_argument("-o", "--output", required=True)
    encode.add_argument("--mode", default=LASER_MODE, choices=list(available_modes()))
    encode.add_argument("--module-mm", type=float, default=DEFAULT_MODULE_MM)

    decode = sub.add_parser("decode", help="recuperar el archivo desde escaneos")
    decode.add_argument("scans", nargs="+")
    decode.add_argument("-o", "--output", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "encode":
            source = Path(args.archivo)
            pdf = encode_pdf(
                source.read_bytes(),
                source.name,
                mode=args.mode,
                module_mm=args.module_mm,
            )
            Path(args.output).write_bytes(pdf)
        else:
            restored = decode_paths(args.scans)
            Path(args.output).write_bytes(restored)
    except PapelError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0

