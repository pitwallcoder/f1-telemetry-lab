"""Command-line pieces every chart shares: year, circuit, output options, and a clean exit when data is missing."""
import argparse
import sys

from pitwall import openf1


def parser(prog, doc, code_example, circuit=True):
    p = argparse.ArgumentParser(prog=prog, description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("year", type=int)
    if circuit:
        p.add_argument("circuit", help="official circuit short name, e.g. 'Mexico City', Monza")
    p.add_argument("--code", default="PW-DRAFT", help=f"series code for the chart and its folder, e.g. {code_example}")
    p.add_argument("--out", default="out")
    return p


def fetch(load):
    """load(), exiting with OpenF1's message instead of a traceback when the data isn't there."""
    try:
        return load()
    except openf1.DataNotFound as error:
        sys.exit(f"error: {error}")
