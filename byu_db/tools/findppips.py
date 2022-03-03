#!/usr/bin/env python3

import json
import os
import glob
import argparse
import sys


def sites(data):
    for i, site in data["SITE_INDEX"].items():
        yield i, site


def types(site):
    if len(site["SITE_TYPE"]) <= 1:
        return
    for k, t in site["SITE_TYPE"].items():
        yield k, t


def bels(stype):
    for k, bel in stype["BEL"].items():
        yield k, bel


def props(bel):
    for k, prop in bel["CONFIG"].items():
        yield k, prop


def vals(prop):
    for k, val in prop["VALUE"].items():
        yield k, val


def on(val):
    if "ON" not in val:
        return []
    return sorted(val["ON"])


def off(val):
    if "OFF" not in val:
        return []
    return sorted(val["OFF"])


def propset(stype, ignorebraminit):
    res = set()
    for belk, bel in bels(stype):
        for propk, prop in props(bel):
            if ignorebraminit and "BUS" in prop and prop["BUS"] == "BLOCK_RAM":
                continue
            for valk, val in vals(prop):
                if on(val) or off(val):
                    res |= {
                        (
                            ":".join([belk, propk, valk]),
                            f"{on(val)} !{off(val)}",
                        )
                    }
    return res


def genBits(x):
    x = x.replace("[", "").replace("]", "").replace("'", "").replace(" ", "")
    x = x.split("!")
    x[0] = x[0].split(",")
    x[1] = x[1].split(",")
    ret = " "
    for b in x[0]:
        if b != "":
            ret += f"(1:0:{b.split('_')[0]}:{b.split('_')[1]})"
    for b in x[1]:
        if b != "":
            ret += f"(0:0:{b.split('_')[0]}:{b.split('_')[1]})"
    return ret


uniq = set()


def printUnique(s):
    if s not in uniq:
        print(s)
        uniq.add(s)


def main():
    parser = argparse.ArgumentParser(
        description="Check database files for select/disable rules."
    )
    parser.add_argument("candidatesfile")
    parser.add_argument("databasedirectory")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--tile")
    args = parser.parse_args()

    files = glob.glob(f"{args.databasedirectory}/ppips_*.db")
    if args.tile is not None:
        files = [f"{args.databasedirectory}/ppips_{args.tile}.db"]

    files.sort()
    ppips = []
    for fil in files:
        if args.verbose:
            print(f"Processing file: {fil}")
        with open(fil) as f:
            for lin in f.readlines():
                lin, typ = lin.rstrip().split(" ")
                lin = lin.split(".")
                ttype = lin[0]
                w2 = lin[1]
                w1 = lin[2]
                s = f"{w1}:{w2}"
                if args.verbose:
                    print(f"{s}")
                ppips.append(s)

    with open(args.candidatesfile) as f:
        for lin in f.readlines():
            toks = lin.strip().split(":")
            if toks[0] != "PIP":
                continue
            s = f"{toks[2]}:{toks[3]}"
            if s in ppips:
                print(f"IS a PPIP: {lin.strip()}")
            else:
                print(f"NOT a PPIP: {lin.strip()}")


if __name__ == "__main__":
    main()
