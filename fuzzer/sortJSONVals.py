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

# This material is based upon work supported  by the Office of Naval Research
# under Contract No. N68335-20-C-0569. Any opinions, findings and conclusions 
# or recommendations expressed in this material are those of the author(s) and 
# do not necessarily reflect the views of the Office of Naval Research.

# Comparing two database .json files to see if they are the same is challenging 
# because some things come out in a different order.
#
# Specifically, when multiple groups of bits can turn on a feature (the feature 
# is an OR of different sets of bits), they come out in the JSON file in different
# orders.
#
# This program reads a JSON file, finds the value sections and sorts the groups of
# bits and prints them out in sorted order.  By running it on two different .json 
# database files the results can then be compared.  If the database files have the 
# same information but the values are in different orders, the output of this
# program will be identical.

# Typical usage:
#    python3 sortJSONVals.py path1/db.DSP_R.json
#    python3 sortJSONVals.py path2/db.DSP_R.json
#    diff path1/db.DSP_R.json.sortedVals path2/db.DSP_R.json.sortedVals

import json
import argparse
#from types import NoneType


def lsort(lst):
    tot = 0
    for e in lst:
        if e.startswith("!"):
            for i in range(2):
                tot -= int(e[1:].split('_')[i])
        else:
            for i in range(2):
                tot += int(e.split('_')[i])
    return tot

def processFile(file, prefix):
    with open(file) as f:
        j = json.load(f)

    dest = file.split("/")[-1]
    with open(prefix + '-' + dest + ".sortedVals", 'w') as fs:
        for top in j:
            if top != "SITE_INDEX":
                continue

            for snk in j[top]:
                for st in j[top][snk]["SITE_TYPE"]:
                    for b1 in j[top][snk]["SITE_TYPE"][st]:
                        if b1 == "SITE_PIP":
                            continue
                        for bel in j[top][snk]["SITE_TYPE"][st][b1]:
                            for prop in j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"]:
                                for val in j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"][prop]["VALUE"]:
                                    print(snk, st, bel, prop, val, end='', file=fs)
                                    vals = j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"][prop]["VALUE"][val]
                                    if len(vals) > 1:
                                        #print(" :: ", len(vals), file=fs)
                                        vals.sort(key=lsort)
                                    print(json.dumps(vals, indent=2), file=fs)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fileNameA', default=None)
    parser.add_argument('--fileNameB', default=None)
    args = parser.parse_args()

    if args.fileNameA:
        processFile(args.fileNameA, "A")
    if args.fileNameB:
        processFile(args.fileNameB, "B")

if __name__ == "__main__":
    main()

    