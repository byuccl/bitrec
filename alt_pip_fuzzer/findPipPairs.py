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

jpype.startJVM(classpath=["../fuzzer/rapidwright-2021.2.0-standalone-lin64.jar"])

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
    """
    Build list of PPIPs (always-on or pullup PIPs)

    Parameters
    ----------
    device : com.xilinx.rapidwright.device.Device
        The RW device object

    Returns
    -------
    ( ppipNames, ppipTypes)
        List of PPIP names and list of PPIP types ("always"=always-on, "default"=pullup)
    """
    ppipNames = []
    ppipTypes = []
    # Get arbitrary tile of this type
    tile = getTileOfType(device, "INT_L")
    # Get all the PIPs in the tile
    pips = tile.getPIPs()
    if args.verbose:
        msg(f"In getPPIPs - tile is: {tile}")
        msg(f"  There are {len(pips)} pips in it.")
    for p in pips:
        sp = str(p)
        # Check for permanent pips
        onlyDriver = p.getEndNode().getAllUphillPIPs()
        if len(onlyDriver) == 0:
            # The PPIP of interest by definition is a driver of its endNode
            msg("INTERNAL ERROR: {p}")
        # A PPIP is a PIP which is the ONLY driver of its downhill node (endNode)
        elif len(onlyDriver) == 1:
            ppipNames.append(getPpipName(sp))
            ppipTypes.append("always")
        # Check for pullup pips ("DEFAULT")
        # In series 7 these seem to have VCC_WIRE in their name
        if "VCC_WIRE" in sp:
            ppipNames.append(getPpipName(sp))
            ppipTypes.append("default")
    return ppipNames, ppipTypes

####################################################################################################

def is_valid_SP(SP,direction,N):
    """
    Determine if a site pin found can be used for one end of a net to solve for a PIP.

    Reasons why it might not be suitable include: 
    1. SP is None
    2. SP is wrong direction (e.g. must be site output pin when searching uphill)
    3. SP is on wrong kind of site.

    The original bitrec for this routine code by Corey Simpson was fairly restrictive.  
        1.  The only valid site types were SLICEL or TIEOFF sites unless the tile type whose PIPs
            were being solved for was not an interconnect tile.  
            In that case, sites from that tile type could be used.
        2.  Site pins named SR or CE could not be used.
    The net result is this code would only solve for part of the pips (3,626 out of ~3,730) (104 unsolved).

    Other variations:
        Sites allowed: add SLICEM and BUFHCE to list
        Site pins allowed: cannot use SR or CE
            Solves for all but 32 PIPs
        
        Sites allowed: add SLICEM and BUFHCE to list
        Site pins allowed: allow all
            Solves for 100% of PIPs.

    Parameters
    ----------
    SP : Device.SitePin 
        Candidate site pin.
    direction : str
        "UP" or "DOWN".
    N : Device.Node
        Node site pin is tied to.

    Returns
    -------
    int
        1 = Success
    """
    global banned_pin_list, args, tile_type
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

    # A first step was to allow SLICEM pins that are the same as SLICEL pins
    # This solved for a bunch more PIPs (but not all)
    #elif ST == "SLICEM" and SP.getPinName() not in allowedSLICEMpins:
    #    return 0
    # But later, to get all PIPs to solve, we opened it up to the site types below
    elif ST not in ["SLICEL", "SLICEM", "TIEOFF", "BUFHCE"] and TT != tile_type :
    #elif ST not in ["SLICEL", "TIEOFF"] and TT != tile_type :
        return 0
    if str(SP).split("/")[-1] in banned_pin_list:
        return 0
    
    # Finally, cannot use a site pin from a site that is already providing a site pin to another net
    #if str(S) in used_sites:
    #    return 0
    return 1

####################################################################################################

def traceUpDn(pip, solutions, dir, stack, indnt, depth):
    """
    The depth first search to find uphill or downhill paths.

    Each path found is either from the PIP uphill to a source site pin or 
    from the PIP downhill to a sink site pin.  
    The 'dir' parameter controls the direction searched.

    Parameters
    ----------
    pip : com.xilinx.rapidwright.device.PIP
        The PIP of interest
    solutions : [ [ com.xilinx.rapidwright.device.PIP, ... ] ]
        A list where solutions are added
    dir : str
        "UP" or "DOWN"
    stack : [ com.xilinx.rapidwright.device.PIP, ... ] 
        A list showing history of PIPs visited (a list of PIPs).  Used in recursive search via pushing and popping.
    indnt : str
        Prefix for the line to get indentation to help show nesting
    depth : int
        How deep to go in the search
    Returns
    -------
    Nothing at all
    """

    # Ignore bidirectional PIPs
    if "<<->>" in str(pip):
        return
    # Have we looped back on ourselves in our search?
    elif pip in stack:
        if args.verbose:
            errmsg(f"Loop found: {pip} {depth}   {stack}   ")
            pass
        return

    # Add current PIP to stack
    stack.append(pip)

    pipsToFollow = []
    # Build list of PIPs that branch from 'pip' that we need to search
    if dir == "UP":
        n = pip.getStartNode()     # Get uphill node
        if n:
            pipsToFollow = n.getAllUphillPIPs()   # Get list of pips to follow
    else:
        n = pip.getEndNode()       # Get downhill node
        if n:
            pipsToFollow = n.getAllDownhillPIPs()   # Get list of pips to follow
    
    # Some PIPs in the Vivado data model have no node on either input or output, return if found one
    if not n:
        stack.pop()
        return
    

    # Is there a site pin attached to this node that is the right direction and 
    # tied to the right type of site and pin?
    sp = n.getSitePin()
    if is_valid_SP(sp, dir, n):
        # Found a valid site pin so this is a solution.  Add a copy of it to list of solutions.
        # But, keep going below since we want to enumerate ALL possible solutions.
        solutions.append(stack[:])
    else:
        sp = None

    # This is the code that prints the indented list showing PIPs visited
    if args.verbose:
        printPip(pip, f"{indnt}{len(stack)}: ", dir)

    # If we haven't gone too deep, do recursive calls on PIPs in pipsToFollow
    depth -=1
    if depth > 0:
        for p in pipsToFollow:
            traceUpDn(p, solutions, dir, stack, indnt+'  ', depth)

    stack.pop()
    
    # On completion nothing is returned but the 'solutions' list will contain all the solutions found.

######################################################################################

def lsort(e):
    """
    Helper comparison function for sorting below.
    """
    return len(e)

######################################################################################

def areDisjointPaths(patha, pathb, pipa, pipb, tilea, tileb):
    """
    Check if two lists of pips are disjoint

    Parameters
    ----------
    patha : [ [pip1Name, pip2Name, ...], [pip3Name, pip4Name, ...], ...]
        List of paths (lists of pip string names)
    pathb : [ [pip1Name, pip2Name, ...], [pip3Name, pip4Name, ...], ...]
        List of paths (lists of pip string names)
    pipa: com.xilinx.rapidwright.device.PIP
        PIP of interest #0
    pipb: com.xilinx.rapidwright.device.PIP
        PIP of interest #1
    tilea: com.xilinx.rapidwright.device.Tile
        Tile where PIP of interest #0 is from
    tileb: com.xilinx.rapidwright.device.Tile
        Tile where PIP of interest #1 is from
    Returns
    -------
    Boolean
        Whether they are disjoint (True) or not (False)
    """

    assert getPpipName(pipa) == getPpipName(pipb)

    # Convert the paths to sets to be able to use set operations
    patha = set(patha)
    pathb = set(pathb)

    # Outright overlap is not allowed so intersect the sets to see if anything is in common
    if len(patha.intersection(pathb)) > 0:
        return False

    # Check origin tiles for the pip of interest for tile-independent overlap
    # First, get all the PIPs in the origin tiles (the tiles where the PIPs of interest are)
    spatha = { getPpipName(p) for p in patha if getTileName(p) == getTileName(tilea)}
    spathb = { getPpipName(p) for p in pathb if getTileName(p) == getTileName(tileb)}
    # Now remove the pips of interest from the lists.  What is left are the PIPs in 
    # the original tiles of the PIPs of interest.  We call these tile-independent PIPs.
    spatha.remove(getPpipName(pipa))
    spathb.remove(getPpipName(pipb))

    # Tile-independent PIPs should not be in common - that would mean the PIPs of interest are not
    # alone in their tiles and therefore there would be bit pollution.
    # But, these tile-independent PIPs name are actually OK if they are PPIPs.
    for p in spatha.intersection(spathb):  # Are there any collisions?
        if p not in ppipNames:  # If not PPIP then a problem
            return False

    # All tests passed so OK
    return True

def findDisjointPairs(solution):
    """
    Generate all possible disjoint pairs of solutions

    Parameters
    ----------
    solution : [ [ com.xilinx.rapidwright.Device.PIP, ...], [ com.xilinx.rapidwright.Device.PIP, ...], ... ]
        List of paths previously found, each path being a list of PIP names 
        leading from a pin to the PIP of interest (or the other way around).
    Returns
    -------
    [ ( [PIPName1, PIPName2], [PIPName3, PIPName4] ), ( [PIPName5], [PIPName6]), ...]
        List of pairs of paths (strings) where each pair's two paths are disjoint.
    """
    ret = []
    sol = []

    # For large lists of uphill or downhill paths, cut them back to a max length, 
    # otherwise the number of pairs to check becomes infeasible,
    # especially true since this routine enumerates ALL pairs of disjoint solutions.
    maxLen = 100  # This value somewhat arbitrarily chosen.
    for i in range(2):
        if len(solution[i]) < maxLen:
            sol.append(solution[i])
        else:
            sol.append(solution[i][0:maxLen-1])

    # Build lists to help simplify the checking.  
    # Note there are pairs of everything since we are doing dual paths.
    origPip = [None, None]
    origTile = [None, None]
    origPathStringPIPNames = [[], []]
    trimmedPaths = [None, None]
    for i in range(2):    
        assert len(sol[i])>0
        assert len(sol[i][0])>0
        # Get a handle to the actual PIP of interest and the tile it is from
        origPip[i] = (sol[i][0][0])
        origTile[i] = origPip[i].getTile()
        # Convert from list of lists of PIPs to list of lists of string PIP names
        origPathStringPIPNames[i] = [ [str(p) for p in s] for s in sol[i]]

    # Take all pairwise combinations, one from each of the two solutions
    for path0 in origPathStringPIPNames[0]:
        for path1 in origPathStringPIPNames[1]:
            # Check if they are disjoint and add to solution if they are
            if areDisjointPaths(path0, path1, origPip[0], origPip[1], origTile[0], origTile[1]):
                ret.append( (path0, path1) )
    return ret

######################################################################################

def printPip(pip, hdr, dir, fout=sys.stdout):
    """
    Format (into a string) a PIP's name along with site pin if one is attached to PIP's node(s).  
    
    If pip is a string, convert to real PIP, then look up the node and site pin.

    Parameters
    ----------
    pip : str or com.xilinx.rapidwright.device.PIP
        The PIP to print out
    hdr : str
        Spacing for formatted printing
    dir : str
        "UP" or "DOWN"
    fout : file, optional
        File to print to, by default sys.stdout

    Returns
    -------
    str
        The name of the PIP and, optionally, the name of the site pin attached to the PIP
    """
    
    # Convert to real PIP object if needed.  
    if type(pip) == str:
        pip = device.getPIP(pip)

    s = f"{hdr}{pip}"

    # Mark PPIPs with a * at the end of the name
    if getPpipName(pip) in ppipNames:
        s += "*"
    
    # Check to see if this ties to a pin of the proper type/direction.
    # If so, add it.
    n = pip.getStartNode() if dir == "UP" else pip.getEndNode()
    sp = n.getSitePin()
    if is_valid_SP(sp, dir, n):
        s += f" (Site pin: {sp})"

    # Return string we have built
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
    """
    Build a final solution by finding a pair of uphill paths which are disjoint from a pair of downhill paths.

    Within each uphill path pair the two paths will already be disjoint from one another.  Just need to find
    such a pair that is disjoint with a downhill pair.

    Parameters
    ----------
    upairs : 
    [ 
        ( [PIPName1, PIPName2, ...], [PIPName3, PIPName4, ...] ), 
        (...), 
        ... 
    ]
        A list of the pairs of uphill paths to consider.
    dpairs : 
    [ 
        ( [PIPName1, PIPName2, ...], [PIPName3, PIPName4, ...] ), 
        (...), 
        ... 
    ]
        A list of the pairs of downhill paths to consider.
    
    Returns
    -------
    ( 
        ( [PIPName1, PIPName2, ...], [PIPName3, PIPName4, ...] ), 
        ( [PIPName1, PIPName2, ...], [PIPName3, PIPName4, ...] ) 
    )
        The 4-way solution pieces found.
    """
    u = [set(pr[0][1:]).union(set(pr[1][1:])) for pr in upairs]
    d = [set(pr[0][1:]).union(set(pr[1][1:])) for pr in dpairs]
    for i in range(len(u)):
        for j in range(len(d)):
            if u[i].isdisjoint(d[j]):
                return( upairs[i], dpairs[j] )    
    return None

######################################################################################

def processPIPs(device, pipName, depth, maxTries):
    """
    Try to solve repeatedly for a PIP by placing it in various tiles.

    Actually do it two tiles at a time (the same PIP in each tile).
    Try only 'maxTries' times before giving up.

    Parameters
    ----------
    device : com.xilinx.rapidwright.device.Device
        The RW device object
    pipName : str
        Name of PIP to solve for
    depth : int
        Max depth of search
    maxTries : int
        How many pairs of locations to try before giving up

    Returns
    -------
    int
        1 = Success, -1 = Failure, 0 = bidirectional PIP (not handled)
    """
    global tile_type
    
    if "<<->>" in pipName:
        errmsg(f"Cannot do bidirectional pips yet: {pipName}, ignoring this one.")
        return 0
    
    pip = device.getPIP(pipName)           # com.xilinx.rapidwright.device.PIP
    tt = pip.getTile().getTileTypeEnum()   # com.xilinx.rapidwright.device.TileTypeEnum
    tile_type = str(tt)

    # Make a list of tiles to try 
    pipsToTry   = [ ]
    # Get all the tiles of the right type
    tmp = device.getAllTiles()
    tmp = [t for t in tmp if t.getTileTypeEnum() == tt]
    # Grab some random tiles and put into pairs in tuples
    tmp = random.choices(tmp, k=maxTries*2)
    tiles = []
    for i in range(maxTries):
        tiles.append((tmp[i], tmp[i+maxTries]))

    # From PIP name and list of tiles to try, build tuples of PIP pairs in 'pipsToTry'
    # The result is 'n' 2-tuples of specific PIPs to try
    for  i,tile in enumerate(tiles):
        newPipName0 = str(tile[0]) + "/" + pipName.split("/")[1]
        newPipName1 = str(tile[1]) + "/" + pipName.split("/")[1]
        newPIP0 = device.getPIP(newPipName0)
        newPIP1 = device.getPIP(newPipName1)
        pipsToTry.append((newPIP0, newPIP1))
    
    # Try to solve each pair of PIPs until you get one that succeeds
    for p in pipsToTry:
        status = processPIP(device, p, depth) 
        if status == 1:
            return 1
        elif status == -1:
            continue
        else:
            errmsg(f"Unknown processPIP return status: {status}")
    # All failed so return fail
    return -1

def processPIP(device, pip, depth):
    """
    Given a pair of PIPs, look for a 4-way solution that is disjoint

    Parameters
    ----------
    device : com.xilinx.rapidwright.device.Device
        The RW device object
    pip : (com.xilinx.rapidwright.device.PIP, com.xilinx.rapidwright.device.PIP)
        Tuple of two pip locations to try
    depth : int
        Max depth of search

    Returns
    -------
    int
        1 = success, -1 = failure
    """
    pipNames = (str(pip[0]), str(pip[1]))
    
    # Search UP for each of the two PIPs
    # There will be 2 lists of uphill paths, one for each PIP
    usol=[[], []]
    for i in range(2):
        traceUpDn(pip[i], solutions=usol[i], dir="UP", stack=[], indnt='', depth=depth)

    # Search DOWN for each of the two PIPs
    # There will be 2 lists of downhill paths, one for each PIP
    dsol=[[], []]
    for i in range(2):
        traceUpDn(pip[i], solutions=dsol[i], dir="DN", stack=[], indnt='', depth=depth)

    # Check to see if there was a failure to find uphill or downhill paths.  Exit if so.
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
    
    if args.verbose:
        msg(f"Usol has ({len(usol[0])}, {len(usol[1])}) entries, searching for upairs")
    # Find lists of uphill pairs that are disjoint from each of the two 'usol' lists.
    upairs = findDisjointPairs(usol)
    if args.verbose:
        msg(f"  Found {len(upairs)} upairs")
    if len(upairs) == 0:
        # If desired, print out the common PIP is keeping this from solving
        if args.verbose:
            for i in range(2):
                upr = [{str(p) for p in s} for s in usol[i]]
                common = reduce(lambda x, y: x.intersection(y), upr)
                for p in pipNames:
                    common.discard(p)
                msg(f"    Common element(s) for pip[{i}] '{pipNames}': {common}", file=resultsFile)
        return -1

    if args.verbose:
        msg(f"Dsol has ({len(dsol[0])}, {len(dsol[1])}) entries, searching for dpairs")
    # Find lists of downhill pairs that are disjoint from each of the two 'dsol' lists.
    dpairs = findDisjointPairs(dsol)
    if args.verbose:
        msg(f"  Found {len(dpairs)} dpairs")
    if len(dpairs) == 0:
        # If desired, print out the common PIP is keeping this from solving
        if args.verbose:
            for i in range(2):
                dpr = [{str(p) for p in s} for s in dsol[i]]
                common = reduce(lambda x, y: x.intersection(y), dpr)
                for p in pipNames:
                    common.discard(p)
                msg(f"    Common element(s) for pip[{i}] '{pipNames}': {common}", file=resultsFile)
        return -1

    if args.verbose:
        printPairs(upairs, "UP")
        printPairs(dpairs, "DOWN")

    # Finally look for a 4 way solution.  
    # This is an uphill disjoint pair (upair) plus a downhill disjoint pair (dpair) which themselves are all
    # disjoint from one another.  
    finalSol = find4Way(upairs, dpairs)
    #msg("\n\n####################################################################################")
    if finalSol is None:
        msg(f"No 4 way solution found for {pip}")
        return -1
    else:
        uFinalPair = finalSol[0]
        dFinalPair = finalSol[1]

        if args.verbose:
            msg(f"\nFinal UP Pair:")
            printPair(uFinalPair, "UP")
            msg(f"\nFinal DOWN Pair:")
            printPair(dFinalPair, "DOWN")

        # There are two ways to combine the uphill/downhill pairs into final solutions since all 4 are mutually disjoint.
        # There may be reasons to want both, so print both.
        msg(f"PIPSolution1: {pip[0]}  {pip[1]}\n", file=resultsFile)
        printUDPair(uFinalPair[0], dFinalPair[0])
        printUDPair(uFinalPair[1], dFinalPair[1])

        msg(f"PIPSolution2: {pip[0]}  {pip[1]}\n", file=resultsFile)
        printUDPair(uFinalPair[0], dFinalPair[1])
        printUDPair(uFinalPair[1], dFinalPair[0])

        return 1

  
#################################################################################################################

def main():
    global device, args, allowedSLICEMpins, ppipNames, resultsFile, banned_pin_list


    parser = argparse.ArgumentParser()
    parser.add_argument('--family',default="artix7")         # Selects the FPGA architecture family
    parser.add_argument('--part',default="xc7a100ticsg324-1L")    # Selects the FPGA part
    parser.add_argument('--pip',default="INT_L_X52Y58/INT_L.SR1END_N3_3->>BYP_ALT0")
    parser.add_argument('--pipfile', default=None, help="File to read pip names from to process")
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument('--startdepth',default=3)
    parser.add_argument('--maxtries',default=5)
    parser.add_argument('--stdoutToFile', default=None)
    parser.add_argument('--resultsFile', default="./pipresults.txt")
    args = parser.parse_args()

    if args.stdoutToFile:
        sys.stdout = open(args.stdoutToFile, 'w')
    
    resultsFile = open(args.resultsFile, 'w')

    errmsg(f"\n[LOG] main, args = {args}")

    device, design = init_rapidwright(args.part)

    #The original pips_rapid.py code didn't allow SR or CE to be source or sink pins.
    # See docstring for is_valid_SP() for explanation of effects of this.
    # banned_pin_list = ["SR","CE"]
    banned_pin_list = []

    # Build list of ppips (always-on or pullup PIPs)
    ppipNames, ppipTypes = getPPipNames(device)
    if args.verbose:
        for p,t in zip(ppipNames, ppipTypes):
            msg(f"PPIP = {p} {t}")
    
    msg("PPIPS:", file=resultsFile)
    for p in ppipNames:
        msg(f"  {getPpipName(p)}", file=resultsFile)
    msg("", file=resultsFile)

    # Build list of allowable SLICEM pins
    # This is if you want to only allow connecting to SLICEM pins in is_valid_SP()
    # which are the same pins that exist on SLICEL's.
    # Using that instead of allowing all SLICEM pins causes some PIPs to not solve
    # since they only go to SLICEM-specific pins.
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

            # Commented out lines        
            if len(l) == 0 or l.startswith("%"):
                continue

            # Lines copied from Tcl files that start with ## 
            if l.startswith("## "):
                l = l.split(" ")[2]

            if getPpipName(l.strip()) not in ppipNames:
                pips.append(l.strip())
    
    # Try to find a solution pair for each pip in the "pips" list
    totSuccesses = 0
    totFailures = 0
    depth = int(args.startdepth)
    maxTries = int(args.maxtries)
    remainingPIPs = []
    while len(pips) > 0:
        msg(f"\n## Starting depth = {depth}\n", file=resultsFile)
        remainingPIPs = pips[:]
        successes = 0
        failures = 0
        biDirs = 0
        tot = len(pips)
        # Take a pass through all the pips
        for i,pipName in enumerate(pips):
            status = processPIPs(device, pipName, depth, maxTries)
            # Success
            if status == 1:
                remainingPIPs.remove(pipName)
                successes += 1
                errmsg(f"[{i} of {tot}]  Success on {getPpipName(pipName)}")
            # Failure
            elif status == -1:
                failures += 1
                errmsg(f"[{i} of {tot}]  Failure on {getPpipName(pipName)}")
            # Was a bidir
            elif status == 0:
                biDirs += 1
                errmsg(f"BiDir")
            else:
                errmsg(f"Unknown processPIPs return code: {status}")
        errmsg()
        # Print unsolved pips, calculate stats on how many solved
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

        # Ask if user wants to continue
        resp = ""
        while resp not in ['c', 'r', 'q']:
            resp = input(f"Depth was {depth}, (c)ontinue with higher depth, (r)epeat with same depth, (q)uit?  ")
            if resp in ['q']:
                break
            elif resp in ['c']:
                depth += 1
                break
            else:
                print("Try again....")

        if resp in ['q']:
            break

        pips = remainingPIPs
        print("")

    msg(f"Unsolved ({len(remainingPIPs)}):", file=resultsFile)
    for p in remainingPIPs:
        msg(f"{getPpipName(p)}", file=resultsFile)
    resultsFile.close()
    return


#####################################################################################################################

if __name__ == "__main__":
    main()