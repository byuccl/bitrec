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


import random
import re
import json
import os
import os.path
from os import path
import datetime
import jpype
import jpype.imports
from jpype.types import *
from data_generator import *
from data_analysis import parse_feature_file
#jpype.startJVM(classpath=["rapidwright-2021.1.1-standalone-lin64.jar"])


from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim

def init_rapidwright(part_name):
    """
    Set device and create design.

    Parameters
    ----------
    part_name : str
        Full name of part.
    """
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)


def get_placement_dict(primitive_dict):
    """
    Create dictionary mappings BELs to the primitives that can be placed on them.

    Done by creating a cell in a design for every primitive type and querying RW for legal placements.
    Data structure is then inverted to map bels -> primitive types.

    Parameters
    ----------
    primitive_dict : list of str
    
    Returns
    -------
    bel_prim : 
        dict of { (siteType, belType) : [primitiveName, ...] }.
        Ex: { ('SLICEL', 'A5FF'): ['FDCE', 'FDPE', 'FDRE', 'FDSE'], ('BUFG', 'BUFG'): ['BUFG'] }.
    """

    global device,design
    # Remove AND2B1L from primitive dictionary
    # TODO: why?  Must be something special about it (in a bad way)...
    primitive_dict.pop("AND2B1L",None)
    #print(primitive_dict.keys())
    placement_map = {}
    print(f"UNISIM values: {Unisim.values}")
    for x in Unisim.values():
        # If x in primitive json - Unisim.getTransform(series) isn't working
        if str(x) in primitive_dict:
            try:
                a = design.createCell("tmp"+str(x),x)
                # Get Java Map<SiteTypeEnum,Set<String>> for cell
                placement = a.getCompatiblePlacements()
                tmp_dict = {}
                for k in placement:
                    tmp_dict[str(k)] = list(str(v) for v in placement[k])
                placement_map[str(x)] = tmp_dict
                design.removeCell(a)
            except:
                continue


    # Need to invert placement_map for bel-> primitive
    bel_prim = {}
    for P in placement_map:
        for ST in placement_map[P]:
            for B in placement_map[P][ST]:
                if (ST,B) not in bel_prim:
                    bel_prim[(ST,B)] = [P]
                else:
                    bel_prim[(ST,B)] += [P]
    #for x in bel_prim:
    #    print(x,bel_prim[x])
    return bel_prim


def is_ultrascale_tieoff(N):
    global args
    if "7" not in args.family:
        s,n = str(N).rsplit("/",1)
        if n == "VCC_WIRE":
            return s + ".US.HARD1"
        elif n == "GND_WIRE":
            return s + ".US.HARD0"
        else:
            return 0
    else:
        return 0

def is_valid_SP(SP,direction,N):
    """
    Determine if a site pin found can be used for one end of a net to solve for a PIP.

    Reasons why it might not be suitable: is None, is wrong direction, is on wrong kind of site.

    Parameters
    ----------
    SP : Device.SitePin 
        Candidate site pin.
    direction : str
        Direction going.
    N : Device.Node
        Node site pin is tied to.

    Returns
    -------
    int
        1 = Success
    """
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
    elif ST not in ["SLICEL","TIEOFF"] and TT != tile_type :
        return 0
    if str(SP).split("/")[-1] in banned_pin_list:
        return 0
    
    # Finally, cannot use a site pin from a site that is aready providing a site pin to another net
    if str(S) in used_sites:
        return 0
    return 1


def dfs(P, direction, path, depth, max_depth, banned_pips):
    """
    Perform depth first search starting from a PIP.

    This is a basic depth first search (depth-limited by max_depth) which goes either 
      uphill (toward a source) or downhill (toward a sink).
    When a node (N) is encountered which ties to a site pin, the site pin is checked to see if it is 
      a valid site pin (going the right direction, not used, not in a used site, a few other edge case checks).
    If it is a valid site pin then success is declared - one end of the wire has been determined.
    Otherwise the search continues until max_depth is reached or a valid site pin is found.

    Parameters
    ----------
    P : Device.PIP
        Starting PIP.
    direction : str
        "UP" or "DOWN""
    path : [ str ]]
        Accumulated path as search progresses.
    depth : int
        How far deep we are.
    max_depth : int
        How far to go.
    banned_pips : [ PIP ]
        ???

    Returns
    -------
    [ [ str(Device.Node), ... ], Device.SitePin ]
        Returns path found and site pin found.
    """
    
    global ft
    if depth > max_depth:
        return None

    if direction == "UP":
        N = P.getStartNode()
    else:
        N = P.getEndNode()

    sP = str(P)
    sN = str(N)
    if N is None or N.isInvalidNode():
        return None
    else:
        path.append(str(N))
        SP = N.getSitePin()
        sSP = str(SP)
        #print("\tSP:",SP)
        if is_valid_SP(SP,direction,N):
            return [path,N.getSitePin()]
        u_tieoff = is_ultrascale_tieoff(N)
        if u_tieoff != 0: # Check if node is a hard0/hard1 in ultrascale
            return [path,u_tieoff]
        if direction == "UP":
            pips = N.getAllUphillPIPs()
        else:
            pips = N.getAllDownhillPIPs()
        #print("\tNODES",list(str(x) for x in nodes),file=ft)
        #BEN Comment out next line to get repeatable behavior
        random.shuffle(pips)
        if len(banned_pips) > 0:
            for PP in pips:
                sPP = str(PP)
                p_simple = str(PP).split("/")[-1]
                if p_simple not in banned_pips:
                    #print("\t\tCHOOSE:",P,PP,p_simple,direction,path)
                    #print("\t\t\t",len(banned_pips),banned_pips,pips)
                    ret = dfs(PP,direction,path.copy(),depth+1,max_depth,[])
                    if ret is not None:
                        return ret
        else:
           for PP in pips:
                sPP = str(PP)
                ret = dfs(PP,direction,path.copy(),depth+1,max_depth,[])
                if ret is not None:
                    return ret 
    return None


def dfs_main(P, direction, max_depth):
    """
    Set up and run DFS.

    Parameters
    ----------
    P : Device.PIP
        Starting PIP.
    direction : str
        "UP" or "DOWN".
    max_depth : int
        Max depth to search for a suitable SitePin.

    Returns
    -------
    [ [ str(Device.Node), ... ], Device.SitePin ]
        Returns path found and site pin found.
    """
    global ft, pip_dict

    banned_pips = []
    p_simple = str(P).rsplit("/")[-1]
    if p_simple in pip_dict:
        pd = pip_dict[p_simple]
        for ps in pd:
            for p in pd[ps]:
                p_name = p.rsplit(":")[-1]
                banned_pips.append(p_name)
    print("      FINAL BAN", P, banned_pips)
    return dfs(P, direction, [], 0, max_depth, banned_pips)


def get_rapid_tile_list(tile_type):
    """
    Return a list of all the tiles in the current device which are of the specified type.

    Parameters
    ----------
    tile_type : str
        Example: "INT_L"

    Returns
    -------
    [ Device.Tile ]
        List of tile objects.
    """
    tile_list = []
    for T in device.getAllTiles():
        if T.getTileTypeEnum().toString() == tile_type:
            tile_list.append(T)
    return tile_list


def create_and_place(primitive,site, site_type,bel):
    """
    Write commands to create and place a cell in the TCL file.

    Parameters
    ----------
    primitive : str
        Ex: "LUT6"
    site : str
        Ex: "SLICE_X12Y30"
    site_type : str
        Ex: "SLICEL"
    bel : str
        "B6LUT""
    """
    if bel == "PHY":
        cell_name = site+"."+bel+"."+primitive
        loc = site+"/"+bel
        # Just create the PHY cell - don't place it - it gets placed later 
        # TODO: why the different treatment?
        print("create_cell -reference",primitive,cell_name,file=ft)
    else:
        cell_name = site+"."+bel+"."+primitive
        loc = site+"/"+bel
        # Create cell
        print("create_cell -reference",primitive,cell_name,file=ft)
        # Handle special case of SLICEM's
        if str(site_type) == "SLICEM":
            print("tcl_drc_lut_rams ",primitive, bel, "[get_sites",site,"]",file=ft) 
        # Place cell
        print("catch { set_property MANUAL_ROUTING",str(site_type),"[get_sites",site,"]}",file=ft)
        print("catch { place_cell",cell_name,loc,"}",file=ft)
        print("catch { reset_property MANUAL_ROUTING","[get_sites",site,"]}",file=ft)


def get_bel_of_pin(BP):
    """
    Get the BEL of a BEL pin.

    This is a recursive function.
    If the BEL for this BEL pin is a normal BEL (not a routing MUX) then return it.
    Otherwise search uphill or downhill as appropriate through routing BELs until you hit a real BEL.

    Parameters
    ----------
    BP : Device.BelPin
        The BEL pin of interest.

    Returns
    -------
    tuple of ( Device.BEL, BelPinName )
        BelPinName is of the form: "B6LUT/A6"
    """
    B = BP.getBEL()
    print("        GETTING BEL OF PIN:", BP)
    # A BEL which is a routing BEL will have a name of the form: "DOUTMUX(RBEL)"
    # Need to follow it through other routing muxes (upstream or downstream) until you hit a real "normal" BEL
    if "RBEL" in str(B):
        if BP.isInput():
            rbel_pins = B.getPins()
            for rbel_pin in rbel_pins:
                if rbel_pin.isOutput():
                    rbel_conns = rbel_pin.getSiteConns()
                    # TODO: not sure what the for loop buys us here...
                    for RBP in rbel_conns:
                        return get_bel_of_pin(RBP)
        else:  # Is output
            rbel_pins = B.getPins()
            for rbel_pin in rbel_pins:
                if rbel_pin.isInput():
                    rbel_conns = rbel_pin.getSiteConns()
                    for RBP in rbel_conns:
                        return get_bel_of_pin(RBP)
    else:
        # We already are at a real BEL so return it
        return B,str(BP).replace(".","/")

def get_placement(site_pin):
    """
    Determine what to place for this site pin

    Knowing the site pin we need to:
    1. Figure out a site_type that uses this pin
    2. Get the BEL pin tied to this site pin
    3. Handle a bunch of special cases
    4. Return a tuple summarizing what you have determined.

    Parameters
    ----------
    site_pin : Device.SitePin
        The site pin of interest.

    Returns
    -------
    A large tuple.  
    Ex: ("SLICE_X13Y37/B6LUT/A3", "LUT6", "SLICE_X13Y37", "SLICEL",    "B6LUT",    1)
            BP_sink               primitive     site      site_type       bel  is_bp
        
    """
    global primitive_map
    ff_regex = re.compile('([A-H]FF.?/CE)|([A-H]FF.?/SR)')

    if "HARD1" in str(site_pin):
        if "US" in str(site_pin):
            S = site_pin.split(".")[0]
            BP = S+".PHY.VCC/P"
            ST = "INT"
        else:
            S = site_pin.getSite()
            BP = str(S)+".PHY.VCC/P"
            ST = S.getSiteTypeEnum()
        #print(site_pin,S,ST,BP)
        return BP,"VCC",str(S),str(ST),"PHY",0
    elif "HARD0" in str(site_pin):
        if "US" in str(site_pin):
            S = site_pin.split(".")[0]
            BP = S+".PHY.GND/G"
            ST = "INT"
        else:
            S = site_pin.getSite()
            BP = str(S)+".PHY.GND/G"
            ST = S.getSiteTypeEnum()
        return BP,"GND",str(S),str(ST),"PHY",0
    else:
        S = site_pin.getSite()
        # Make a list of all the site types that could be used for this site
        site_types = list(x for x in S.getAlternateSiteTypeEnums()) + [S.getSiteTypeEnum()]
        for ST in site_types:
            sST = str(ST)
            #print("\t\t",ST)
            try:
                # For this site type, is there a corresponding BEL pin?
                # One of the Vivado warts is that not all site pins are used in all site types for a given site.
                # So, you have to try until you find one that uses it.
                port_bel_pin = site_pin.getBELPin(ST)
            except:
                continue
            # Get list of bel pins this site pin can connect to.
            # Example for SLICE_X36Y163/A2 = [A5LUT.A2, A6LUT.A2]
            bel_conns = port_bel_pin.getSiteConns()
            print("      GETTING PLACEMENT:",site_pin,ST,S,bel_conns)
            # TODO: Not sure what this for loop is doing for us
            for BP in bel_conns:
                # Get BEL and name (ex: "B6LUT/A6") of BEL pin
                B,BP_sink = get_bel_of_pin(BP)
                print("      RETURNED:",B,BP_sink)
                #print("\t\t\tGETTING CONNS:",B,BP_sink)
                # Change 5LUT to 6LUT 
                if str(ST) in ["SLICEM","SLICEL"] and "5LUT" in str(B):
                    B = str(B).replace("5","6")
                    BP_sink = str(BP_sink).replace("5LUT","6LUT")
                #print("\t\t\t",BP,BP.getDir(),B)
                # Build key into primitive map, ex: ('SLICEL', 'B6LUT')
                key = (str(ST),str(B).replace("(BEL)",""))
                if key in primitive_map:  # If not here it is an error
                    #create_and_place(primitive_map[key][0],str(S),key[0],key[1])
                    #print("SINK:",BP_sink)
                    if "7" not in args.family:
                        if BP_sink in ["CARRY4/CYINIT","CARRY4/CI","CARRY8/CI","CARRY8/CI_TOP"]:
                            is_bp = 0
                            BP_sink = str(S)+".CARRY4."+BP_sink
                        elif BP_sink in ["CARRY8/AX","CARRY8/BX","CARRY8/CX","CARRY8/DX","CARRY8/EX","CARRY8/FX","CARRY8/GX","CARRY8/HX"]:
                            continue
                            # These pins don't automatically have their cell pins mapped to these bel pins - not sure how to remap them
                                # Remap by unplace, attach pin, then replace
                        elif ff_regex.match(BP_sink): #{ABCDEFG}/FF{2}/{SR|CE}
                            is_bp = 2
                            BP_sink = str(S)+"/"+BP_sink
                        else:
                            is_bp = 1
                            BP_sink = str(S)+"/"+BP_sink
                    else:
                        is_bp = 1
                        BP_sink = str(S)+"/"+BP_sink  # Ex: SLICE_X12Y41/D6LUT/A5

                    # Need to check if BP is actually a part of the primitive - Such as the CLK bel pin of the A6LUT in SLICEM not used in LUT6
                    primitive = primitive_map[key][0]
                    if primitive == "LUT6" and ("CLK" in BP_sink or "WE" in BP_sink) and "7" not in args.family:
                        primitive = "SRLC32E"
                    if primitive == "FDCE" and ("CLK" in BP_sink) and "7" not in args.family:
                        primitve = "FDSE"
                    ss = str(S)
                    return BP_sink,primitive,str(S),key[0],key[1],is_bp
                else:
                    print("\t#",B,BP_sink,"NO PRIMITIVE",file=ft)
                    return 0

def reset_manual_routing(CP):
    print("set S [get_sites -of_objects [get_cells -of_objects [get_pins",CP,"]]]",file=ft)
    print("set ST [get_property MANUAL_ROUTING $S]",file=ft)
    print("reset_property MANUAL_ROUTING $S",file=ft)




def attach_net(BP,is_bp,net_name):
    """
    Emit TCL code to connect a net to a BEL pin.

    Unplaces corresponding cell if it is placed and then re-places it.

    Parameters
    ----------
    BP : str
        Name of BEL pin.  Ex: "SLICE_X6Y98/D6LUT/A3"
    is_bp : int
        Means various things, 1 is normal BEL pin.  See elsewhere for others.
    net_name : str
        The net name.
    """
    if is_bp == 1:
        print("set P [get_pins -of_objects [get_bel_pins ",BP,"]]",file=ft)
    elif is_bp == 2:
        print("#IS BP 2:",file=ft)
        bel = BP.rsplit("/",1)[0]
        pin = BP.rsplit("/",1)[1]
        if pin == "SR":
            pin = "CLR"
        print("set P [get_pins [get_cells -of_objects [get_bels " + bel + "]]/"+pin+"]",file=ft)
    else:
        print("set P [get_pins ",BP,"]",file=ft)
    print("if {$P != \"\"} {",file=ft)
    print("set C [get_cells -of_objects $P]\nset loc [get_property LOC $C]\nset bel [get_property BEL $C]",file=ft)
    print("if {$loc != \"\"} { catch { unplace_cell $C  } }",file=ft)
    print("connect_net -net",net_name, "-objects $P",file=ft)
    print("if {$loc != \"\"} { catch { place_cell $C \"$loc/$bel\" } }",file=ft)
    print("}",file=ft)
    
def add_nets():
    """
    Output TCL code to create nets in the global nets list.

    Previously, the create_net() function just aded net ionfo to a global list.
    This actually emits the Tcl code to create all those nets and set their routing.
    """
    global nets, ft
    for x in nets:
        is_bel_pin_up, is_bel_pin_down, BP_up, BP_down, path,net_name = x
        print("set N [create_net -net", net_name,"]",file=ft)
        attach_net(BP_up,is_bel_pin_up,net_name)
        attach_net(BP_down,is_bel_pin_down,net_name)
        print("catch {set_property FIXED_ROUTE",path,"$N}",file=ft)
    nets = []

def create_net(is_bp_up,is_bp_down,BP_up, BP_down, path,net_name):
    """
    Add new net info to list of nets to be created

    Parameters
    ----------
    is_bp_up : int
        There are 3 different int values for this depending on what the BEL pin is tied to.  
        For 7series is always 1, for others can be 0, 1, or 2.
    is_bp_down : int
        See description for is_bp_up.
    BP_up : str
        Ex: "SLICE_X6Y8/B6LUT/A4"
    BP_down : str
        Ex: "SLICE_X6Y8/B6LUT/A4"
    path : [ str, ... ]
        List of names of nodes making up the net's path.
    net_name : str
        Name of net.

    Global Effects
    --------------
    Adds list representing net to nets.
    """
    global nets
    nets.append([is_bp_up, is_bp_down,BP_up, BP_down, path,net_name])
    

def export_path(path_up, site_pin_up,path_down, site_pin_down,net_name):
    """
    Place cells for the endpopints of a net and add net info to global list of nets to be created later.

    Parameters
    ----------
    path_up : [ str, ... ]
        List of node names from PIP to sink.
    site_pin_up : Device.SitePin
        Sink site pin.
    path_down : [ str, ... ]
        List of node names from PIP to source.
    site_pin_down : Device.SitePin
        Source site pin.
    net_name : str
        Name of net.

    Returns
    -------
    int
        1 = success, 0 = failure
    """
    up,down = [],[]
    #BP_sink, primitive, site, site_type, bel
    #Ex: ("SLICE_X13Y37/B6LUT/A3", "LUT6", "SLICE_X13Y37", "SLICEL",    "B6LUT",    1)
    up = get_placement(site_pin_up)
    down = get_placement(site_pin_down)
    print("\tEXPORT:",path_up, site_pin_up,path_down, site_pin_down,net_name,up,down)
    if up and down:
        if ".".join(up[2:5]) != ".".join(down[2:5]): # Check if site/site_type/bel is equivalent - only place one
            create_and_place(*up[1:5])
            create_and_place(*down[1:5])
        else:
            create_and_place(*up[1:5])
        path_down.reverse()
        #path_down = path_down[:-2]
        # Create total path from the UP and DOWN paths.
        path = list(str(x) for x in path_down) + (list(str(x) for x in path_up))
        path_str = "{"
        for x in path:
            path_str += x + " "
        path_str += "}"
        # Add this net to list of nets to be created later.
        create_net(up[5],down[5],up[0],down[0],path_str,net_name)
        return 1
    else:
        return 0
    



def generate_pip_bitstream():
    global fuzz_path, specimen_number, tile_type
    post_placement_drc(1)
    add_nets()
    pip_bitstream_drc()
    print("record_device_pips data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.ft",file=ft)
    write_bitstream("data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.bit")
    specimen_number+=1
    open_checkpoint("vivado_db/init")
    return 

def add_used_site(site_pin):
    """
    Add a site to list of used sites.

    Parameters
    ----------
    site_pin : Device.SitePin
        The site pin of interest.

    Global Effects
    --------------
    Appends Device.Site objects to global used_sites list.        
    """
    global used_sites
    if "HARD" not in str(site_pin):
        S = str(site_pin.getSite())
    elif ".US." in str(site_pin):
        S = site_pin.split(".")[0]
    else:
        S = str(site_pin.getSite())
    print("SITEPIN:",site_pin,S)
    used_sites.append(S)



def run_pip_generation(tile_list,pip_list):
    """
    Create specimens and run Vivado on them to solve for pips.

    Parameters
    ----------
    tile_list : [ Device.Tile, ... ]]
        List of all tiles of the proper type.
    pip_list : [ int, ... ]
        List of indices of PIPs that need solving for.  
        Each entry indexes into list that Device.Tile.getPIPs() returns.
    
    Global Effects
    --------------
    ????
    """
    global specimen_number,tile_type,fuzz_path, used_sites, ft, banned_pin_list,args, pipsToDo
    
    used_tiles = [] # need to make sure placement doesn't collide with other tiles
    max_pips_test = 75
    if len(tile_list) < max_pips_test:
        max_pips_test = 10
    if tile_type in ["BRAM_L","BRAM_R","BRAM"]:
        max_pips_test = 1
    if max_pips_test > len(tile_list):
        max_pips_test = len(tile_list)
    
    # List of tiles available for use
    cur_tile_list = tile_list.copy()

    # List of sites that have been used and should be avoided
    used_sites = []

    # A dict that tabulates how many times a given PIP has failed its 
    # UP/DOWN search for suitable SitePin endpoints.
    max_attempt = {}

    iteration = 0
    banned_pin_list = ["SR","CE"]
    if "7" in args.family:
        series_depth = 6
        max_route_attempt = 2
    else:
        series_depth = 7
        max_route_attempt = 20
    
    print(f"[LOG]: Starting run_pip_generation, len(pip_list)={len(pip_list)}  {datetime.datetime.now()}", file=sys.stderr)
    while(1):
        # Shuffle the PIP ordering to mix things up
        #BEN Comment out next line to get repeatable behavior
        random.shuffle(pip_list)
        current_pip_count = 0
        for nn,i in enumerate(pip_list):
            # Next 5 lines are for selecting pips to process
            T = random.choice(cur_tile_list)
            pname = str(T.getPIPs()[i])
            print(pname)
            if len(pipsToDo) > 0 and not pname.split('.')[-1] in pipsToDo:
                continue
            attempt_count = 0
            current_pip_count += 1
            max_depth = series_depth
            # Try harder if this PIP has failed before
            if i in max_attempt:
                max_route_attempt = 5
                max_depth+=2
                if max_attempt[i] > 4:
                    max_route_attempt = 10
                    max_depth+=2
                if max_attempt[i] > 9:
                    max_route_attempt = 20
                    max_depth+=2
                if max_attempt[i] > 15:
                    max_route_attempt = 30
                    max_depth+=2

            print(f"\n{nn}:{i}", file=sys.stderr, flush=True)
            while (1):
                print(".", file=sys.stderr, flush=True)
                attempt_count += 1
                #BEN Swap next two lines to get repeatable behavior
                T = random.choice(cur_tile_list)
                # T = cur_tile_list[0]

                # Select PIP 'i' from a randomly chosen tile
                P = T.getPIPs()[i]
                #path_up, site_pin_up = bfs(P,"DOWN")
                #path_down, site_pin_down = bfs(P,"UP")
                #print("MAX DEPTH:",max_depth)

                # Search up and then down
                ret_up = dfs_main(P,"UP",max_depth)
                ret_down = dfs_main(P,"DOWN",max_depth)
                # Did we succeed in both directions?
                if ret_up != None and ret_down != None:
                    # Not a clue why the direction names change on next 2 lines ???
                    # But, site_pin_up will be the sink of the net and site_pin_down the source
                    path_up, site_pin_up = ret_down
                    path_down, site_pin_down = ret_up
                    sspu = str(site_pin_up)
                    sspd = str(site_pin_down)
                    # The following 2 lines print to the TCL file comments about the paths/pins found 
                    # They are invaluable for understanding what tool is doing/debugging
                    print("##",T,P,max_depth,file=ft)
                    print("##",ret_up,ret_down,file=ft)
                    # Net name will be tile.tile_type.pip_name.  Ex: INT_L_X7Y29.INT_L.GFAN3->>BYP_ALT7
                    net_name = str(T)+"."+str(P).split("/")[1]
                    # Place endpoint cells for net and put net on list to be created later.
                    if export_path(path_up, site_pin_up,path_down, site_pin_down,net_name):
                        # Remove sites and tile from further use
                        add_used_site(site_pin_up)
                        add_used_site(site_pin_down)
                        cur_tile_list.remove(T)
                        break
                elif attempt_count >= max_route_attempt:
                    print("##",P,"MAX ATTEMPT REACHED",max_depth,file=ft)
                    if i not in max_attempt:
                        max_attempt[i] = 1
                    else:
                        max_attempt[i] = max_attempt[i] + 1
                    print(f"  MAX REACHED: {T} {P}", file=sys.stderr, end="")
                    break

            if current_pip_count%max_pips_test == max_pips_test-1:
                generate_pip_bitstream()
                used_sites = []
                cur_tile_list = tile_list.copy()
            #if specimen_number%10 == 3:
            #    break
        generate_pip_bitstream()
        ft.close()
        print("\n[LOG]: Running Vivado...", file=sys.stderr)
        os.system("vivado -mode batch -source data/" + fuzz_path + "/fuzz_pips.tcl -stack 2000")
        pips = tile_list[0].getPIPs()
        pip_list = check_pip_files(pips)

        print(f"[LOG]: len(pip_list)={len(pip_list)}, iteration={iteration}  {datetime.datetime.now()}", file=sys.stderr)
        os.system(f"cp data/{fuzz_path}/fuzz_pips.tcl data/{fuzz_path}/fuzz_pips_{iteration}.tcl")
        # There are 3 ways to stop iterating:
        #   a) We disambiguate all the pips in the list of pips
        #   b) We hit our iteration count
        #   c) A file named "STOP" has been placed into the directory with the .bit files
        # The last method is a way to force an early stop if the iteration count is not getting reached
        # Examples for INT_L: iteration count=20 takes 8 hrs, 23 takes 18 hrs
        # At 8 hrs there were ~150 signals still in pip_list and at 18 hrs it was ~115
        # See bitrec/fuzzer/readme.md for discussion on disambiguatin pips in pip fuzzer
        if len(pip_list) == 0 or \
              iteration >= int(args.pip_iterations) or \
              path.exists(f"data/{fuzz_path}/STOP"):
            break

        init_file()
        iteration+=1
        if iteration >= 2:
            banned_pin_list = []
    print("[LOG]: Exiting run_pip_generation", file=sys.stderr)  



def add_pip_to_set(set_name,P):
    """
    Add PIP name to list of PIPs for a 

    Parameters
    ----------
    set_name : str
        Name of wire that is output of a PIP.
    P : str
        Name of PIP.
    """
    global pip_set
    if set_name not in pip_set:
        pip_set[set_name] = [P.rsplit("/",1)[-1]]
    else:
        pip_set[set_name] += [P.rsplit("/",1)[-1]]

def generate_pip_sets(pip_list):
    """
    Create dict mapping wires to the set of PIPs that drive them.

    Parameters
    ----------
    pip_list : [ PIP ]
        List of PIPs for a given tile.
    
    Global Effects
    --------------
    pip_set : dict of { str : [ str, ... ]}
        Example dict entry: 'CMT_IN_FIFO_WRCLK': ['CMT_FIFO_L.CMT_FIFO_L_CLK1_6->CMT_IN_FIFO_WRCLK', ... ]
    """

    global pip_set
    pip_set = {}
    for pip in pip_list:
        P = str(pip)
        set_name = P.rsplit(">",1)[-1]
        # Is this PIP bi-directional?  If so, put in  two entries, one for each direction.
        if "<" in P:
            up_P = P.replace("<","")
            add_pip_to_set(set_name,up_P.rsplit("/",1)[-1])
            dest = P.rsplit(">",1)[-1]
            base_src = P.rsplit("<",2)[0]
            base, src = base_src.rsplit(".")
            base = base.split("/")[-1]
            add_pip_to_set(src,base+"."+dest + "->>" + src)
        else:
            add_pip_to_set(set_name,P)

    print("PIP_SET from generate_pip_sets():")
    for x in pip_set:
        print("  ", x,len(pip_set[x]),pip_set[x])


def check_pip_files(pip_list):
    """
    Create list of pips that are still not dis-ambiguated and therefore still need to be solved for.

    Parameters
    ----------
    pip_list : [ Device.PIP, ... ]
        List of pips in current tile to check.

    Returns
    -------
    [ int, ...]
        List of indices to PIPs from tile_type that this *thinks still need to be solved for.
    """
    global fuzz_path, pip_dict, bel_dict, pip_set, pipsToDo
    # Step 1: Start with an empty pip_dict and add to it
    pip_dict = {}
    fileList = os.listdir("data/" + fuzz_path + "/")
    for file in sorted(fileList):
        if ".ft" in file:
            # Look for specimens we have a .ft and .bit for...
            if os.path.exists("data/" + fuzz_path + "/" + file.replace(".ft", '.bit')):
                specimen, tile_type, pip_ext, ext = file.split(".")
                # Parse feature file and build tile_feature_dict
                f = open("data/" + fuzz_path + "/" + file)
                # Build a dict called tile_feature_dict
                # It has keys such as: CLB.0105.0.INT_L_X20Y25 (one for each tile that has PIPs turned on)
                #   These are of the form: CONFIGBUS.FUZZ_PATH.SPECIMEN.TILE
                # Each entry contains a list of strings such as: [ 'C:Tile_Pip:INT_L.NR1END1->>GFAN0', 'C:Tile_Pip:INT_L.GFAN0->>BYP_ALT1', ... ]
                #   These are of the form: CONFIGBUS_FIRSTCHAR:FEATURE_TYPE:FEATURE_NAME
                tile_feature_dict = parse_feature_file(f, fuzz_path + "." + specimen, tile_type)
                print("PARSED FEATURE")
                f.close()
                for T in tile_feature_dict:
                    # Only worry about features (PIPS) in tile_type of interest
                    if tile_type in T:
                        for F in tile_feature_dict[T]:
                            # Get the PIP name and see if already in dict
                            F_name = F.rsplit(":",1)[-1]
                            if F_name not in pip_dict:
                                tmp = {}
                                for PF in tile_feature_dict[T]:
                                    set_p = PF.rsplit(">",1)[-1]
                                    tmp[set_p] = {PF}
                                pip_dict[F_name] = tmp
                                #pip_dict[F_name] = set(tile_feature_dict[T])
                            else:
                                diff_keys = set(pip_dict[F_name].keys()) - set(list(x.rsplit(">",1)[-1] for x in tile_feature_dict[T]))
                                #print("DIFF KEYS:",diff_keys)
                                for x in diff_keys:
                                    pip_dict[F_name].pop(x,None)
                                for PF in tile_feature_dict[T]:
                                    set_p = PF.rsplit(">",1)[-1]
                                    if set_p in pip_dict[F_name]:
                                        pip_dict[F_name][set_p].add(PF)
                                        if len(pip_dict[F_name][set_p]) >= len(pip_set[set_p]):
                                            pip_dict[F_name].pop(set_p,None)
                                #pip_dict[F_name] = pip_dict[F_name] & set(tile_feature_dict[T])
    #print("PRINTING PIP DICT:")
    #for F in pip_dict:
    #    print(F,pip_dict[F])
    pd = pip_dict
    print("^^^ ", type(pd), len(pd))
    for e in pd:
        print("    ", e, type(e), type(pd[e]))
        for f in pd[e]:
            print("        ", f, type(f), type(pd[e][f]), pd[e][f])

    # Step 2: Throw out all default/always PIPs
    for F in pip_dict:
        # If pip is default/always, then remove it entirely
        if F.split(".")[-1] in bel_dict["TILE_PIP"] and bel_dict["TILE_PIP"][F.split(".")[-1]]["TYPE"] != "PIP":
            pip_dict[F] = {}
        else:
            remove_pips = set()
            # Remove always and default pips
            for x in pip_dict[F]:
                #print("X:",x)
                for y in pip_dict[F][x]:
                    #print("Y:",y)
                    if y.split(".")[-1] in bel_dict["TILE_PIP"] and bel_dict["TILE_PIP"][y.split(".")[-1]]["TYPE"] != "PIP":
                        remove_pips.add(x)
            #print("Removing:",remove_pips)
            for x in remove_pips:
                pip_dict[F].pop(x,None)
            #pip_dict[F] = pip_dict[F] - remove_pips
        
        #print(F,len(pip_dict[F]),pip_dict[F])

    # Step 3: From the entries in pip_dict create list of pips that *may not* have been solved for
    remaining_pips = []
    pips = list(str(x).split("/")[-1] for x in pip_list)
    #print(pip_dict.keys())
    for idx, x in enumerate(pips):
        #print("ENUM",idx,x)
        F = x.split(".")[-1]
        if bel_dict["TILE_PIP"][F]["TYPE"] != "PIP":
            continue
        # There are 2 conditions for this to think a pip has not been solved for.
        # The first is it is not in the pip_dict
        # The second is that is in the pip_dict but has an entry longer than 1 
        #   (meaning it is not the only PIP turned on in its tile)
        if x not in pip_dict or len(pip_dict[x]) > 1:
            # Next 2 lines are for selecting pips to process
            if len(pipsToDo) > 0 and not F.split('.')[-1] in pipsToDo:
                continue

            remaining_pips.append(idx)
    
    #for x in pip_dict:
    #   if len(pip_dict[x]) > 1:
    #        remaining_pips.append(pips.index(x.split(":")[-1]))
    print("REMAINING:", len(remaining_pips))
    for x in remaining_pips:
        print('  ', x,pips[x])
        if pips[x] in pip_dict:
            print("\t",pip_dict[pips[x]])
    print("DONE CHECK")
    return remaining_pips


def init_file():
    """
    Begin TCL file.

    Create TCL file, add first few commands, turn off DRC checks.
    """
    global ft, fuzz_path, args
    ft = open("data/" + fuzz_path + "/fuzz_pips.tcl","w",buffering=1)
    set_ft(ft)
    print("source ../../record_device.tcl",file=ft)
    print("source ../../drc.tcl",file=ft)
    open_checkpoint("vivado_db/init")
    disable_drc()
    #print("source ../../fuzz_pip.tcl",file=ft)
    print("set ::family " + args.family,file=ft)
    print("set part_name " + args.part,file=ft)


def run_pip_fuzzer(in_fuzz_path,in_args):
    """
    Run the PIP fuzzer.

    Relies on the BEL fuzzer having been run previously to create <familly>/<part>/dir/db.<tile_type>.json file.

    Parameters
    ----------
    in_fuzz_path : str
        Relative patch from bitrec/fuzzer to numbered directory (ex: 0014) where program is working.
    in_args : parseargs::args
        Command line args.
    """ 
    global args, tile_type, tile_dict, primitive_map, nets, ft, fuzz_path, specimen_number, bel_dict, pip_dict, pipsToDo

    tile_type = in_args.tile_type[0]
    fuzz_path = in_fuzz_path
    args = in_args
    set_args(in_args)   # In data_generator.py
    nets = []
    fj = open("vivado_db/primitive_dict.json")
    primitive_dict = json.load(fj) 
    fj.close()
    fj = open("vivado_db/bel_dict.json")
    bel_dict = json.load(fj) 
    fj.close()
    bel_dict = bel_dict["TILE_TYPE"][tile_type]
    specimen_number = 0
    
    pipsToDo = ["EE2END2->>IMUX_L20", "GFAN0->>BYP_ALT1"]

    # Superfluous assignment, done for real in check_pip_files
    pip_dict = {}

    # Create TCL file, write first few commands, turn off DRC.
    init_file()

    # Set device and create design.
    init_rapidwright(args.part)

    # Get dict of { (siteType, belType) : [primitiveName, ...] }
    primitive_map = get_placement_dict(primitive_dict["PRIMITIVE"])

    tile_list = get_rapid_tile_list(tile_type)

    # Create a dictionary mapping each pip output wire to the set of all pips that drive that wire.
    generate_pip_sets(tile_list[0].getPIPs())

    # Create list of pips that are still not dis-ambiguated and therefore still need to be solved for
    pip_list = check_pip_files(tile_list[0].getPIPs())
    
    run_pip_generation(tile_list,pip_list)
    check_pip_files(tile_list[0].getPIPs())

    
