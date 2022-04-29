#!/usr/bin/env python3

# Copyright 2020-2022 BitRec Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0


import json
import os
import glob
import argparse

allowbels = {}
onbels = {"INBUF_EN", "OUTBUF"}


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


def eachval(file):
    with open(file) as f:
        data = json.load(f)
        tile = file.split(".")[1]
        for i, site in sites(data):
            for typek, stype in types(site):
                for belk, bel in bels(stype):
                    for propk, prop in props(bel):
                        for valk, val in vals(prop):
                            yield tile, i, typek, belk, propk, valk, on(val), off(val)


def bitsculpt(on, bits):
    res = []
    for b in bits:
        post = b.split("_")
        res.append(f"({on}:0:{post[0]}:{post[1]})")
    return "".join(res)


uniq = set()


def printUnique(s):
    if s not in uniq:
        print(s)
        uniq.add(s)


def enable(tile, ix, site, bel, prop, val, on, off):
    if not on:
        return
    if bel in allowbels:
        printUnique(f"# CFG:ENABLE:{tile}@{ix}:{site}:{bel}   {prop} {val}")
        printUnique(
            f"CFG:ENABLE:{tile}@{ix}:{site}:{bel} {bitsculpt('1',on)} {bitsculpt('0',off)}"
        )
    if bel in onbels:
        printUnique(f"# CFG:ENABLE:{tile}@{ix}:{site}:{bel}   {prop} {val}")
        printUnique(f"CFG:ENABLE:{tile}@{ix}:{site}:{bel} {bitsculpt('1',on)}")


elim = {}


def disable(tile, ix, site, bel, prop, val, on, off):
    if bel not in allowbels and bel not in onbels:
        return
    key = f"CFG:DISABLE:{tile}@{ix}:{site}:{bel}"
    key = (key, prop)
    elim.setdefault(key, [True, set()])
    if not on:
        elim[key][0] = False
        return
    elim[key][1] |= set(on)


parser = argparse.ArgumentParser(
    description="Check database files for bel select/disable rules."
)
parser.add_argument("--tile")
parser.add_argument("--ignore_bram_inits", action="store_true")
args = parser.parse_args()

files = glob.glob("db.*.json")
if args.tile is not None:
    files = [f"db.{args.tile}.json"]

print("GRID:BYU")

for file in files:
    for p in eachval(file):
        enable(*p)
        disable(*p)
    for k, v in elim.items():
        if v[0]:
            printUnique(f"# {k[0]} {k[1]}")
            printUnique(f"{k[0]} {bitsculpt('0', v[1])}")
