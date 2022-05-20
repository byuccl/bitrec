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
    print(f"{hdr}{str(s)}", file=sys.stdout, end=end)

def errmsg(s, hdr='', end="\n"):
    msg(s, hdr, file=sys.stderr, end=end)

def getTileOfType(device, tile_type):
    for T in device.getAllTiles():
        if T.getTileTypeEnum().toString() == tile_type:
            return T
    return None


def init_rapidwright(part_name):
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)
    return (device,design)

def printSolution(sol):
    msg(sol)

####################################################################################################

# Determine if a site pin found can be used for one end of a net to solve for a PIP
# See comments below for explanation on the rules used to determine this
def is_valid_SP(SP,direction,N, tile_type):
    global used_sites, banned_pin_list, args
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

def traceUpDn(pip, tile_type, dir, stack, indnt, depth):
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
    if not is_valid_SP(sp, dir, n, tile_type):
        sp = None

    if args.verbose:
        msg(f"{pip}", hdr=f"{indnt}{len(stack)}: ", end='')
        if sp:
            msg(f"    Site pin: {sp}")
        else:
            msg()
        #msg(f"{[str(p) for p in pipsToFollow]}")

    depth -=1
    if depth > 0:
        for p in pipsToFollow:
            traceUpDn(p, tile_type, dir, stack, indnt+'  ', depth)

    stack.pop()

######################################################################################

def processPIP(device, pipName, lodepth, hidepth):
    global banned_pin_list, used_sites

    banned_pin_list = []
    used_sites = []

    pip = device.getPIP(pipName)
    tile_type = str(pip.getTile().getTileTypeEnum())

    if pip:
        msg("\n----------------------------------------------------------------")
        msg("<<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>>")
        msg(f"Doing PIP: {pip}")
        msg("<<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>> <<>>")
        msg("----------------------------------------------------------------")
    else:
        errmsg(f"No such pip: {pip}, ignoring")
        return

    msg("\n############################################")
    msg("Searching UP...")
    msg("############################################")
    sol = traceUpDn(pip, tile_type=tile_type, dir="UP", stack=[], indnt='', depth=3)
    msg("\n############################################")
    msg("Searching DOWN...")
    msg("############################################")
    sol = traceUpDn(pip, tile_type=tile_type, dir="DOWN", stack=[], indnt='', depth=3)
    printSolution(sol)

#################################################################################################################

def main():
    global args, allowedSLICEMpins

    parser = argparse.ArgumentParser()
    parser.add_argument('--family',default="artix7")         # Selects the FPGA architecture family
    parser.add_argument('--part',default="xc7a100ticsg324-1L")    # Selects the FPGA part
    parser.add_argument('--pip',default="INT_L_X50Y102/INT_L.GFAN0->>BYP_ALT1")
    parser.add_argument('--pipfile')
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument('--lodepth',default=4)
    parser.add_argument('--hidepth',default=5)
    args = parser.parse_args()

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

#####################################################################################################################

if __name__ == "__main__":
    main()