#!/usr/bin/env python3

import json
import os
import glob
import argparse

def sites(data):
    for i, site in data["SITE_INDEX"].items():
        yield i, site

def types(site):
    for k, t in site["SITE_TYPE"].items():
        yield k, t

def bels(stype):
    for k, bel in stype["BEL"].items():
        yield k, bel

def spips(stype):
    for k, spip in stype["SITE_PIP"].items():
        yield k, spip

def pipval_list(spip):
    return spip["SITE_PIP_VALUE"]

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

def eachpip(file):
    with open(file) as f:
        data = json.load(f)
        tile = file.split(".")[1]
        for i, site in sites(data):
            for typek, stype in types(site):
                for spipk, spip in spips(stype):
                    yield tile, i, typek, spipk, pipval_list(spip)
    
def ppip(tile, ix, site, name, pip):
    if len(pip) > 1:
        return
    con = next(iter(pip))
    print(f"{tile}.{tile}_{name}.{tile}_{con} always")

parser = argparse.ArgumentParser(
    description="Check database files for bel select/disable rules."
)
parser.add_argument("--tile")
parser.add_argument("--ignore_bram_inits", action="store_true")
args = parser.parse_args()

files = glob.glob("db.*.json")
if args.tile is not None:
    files = [f"db.{args.tile}.json"]

for file in files:
    for p in eachpip(file):
        ppip(*p)
