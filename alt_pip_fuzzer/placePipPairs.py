
import jpype
import jpype.imports
from jpype.types import *
import sys
import argparse
import random
from functools import reduce
import datetime
import json

jpype.startJVM(classpath=["rapidwright-2021.2.0-standalone-lin64.jar"])

from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim

def init_rapidwright(part_name):
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)
    return (device,design)

def msg(s='', hdr='', end="\n", file=sys.stdout):
    print(f"{hdr}{str(s)}", end=end, file=file)

def errmsg(s='', hdr='', end="\n"):
#    print(f"{hdr}{str(s)}", file=sys.stderr, end=end)
#    msg(f"{hdr}{str(s)}", end=end)
    msg(s, hdr, file=sys.stderr, end=end)

def getPpipName(p):
    return str(p).split('.')[-1]

def getTileName(t):
    st = str(t)
    if "/" in st:
        return st.split('/')[0]
    else:
        return st

#################################################################################################################

def canPlace(sol, usedTiles):
    ok = True
    for s in sol:
        s = getTileName(s.split(' ')[0])
        if s in usedTiles:
            ok = False
    return ok

def place(sol, usedTiles, sitePins):
    for s in sol:
        tmp = s.split(' ')
        s = getTileName(tmp[0])
        if len(tmp) > 1:
            sitePins.add(tmp[-1])
        usedTiles.add(s)

#################################################################################################################

def main():
    global device, args

    parser = argparse.ArgumentParser()
    parser.add_argument('--placelimit',default=50)
    parser.add_argument('--stdoutToFile', default=None)
    parser.add_argument('--pipsfile', default="pipresults.txt")
    parser.add_argument('--resultsfile', default='packedResults.txt')
    args = parser.parse_args()

    if args.stdoutToFile:
        sys.stdout = open(args.toFile, 'w')
    
    errmsg(f"\n[LOG] main, args = {args}")

    device, design = init_rapidwright("xc7a100ticsg324-1L")

    solutions = {}
    sitePins = set()

    resultsFile = open(args.resultsfile, 'w')

    # Process PIPs until device full
    with open(args.pipsfile) as f:
        lines = f.readlines()
    
    for i in range(len(lines)):
        lines[i] = lines[i].strip()
        
    i = 0
    while i < len(lines):
        while i < len(lines) and not lines[i].startswith("PIPSolution1:"):
            i += 1
        if i >= len(lines):
            break
        lin = lines[i]
        pipName = lin.split(' ')[1].split('.')[1]
        sol = [None, None]
        i += 2
        for j in range(2):
            sol[j] = []
            lin = lines[i]
            while len(lin) != 0:
                if lin == "--":
                    i += 1
                else:
                    sol[j].append(lin)

                i += 1
                lin = lines[i]
            i += 1
        assert pipName not in solutions
        solutions[pipName] = sol

    # Pack solutions into a device
    usedTiles = set()
    placeLimit = int(args.placelimit)
    placed = 0
    bitnum = 1
    bitstreams = {}
    while (True):
        while len(solutions) > 0 and placed < placeLimit:
            tmpSol = solutions.copy()
            placedSolutions = dict()
            for key,sol in solutions.items():
                if canPlace(sol[0], usedTiles) and canPlace(sol[1], usedTiles):
                    place(sol[0], usedTiles, sitePins)
                    place(sol[1], usedTiles, sitePins)
                    placedSolutions[key] = sol
                    placed += 1
                    tmpSol.pop(key)
                    if placed == placeLimit:
                        break;
            #random.shuffle(tmpSol)
            solutions = tmpSol
            msg(f"Was able to place {placed} solutions, continuing...")
            if len(solutions) < 4:
                s = json.dumps(solutions, indent=2)
                #msg(s)
            placed = 0
            usedTiles = set()
            bitstreams[f"Bitstream:{str(bitnum).zfill(3)}"] = placedSolutions
            bitnum += 1
        if len(solutions) == 0:
            break

    bitstreams = json.dumps(bitstreams, indent=2)
    msg(bitstreams, file=resultsFile)

    sps = set()
    for sp in sitePins:
        s = device.getSite(sp.split('/')[0])
        s = str(s.getSiteTypeEnum()) + "-" + sp.split('/')[-1]
        sps.add(s)
    sps = list(sps)
    sps.sort()
    msg("\nSite pins that need to be supported:")
    msg(json.dumps(list(sps), indent=2))

#####################################################################################################################

if __name__ == "__main__":
    main()