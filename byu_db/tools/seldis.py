#!/usr/bin/env python3

import json
import os
import glob
import argparse


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
    parser.add_argument("--tile")
    parser.add_argument("--ignore_bram_inits", action="store_true")
    args = parser.parse_args()

    files = glob.glob("db.*.json")
    if args.tile is not None:
        files = [f"db.{args.tile}.json"]

    print("GRID:BYU")

    for file in files:
        with open(file) as f:
            data = json.load(f)
            tile = file.split(".")[1]
            for i, site in sites(data):
                ps = {}
                union = set()
                countp = {}
                for typek, stype in types(site):
                    v = propset(stype, args.ignore_bram_inits)
                    ps[typek] = v
                    union |= v
                    for p in v:
                        countp[p] = countp.get(p, 0) + 1
                for k, v in ps.items():
                    # output disable rules
                    diff = union - v
                    for x in diff:
                        printUnique(f"# SITE:DISABLE:{tile}@{i}:{k}:{x[0]}")
                        bits = genBits(x[1])
                        printUnique(f"SITE:DISABLE:{tile}@{i}:{k}{bits}")
                    # output select rules
                    pflag = False
                    for x in v:
                        if countp.get(x, 0) == 1:
                            pflag = True
                            printUnique(f"# SITE:SELECT:{tile}@{i}:{k}:{x[0]}")
                            bits = genBits(x[1])
                            printUnique(f"SITE:SELECT:{tile}@{i}:{k}{bits}")


if __name__ == "__main__":
    main()
