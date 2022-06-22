########################################################################################
# File: mypips.py
# Author: Brent Nelson
# Date: May 2022
# Description:
#  The routine pips_rapid.py/run_pip_generation() iterates on solving for PIPs and, 
#    after each iteration checks to see what PIPs remain "unsolved".   A PIP remains
#    unsolved (or ambiguated) if it doesn't appear in an .ft file or if it only
#    appears in tiles where other things are also turned on.
#  It became clear that no matter how many iterations you run it, some small 
#    subset (8) of the PIPs will never be fully disambiguated according to the
#    criteria.
#  One of the PIPs that is never solved for is: GFAN0->>BYP_ALT1.  There will never
#    be a case where it is the only thing in the tile.
#  This program investigates an alternative approach.  
#    - Given a PIP 'P', enumerate all the <=n hop ways to go upstream and get to 
#      a site pin.  Now do the same for downstream.  
#    - Now, find two uphill paths and two downhill paths that are all totally
#      disjoint from each other.
#    - The solution can then be uphill[0]/downhill[0]and uphill[1]/downhill[1], each of
#      which pass through pip P but which are otherwise disjoint. 
#    - Or, it could be uphill[0]/downhill[1]and uphill[1]/downhill[0], each of
#      which pass through pip P but which are otherwise disjoint. 
#    - Call this a 4-way solution.
#    - Create a tile with the first solution and a different file with the second.
#    - Since the only thing common between the two tiles is P, this should provide
#      enough info to completely solve for P.
#  
#  A side discovery is that for PIP: GFAN0->>BYP_ALT, there are only two ways out 
#     of the tile when going downhill.  And, one of those paths can only terminate 
#     at a SLICEM's input pin.  Thus, to find two downhill paths as above will require 
#     that SLICEM sites be allowed to be used (the code currently allows only SLICEL).
#  If allowing SLICEM sites, restricting the pins usable on them to the same pins 
#     usable on a SLICEL will avoid the DRC rules for LUTRAM and SRL's.  This code 
#     does that.
#
#  Another side discovery was that sometimes the original run_pip_generation() code
#     will end up using the same PIP in both its uphill and its downhill sub-nets 
#     (have observed it as through a bounce pip). This is unroutable and so wastes 
#     Vivado time.  This algorithm naturally avoids that problem based on the way 
#     it works..
#  TODO: is the logic sound - determine that.
#  TODO: Determine how well this works - is it able to solve for PIPs not otherwise
#        solvable or not otherwise solvable without many specimens?
#  TODO: Determine how many specimens (bitstreams) it requires compared to normal?
#  TODO: Measure speed of search - is the requirement to find all paths wthin a 
#        certain distance simply too slow?
########################################################################################



import jpype
import jpype.imports
from jpype.types import *
import sys
import argparse
import random
from functools import reduce
import datetime

jpype.startJVM(classpath=["rapidwright-2021.2.0-standalone-lin64.jar"])

from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim

def msg(s='', hdr='', end="\n", file=sys.stdout):
    print(f"{hdr}{str(s)}", end=end, file=file)

def errmsg(s='', hdr='', end="\n"):
#    print(f"{hdr}{str(s)}", file=sys.stderr, end=end)
#    msg(f"{hdr}{str(s)}", end=end)
    msg(s, hdr, file=sys.stderr, end=end)

def getTileOfType(device, ttype):
    for T in device.getAllTiles():
        if T.getTileTypeEnum().toString() == ttype:
            return T
    return None

def getPpipName(p):
    return str(p).split('.')[-1]

def getTileName(t):
    st = str(t)
    if "/" in st:
        return st.split('/')[0]
    else:
        return st

def init_rapidwright(part_name):
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)
    return (device,design)

def printSolution(dir, i, sol):
    msg(f"\n{dir} Solution #{i}:")
    for pip in sol:
        printPip(pip, "    ", dir)

def printSolutions(sol, dir, reverse):
    for i,s in enumerate(sol):
        if reverse:
            printSolution(dir,i+1,s[::-1])
        else:
            printSolution(dir,i+1,s)

#################################################################################################################

def getPPipNames(device):
    ppipNames = []
    ppipTypes = []
    tile = getTileOfType(device, "INT_L")
    pips = tile.getPIPs()
    if args.verbose:
        msg(f"In getPPIPs - tile is: {tile}")
        msg(f"  There are {len(pips)} pips in it.")
    for p in pips:
        sp = str(p)
        # Check for permanent pips
        uphill = p.getEndNode().getAllUphillPIPs()
        if len(uphill) == 0:
            msg("INTERNAL ERROR: {p}")
        elif len(uphill) == 1:
            ppipNames.append(getPpipName(sp))
            ppipTypes.append("always")
        # Check for pullup pips ("DEFAULT")
        if "VCC_WIRE" in sp:
            ppipNames.append(getPpipName(sp))
            ppipTypes.append("default")
    return ppipNames, ppipTypes

####################################################################################################

# Determine if a site pin found can be used for one end of a net to solve for a PIP
# See comments below for explanation on the rules used to determine this
def is_valid_SP(SP,direction,N):
    global used_sites, banned_pin_list, args, tile_type
    # Also need a list of nodes that are used to prevent path collisions

    # Is it actually not a site pin?
    if SP == None:
        return 0

    # Is it the right direction?  That is, if looking uphill it cannot be an inpin.
    if direction == "UP": 
        if SP.isInput():
            return 0
    else:
        if SP.isInput() == False:
            return 0

    # Next, check some family- and tile-specific rules
    S = SP.getSite()
    ST = str(S.getSiteTypeEnum())
    T = S.getTile()
    TT = str(T.getTileTypeEnum())
    # For anything other than 7 series (US/US+) and for which CTRL is in the net name:
    #    if the site pin is NOT from a SLICEL/SLICEM/TIEOFF site then can't use it.
    if "CTRL" in str(N) and "7" not in args.family:
        if ST not in ["SLICEL","TIEOFF","SLICEM"]:
            return 0

    # Next, CANNOT use a site pin if:
    #   the site is not either SLICEL or TIEOFF AND the site is in a different tile type than being solved for 
    # Put in a positive logic way (using DeMorgan's) you CAN use a site pin if:
    #   the site is either SLICEL or TIEOFF
    #      OR
    #   the site pin is from a tile of the same type being solved for
    # This means that when solving for INT_L/INT_R tiles, site pins must either be on TIEOFF sites (which are in INT tiles) or on SLICEL's.
    #    Corey said he did this to simplify obeying the DRC rules on what things can drive what other things.
    #    He said relaxing this rule would likely require handling a bunch of DRC checks.
    # This also means that if you are solving for a DSP_L tile then the site pin must also come from a DSP_L tile.
    # TODO: seems a bit strict - is it necessary?

    #elif ST == "SLICEM" and SP.getPinName() not in allowedSLICEMpins:
    #    return 0
    elif ST not in ["SLICEL", "SLICEM", "TIEOFF", "BUFHCE"] and TT != tile_type :
        return 0
    if str(SP).split("/")[-1] in banned_pin_list:
        return 0
    
    # Finally, cannot use a site pin from a site that is aready providing a site pin to another net
    if str(S) in used_sites:
        return 0
    return 1

####################################################################################################

def traceUpDn(pip, solutions, dir, stack, indnt, depth):

    if "<<->>" in str(pip):
        return
    elif pip in stack:
        if args.verbose:
            #errmsg(f"Loop found: {pip} {depth}   {stack}   ")
            pass
        return

    stack.append(pip)

    if dir == "UP":
        n = pip.getStartNode()
        if n:
            pipsToFollow = n.getAllUphillPIPs()
    else:
        n = pip.getEndNode()
        if n:
            pipsToFollow = n.getAllDownhillPIPs()
    
    if not n:
        stack.pop()
        return
    
    sp = n.getSitePin()
    if not is_valid_SP(sp, dir, n):
        sp = None
    else:
        # Found a solution, add a copy of it to list of solutions
        solutions.append(stack[:])

    if args.verbose:
        printPip(pip, f"{indnt}{len(stack)}: ", dir)

    depth -=1
    if depth > 0:
        for p in pipsToFollow:
            traceUpDn(p, solutions, dir, stack, indnt+'  ', depth)

    stack.pop()

######################################################################################

def lsort(e):
    return len(e)

######################################################################################

def areDisjointPaths(patha, pathb, pipa, pipb, tilea, tileb):
    """
    Check if two lists of pips are disjoint

    Parameters
    ----------
    a : [ PIP_type_
        _description_
    b : _type_
        _description_
    p : _type_
        _description_
    """

    assert getPpipName(pipa) == getPpipName(pipb)

    patha = set(patha)
    pathb = set(pathb)

    # Outright overlap is not allowed
    if len(patha.intersection(pathb)) > 0:
        return False

    # Check origin tiles for the pip of interest for tile-independent overlap
    spatha = { getPpipName(p) for p in patha if getTileName(p) == getTileName(tilea)}
    spathb = { getPpipName(p) for p in pathb if getTileName(p) == getTileName(tileb)}
    spatha.remove(getPpipName(pipa))
    spathb.remove(getPpipName(pipb))
    foo=1

    # These tile-independent PIPs name are OK only if they are PPIPs
    # This means they will collide in the sensitivity analysis
    # # But if they are PPIPs they don't contribute any bit pollution so it is OK
    for p in spatha.intersection(spathb):
        if p not in ppipNames:
            return False

    return True

def findDisjointPairs(solution, dir):
    """
    Generate list of disjoint pairs of solutions

    Parameters
    ----------
    sol : [ { pip1, pip2, ...}, { pip3, pip4, ...}, ... ]
        List of 
    dir : _type_
        _description_
    """
    ret = []

    sol = []

    for i in range(2):
        if len(solution[i]) < 100:
            sol.append(solution[i])
        else:
            sol.append(solution[i][0:99])


    origPip = [None, None]
    origTile = [None, None]
    origPaths = [None, None]
    trimmedPaths = [None, None]
    for i in range(2):    
        assert len(sol[i])>0
        assert len(sol[i][0])>0
        origPip[i] = (sol[i][0][0])
        origTile[i] = origPip[i].getTile()
        origPaths[i] = [ [str(p) for p in s] for s in sol[i]]

    for path0 in origPaths[0]:
        for path1 in origPaths[1]:
            # Now need to 
            if areDisjointPaths(path0, path1, origPip[0], origPip[1], origPip[0], origTile[1]):
                ret.append( (path0, path1) )
    return ret

######################################################################################

def printPip(pip, hdr, dir, fout=sys.stdout):
    global tile_type

    if type(pip) == str:
        pip = device.getPIP(pip)

    s = f"{hdr}{pip}"

    if getPpipName(pip) in ppipNames:
        s += "*"
    
    n = pip.getStartNode() if dir == "UP" else pip.getEndNode()
    sp = n.getSitePin()
    if is_valid_SP(sp, dir, n):
        s += f" (Site pin: {sp})"
    return s
  

######################################################################################



def printUDPair(u, d):
    a = u[::-1]
    b = d[:]
    for e in a:
        s = printPip(e, "    ", "UP", fout=resultsFile)
        s = s.replace("(Site pin:", "").replace(")", "")
        # Dump results to final file
        print(s, file=resultsFile)
    msg("--", file=resultsFile)
    #print("+", file=resultsFile)
    for e in b:
        s = printPip(e, "    ", "DOWN", fout=resultsFile)
        s = s.replace(" (Site pin:", "").replace(")", "")
        # Dump results to final file
        print(s, file=resultsFile)
    print("", file=resultsFile)


def printPair(pr, dir):
    if dir=="UP":
        a = pr[0][::-1]
        b = pr[1][::-1]
    else:
        a = pr[0]
        b = pr[1]
    for e in a:
        printPip(e, "    ", dir)
    msg()
    for e in b:
        printPip(e, "    ", dir)

def printPairs(pairs, dir):
    msg("\n##################################################\n")
    msg(f"{dir} Pairs:")
    for i,pr in enumerate(pairs):
        msg(f"Pair {i}:")
        printPair(pr, dir)
        if i > 999:
            msg(f"\nLength of pairs = {len(pairs)}, only printing first 1000.")
            break

######################################################################################

def find4Way(upairs, dpairs):
    u = [set(pr[0][1:]).union(set(pr[1][1:])) for pr in upairs]
    d = [set(pr[0][1:]).union(set(pr[1][1:])) for pr in dpairs]
    for i in range(len(u)):
        for j in range(len(d)):
            if u[i].isdisjoint(d[j]):
                return( upairs[i], dpairs[j] )    
    return None

######################################################################################

def processPIPs(device, pipName, depth, maxTries):
    global tile_type
    #msg(f"\nPIP Name: {pipName}")

    if "<<->>" in pipName:
        errmsg(f"Cannot do bidirectional pips yet: {pipName}, ignoring this one.")
        return 0
    
    pip = device.getPIP(pipName)
    tt = pip.getTile().getTileTypeEnum()
    tile_type = str(tt)

    # Make a list of tiles to try in
    # First, try the requested one
    pipsToTry   = [ ]
    # Now, add some more in case that fails
    tmp = device.getAllTiles()
    tmp = [t for t in tmp if t.getTileTypeEnum() == tt]
    # Get list pairs of random tiles
    tmp = random.choices(tmp, k=maxTries*2)
    tiles = []
    
    for i in range(maxTries):
        tiles.append((tmp[i], tmp[i+maxTries]))
    for  i,tile in enumerate(tiles):
        newPipName0 = str(tile[0]) + "/" + pipName.split("/")[1]
        newPipName1 = str(tile[1]) + "/" + pipName.split("/")[1]
        newPIP0 = device.getPIP(newPipName0)
        newPIP1 = device.getPIP(newPipName1)
        pipsToTry.append((newPIP0, newPIP1))
    
    for p in pipsToTry:
        #errmsg("^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        #errmsg(f"Trying: {p[0]} and {p[1]}")
        status = processPIP(device, p, depth) 
        if status == 1:
            # It worked, return it
            #errmsg("TrySuccess !!!")
            #errmsg("^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            return 1
        elif status == -1:
            #errmsg("TryFailure !!!")
            #errmsg("^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            pass
        elif status == 0:
            return 0
        else:
            errmsg(f"Unknown processPIP return status: {status}")
    return -1



def processPIP(device, pip, depth):
    global banned_pin_list, used_sites

    pipNames = (str(pip[0]), str(pip[1]))
    
    used_sites = []



    #msg("\n----------------------------------------------------------------")
    #msg("<<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>>")
    #msg(f"Doing PIP: {pip[0]}  {pip[1]}")
    #msg("<<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>>")
    #msg("----------------------------------------------------------------")

    #msg("Searching UP...")
    usol=[[], []]
    for i in range(2):
        traceUpDn(pip[i], solutions=usol[i], dir="UP", stack=[], indnt='', depth=depth)


    #msg("Searching DOWN...")
    dsol=[[], []]
    for i in range(2):
        traceUpDn(pip[i], solutions=dsol[i], dir="DN", stack=[], indnt='', depth=depth)

    for i in range(2):
        if len(usol[i]) == 0:
            if args.verbose:
                errmsg(f"  Empty usol[{i}] for PIP: {pip[0]}  {pip[1]}")
            return -1
        if len(dsol[i]) == 0:
            if args.verbose:
                errmsg(f"  Empty dsol[{i}] for PIP: {pip[0]}  {pip[1]}")
            return -1
    
        # Sort solutions from shortest to longest
        #msg("Sorting")
        usol[i].sort(key=lsort)
        dsol[i].sort(key=lsort)
    
        if args.verbose:
            msg("\n################################################################################")
            printSolutions(usol[i], "UP", reverse=True)
            msg("\n################################################################################")
            printSolutions(dsol[i], "DOWN", reverse=False)
    
    # Find lists of uphill pairs that are disjoint
    #msg(f"Usol has ({len(usol[0])}, {len(usol[1])}) entries, searching for upairs")
    upairs = findDisjointPairs(usol, "UP")
    #msg(f"  Found {len(upairs)} upairs")
    if len(upairs) == 0:
#        for i in range(2):
#            upr = [{str(p) for p in s} for s in usol[i]]
#            common = reduce(lambda x, y: x.intersection(y), upr)
#            for p in pipNames:
#                common.discard(p)
#            msg(f"    Common element(s) for pip[{i}] '{pipNames}': {common}", file=resultsFile)
        return -1

    # Repeat for downhill 
    #msg(f"Dsol has ({len(dsol[0])}, {len(dsol[1])}) entries, searching for dpairs")
    dpairs = findDisjointPairs(dsol, "DOWN")
    #msg(f"  Found {len(dpairs)} dpairs")
    if len(dpairs) == 0:
#        dpr = [{str(p) for p in s} for s in dsol]
#        common = reduce(lambda x, y: x.intersection(y), dpr)
#        common.remove(pipNames)
#        msg(f"    Common element(s) for pip '{pipNames}': {common}")
#        msg([[str(s) for s in sol] for sol in dsol])
        return -1

    if args.verbose:
        printPairs(upairs, "UP")
        printPairs(dpairs, "DOWN")

    # Finally look for a 4 way solution
    finalSol = find4Way(upairs, dpairs)
    #msg("\n\n####################################################################################")
    if finalSol is None:
        msg(f"No 4 way solution found for {pip}")
        return -1
    else:
        uFinalPair = finalSol[0]
        dFinalPair = finalSol[1]

        #msg(f"\nFinal UP Pair:")
        #printPair(uFinalPair, "UP")
        #msg(f"\nFinal DOWN Pair:")
        #printPair(dFinalPair, "DOWN")

        msg(f"\nFinal Solution #1:", file=resultsFile)
        msg(f"PIPSolution1: {pip[0]}  {pip[1]}\n", file=resultsFile)
        printUDPair(uFinalPair[0], dFinalPair[0])
        #msg("and ...", file=resultsFile)
        printUDPair(uFinalPair[1], dFinalPair[1])
        msg(f"\nFinal Solution #2:", file=resultsFile)
        msg(f"PIPSolution2: {pip[0]}  {pip[1]}\n", file=resultsFile)
        printUDPair(uFinalPair[0], dFinalPair[1])
        #msg("and ...", file=resultsFile)
        printUDPair(uFinalPair[1], dFinalPair[0])

    
        # Let's do a final sanity check
        #u0 = set([str(p) for p in uFinalPair[0][1:]])
        #u1 = set([str(p) for p in uFinalPair[1][1:]])
        #d0 = set([str(p) for p in dFinalPair[0][1:]])
        #d1 = set([str(p) for p in dFinalPair[1][1:]])
        #assert u0.isdisjoint(u1), f"Not disjoint: {u0.intersection(u1)}"
        #assert d0.isdisjoint(d1), f"Not disjoint: {d0.intersection(d1)}"

        #assert u0.isdisjoint(d0), f"Not disjoint: {u0.intersection(d0)}"
        #assert u1.isdisjoint(d0), f"Not disjoint: {u1.intersection(d0)}"
        #assert u0.isdisjoint(d1), f"Not disjoint: {u0.intersection(d1)}"
        #assert u1.isdisjoint(d1), f"Not disjoint: {u1.intersection(d1)}"
        return 1

  
#################################################################################################################

def main():
    global device, args, allowedSLICEMpins, ppipNames, resultsFile, banned_pin_list


    parser = argparse.ArgumentParser()
    parser.add_argument('--family',default="artix7")         # Selects the FPGA architecture family
    parser.add_argument('--part',default="xc7a100ticsg324-1L")    # Selects the FPGA part
    #parser.add_argument('--pip',default="INT_L_X50Y102/INT_L.GFAN0->>BYP_ALT1")
    parser.add_argument('--pip',default="INT_L_X52Y58/INT_L.SR1END_N3_3->>BYP_ALT0")
    #parser.add_argument('--pip',default="INT_L_X40Y5/INT_L.BYP_BOUNCE3->>IMUX_L23")
    parser.add_argument('--pipfile', default=None)
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument('--startdepth',default=3)
    parser.add_argument('--maxtries',default=5)
    parser.add_argument('--toFile', default=None)
    parser.add_argument('--resultsFile', default="./pipresults.txt")
    args = parser.parse_args()

    if args.toFile:
        sys.stdout = open(args.toFile, 'w')
    
    resultsFile = open(args.resultsFile, 'w')

    errmsg(f"\n[LOG] main, args = {args}")

    device, design = init_rapidwright(args.part)

    #banned_pin_list = ["SR","CE"]
    banned_pin_list = []

    ppipNames, ppipTypes = getPPipNames(device)
    if args.verbose:
        for i, p in enumerate(ppipNames):
            msg(f"PPIP = {p} {ppipTypes[i]}")
    
    msg("PPIPS:", file=resultsFile)
    for p in ppipNames:
        msg(f"  {getPpipName(p)}", file=resultsFile)
    msg("", file=resultsFile)

    # Build list of allowable SLICEM pins
    slice = getTileOfType(device, "CLBLL_L").getSites()[0]
    assert str(slice.getSiteTypeEnum()) == "SLICEL"
    allowedSLICEMpins = [slice.getPinName(i) for i in range(slice.getSitePinCount())]

    # Get pips to process
    if args.pipfile is None:
        pips = [ args.pip ]
    else:
        pips = []
        with open(args.pipfile) as f:
            lines = f.readlines()
        for l in lines:
            l = l.strip()

            if len(l) == 0 or l.startswith("%"):
                continue

            if l.startswith("## "):
          
                l = l.split(" ")[2]

            if getPpipName(l.strip()) not in ppipNames:
                pips.append(l.strip())
    
    totSuccesses = 0
    totFailures = 0
    depth = int(args.startdepth)
    maxTries = int(args.maxtries)
    while len(pips) > 0:
        msg(f"\n## Starting depth = {depth}\n", file=resultsFile)
        remainingPIPs = pips[:]
        successes = 0
        failures = 0
        biDirs = 0
        tot = len(pips)
        for i,pipName in enumerate(pips):
            status = processPIPs(device, pipName, depth, maxTries)
            if status == 1:
                remainingPIPs.remove(pipName)
                successes += 1
                errmsg(f"[{i} of {tot}]  Success on {getPpipName(pipName)}")
            elif status == -1:
                failures += 1
                errmsg(f"[{i} of {tot}]  Failure on {getPpipName(pipName)}")
            elif status == 0:
                biDirs += 1
                errmsg(f"BiDir")
            else:
                errmsg(f"Unknown processPIPs return code: {status}")
        errmsg()
        msg("Here are the unsolved PIPs:")
        for p in remainingPIPs:
            msg(f"    {p}")
        errmsg()
        errmsg(f"Time is: {datetime.datetime.now()}")
        errmsg(f"Depth was: {depth}")
        errmsg(f"Successes = {successes}, failures = {failures}, biDirs = {biDirs}")
        totSuccesses += successes
        totFailures = failures
        errmsg(f"Total Successes = {totSuccesses}, total failures = {totFailures}")
        errmsg()


        resp = ""
        while resp not in ['Y', 'y', 'N', 'n']:
            resp = input(f"Depth was {depth}, continue the program with depth of {depth+1}? [y/n]")
            if resp in ['N', 'n']:
                msg("Unsolved:", file=resultsFile)
                for p in remainingPIPs:
                    msg(f"{getPpipName(p)}", file=resultsFile)
                resultsFile.close()
                return
            elif resp in ['Y', 'y']:
                pass
            else:
                print("Try again....")

        pips = remainingPIPs
        depth += 1
    
    msg("Unsolved:", file=resultsFile)
    resultsFile.close()

#####################################################################################################################

if __name__ == "__main__":
    main()