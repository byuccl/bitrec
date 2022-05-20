import jpype
import jpype.imports
from jpype.types import *
import sys
import argparse

jpype.startJVM(classpath=["rapidwright-2021.2.0-standalone-lin64.jar"])

from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim

def msg(s='', hdr='', file=sys.stdout, end="\n"):
    print(f"{hdr}{str(s)}", file=file, end=end)

def errmsg(s='', hdr='', end="\n"):
    msg(s, hdr, file=sys.stderr, end=end)

def getTileOfType(device, ttype):
    for T in device.getAllTiles():
        if T.getTileTypeEnum().toString() == ttype:
            return T
    return None


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

    elif ST == "SLICEM" and SP.getPinName() not in allowedSLICEMpins:
        return 0
    elif ST not in ["SLICEL", "SLICEM", "TIEOFF"] and TT != tile_type :
        return 0
    if str(SP).split("/")[-1] in banned_pin_list:
        return 0
    
    # Finally, cannot use a site pin from a site that is aready providing a site pin to another net
    if str(S) in used_sites:
        return 0
    return 1

####################################################################################################

def traceUpDn(pip, solutions, dir, stack, indnt, depth):
    stack.append(pip)

    if dir == "UP":
        n = pip.getStartNode()
        w = pip.getStartWire()
        pipsToFollow = n.getAllUphillPIPs()
    else:
        n = pip.getEndNode()
        w = pip.getEndWire()
        pipsToFollow = n.getAllDownhillPIPs()
    
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

def findDisjointPairs(sol):
    ret = []

    tmp = [set(s[1:]) for s in sol]
    for i in range(len(tmp)):
        for j in range(i,len(tmp)):
            if tmp[i].isdisjoint(tmp[j]):
                ret.append( (sol[i], sol[j]) )
    return ret

######################################################################################

def printPip(pip, hdr, dir):
    global tile_type
    msg(f"{hdr}{pip}", end='')
    
    n = pip.getStartNode() if dir == "UP" else pip.getEndNode()
    sp = n.getSitePin()
    if is_valid_SP(sp, dir, n):
        msg(f" (Site pin: {sp})")
    else:
        msg()
  

######################################################################################

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

def processPIP(device, pipName, lodepth, hidepth):
    global banned_pin_list, used_sites, tile_type

    banned_pin_list = []
    used_sites = []

    pip = device.getPIP(pipName)
    tile_type = str(pip.getTile().getTileTypeEnum())

    if pip:
        msg("\n----------------------------------------------------------------")
        msg("<<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>>")
        msg(f"Doing PIP: {pip}")
        errmsg(f"  Doing PIP: {pip}")
        msg("<<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>>")
        msg("----------------------------------------------------------------")
    else:
        errmsg(f"No such pip: {pip}, ignoring")
        return

    if args.verbose:
        msg("\n############################################")
        msg("Searching UP...")
        msg("############################################")
    usol = []
    traceUpDn(pip, solutions=usol, dir="UP", stack=[], indnt='', depth=4)

    if args.verbose:
        msg("\n############################################")
        msg("Searching DOWN...")
        msg("############################################")
    dsol = []
    traceUpDn(pip, solutions=dsol, dir="DOWN", stack=[], indnt='', depth=4)

    # Sort solutions from shortest to longest
    usol.sort(key=lsort)
    dsol.sort(key=lsort)

    if args.verbose:
        msg("\n################################################################################")
        printSolutions(usol, "UP", reverse=True)
        msg("\n################################################################################")
        printSolutions(dsol, "DOWN", reverse=False)

    # Find lists of uphill pairs that are disjoint
    upairs = findDisjointPairs(usol)
    # Repeat for downhill 
    dpairs = findDisjointPairs(dsol)

    if args.verbose:
        printPairs(upairs, "UP")
        printPairs(dpairs, "DOWN")

    # Finally look for a 4 way solution
    finalSol = find4Way(upairs, dpairs)
    msg("\n\n####################################################################################")
    if finalSol is None:
        msg(f"No 4 way solution found for {pip}")
    else:
        uFinalPair = finalSol[0]
        dFinalPair = finalSol[1]

        msg(f"\nFinal UP Pair:")
        printPair(uFinalPair, "UP")
        msg(f"\nFinal DOWN Pair:")
        printPair(dFinalPair, "DOWN")
    
        # Let's do a final sanity check
        u0 = set([str(p) for p in uFinalPair[0][1:]])
        u1 = set([str(p) for p in uFinalPair[1][1:]])
        d0 = set([str(p) for p in dFinalPair[0][1:]])
        d1 = set([str(p) for p in dFinalPair[1][1:]])
        assert u0.isdisjoint(u1), f"Not disjoint: {u0.intersection(u1)}"
        assert d0.isdisjoint(d1), f"Not disjoint: {d0.intersection(d1)}"

        assert u0.isdisjoint(d0), f"Not disjoint: {u0.intersection(d0)}"
        assert u1.isdisjoint(d0), f"Not disjoint: {u1.intersection(d0)}"
        assert u0.isdisjoint(d1), f"Not disjoint: {u0.intersection(d1)}"
        assert u1.isdisjoint(d1), f"Not disjoint: {u1.intersection(d1)}"


    
#################################################################################################################

def main():
    global device, args, allowedSLICEMpins


    parser = argparse.ArgumentParser()
    parser.add_argument('--family',default="artix7")         # Selects the FPGA architecture family
    parser.add_argument('--part',default="xc7a100ticsg324-1L")    # Selects the FPGA part
    parser.add_argument('--pip',default="INT_L_X50Y102/INT_L.GFAN0->>BYP_ALT1")
    parser.add_argument('--pipfile')
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument('--lodepth',default=4)
    parser.add_argument('--hidepth',default=5)
    args = parser.parse_args()

    errmsg(f"\n[LOG] main, args = {args}")

    device, design = init_rapidwright(args.part)

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
            if l.startswith("## "):
                l = l.split(" ")[2]
            pips.append(l.strip())

    for pipName in pips:
        processPIP(device, pipName, args.lodepth, args.hidepth)
    errmsg()

#####################################################################################################################

if __name__ == "__main__":
    main()