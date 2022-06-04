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
import argparse
import sys
import random
from multiprocessing import Pool

def data_generator_init():
    global primitive_dict, bel_dict, tile_dict, tilegrid, tile_type, ft, specimen_number
    fj = open("vivado_db/primitive_dict.json")
    primitive_dict = json.load(fj) 
    fj.close()
    fj = open("vivado_db/bel_dict.json")
    bel_dict = json.load(fj) 
    fj.close()
    fj = open("vivado_db/tile_dict.json")
    tile_dict = json.load(fj) 
    fj.close()
    fj = open("vivado_db/tilegrid.json")
    tilegrid = json.load(fj) 
    fj.close()

    tile_type = ""
    ft = ""
    specimen_number = 0

##================================================================================##
##                                CREATE TCL SCRIPT                               ##
##================================================================================##                  

####################################################################################
# The next group of routines simply emit the TCL code which roughly corresponds to 
# the routine's name.
####################################################################################
def set_dir(folder):
    print("cd " + folder,file=ft)

def set_port_standard(io_standard):
    print("if {[get_ports] != \"\"} {",file=ft)
    print("set_property IOSTANDARD "+ io_standard + " [get_ports] }",file=ft)

def create_cell(ref,count):
    print("create_cell -reference "+ ref + " C_" + str(count),file=ft)

def create_cells(ref,name_list):
    print("create_cell -reference "+ ref + " " + name_list,file=ft)

def set_site_type(tile_type,site_index,site_type):
    print("foreach T [get_tiles -filter \"TYPE==" +tile_type+"\"] { set_property MANUAL_ROUTING " + site_type + " [lindex [get_sites -of_objects $T] "+site_index+" ]}",file=ft)
    #print("set_property SITE_PIPS [list] $site_list" ,file=ft)

def reset_site_type(tile_type,site_index):
    print("foreach T [get_tiles -filter \"TYPE==" +tile_type+"\"] { reset_property MANUAL_ROUTING [lindex [get_sites -of_objects $T] "+site_index+" ]}",file=ft)

def place_cell_str(tile,site_index,bel,count):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    return "\"C_" + str(count) + "\" " + site + "/" + bel

def place_cell(tile,site_index,bel,count):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    print("place_cell [get_cells \"C_" + str(count) + "\"] " + site + "/" + bel,file=ft)

def place_cells(cell_placement_list):
    print("place_cell " + cell_placement_list,file=ft)

def set_property(count, prop, val,primitive):
    if primitive == "PORT":
        print("catch {[set_property ", prop, val, "[get_ports \"port_" + str(count) + "\"] ]}",file=ft)
    else:
        print("catch {[set_property ", prop, val, "[get_cells \"C_" + str(count) + "\"] ]}",file=ft)

def set_property_by_loc(T, site_index, site_type, bel, prop, val,primitive):
    site = "[lindex [get_sites -of_objects [get_tiles " + T + "]] " + site_index + "]"
    if primitive == "PORT":
        cell = "[get_ports -filter \"LOC==" + site + "\"]"
    else:
        cell = "[get_cells -filter \"LOC==" + site + " && BEL== " + site_type + "." + bel + "\"]"
    print("catch {[set_property ", prop, val, cell," ]}",file=ft)

def write_checkpoint(file_name):
    print("write_checkpoint " + file_name +".dcp" + " -force",file=ft)

def init_design():
    """
    Emit TCL to close existing design (if any) and load init.dcp.
    """
    print("if {[catch {get_designs}] == 0} { close_design }",file=ft)
    print("open_checkpoint vivado_db/init.dcp -ignore_timing",file=ft)

def open_checkpoint(file_name):
    print("if {[catch {get_designs}] == 0} { close_design }",file=ft)
    print("open_checkpoint " + file_name + ".dcp -ignore_timing",file=ft)

def lock_design():
    print("foreach C [get_cells] {",file=ft)
    print("set_property DONT_TOUCH 1 $C",file=ft)
    print("}",file=ft)

def place_design():
    print("tie_unused_pins",file=ft)
    print("set r [catch {[place_design]}]",file=ft)

def route_design():
    print("catch {[route_design]}",file=ft)
    print("if {$r == 1} { catch {[place_design]}}",file=ft)

def reroute_physical_design():
    print("catch {[route_design -unroute -physical_nets]}",file=ft)
    print("catch {[route_design -physical_nets]}",file=ft)
    print("tcl_drc_ultra_latch",file=ft)


def write_bitstream(file_name):
    if int(args.checkpoints) == 2:
        write_checkpoint(file_name + "backup")
        print("catch {[write_bitstream " + file_name + " -force]}",file=ft)
    elif int(args.checkpoints) == 1:
        print("if {[catch {write_bitstream " + file_name + " -force}] == 1} {",file=ft)
        print("   write_checkpoint " + file_name +".dcp",file=ft)
        print("   close_design",file=ft)
        print("   open_checkpoint " + file_name +".dcp -ignore_timing",file=ft)
        #print("tcl_drc_invalid_io_sitepips",file=ft)
        print("   catch {[write_bitstream " + file_name + " -force]}",file=ft)
        print("}",file=ft)
    else:
        print("catch {[write_bitstream " + file_name + " -force]}",file=ft)

def disable_drc():
    if int(args.drc) == 0:
        print("disable_drc",file=ft)

def create_site_pip(tile, site_index, site_pip, site_pip_value):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    print( "catch {[set_property SITE_PIPS " + site +"/" + site_pip + ":" + site_pip_value + " "+  site + "]}",file=ft)

def record_feature_file(file_name):
    global tile_type
    print("record_device " + file_name + ".ft " + tile_type,file=ft)

def create_polarity_selector(count, pin, val, tile,site_index,site_type):
    site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
    print("reset_property MANUAL_ROUTING " + site,file=ft)
    print("set p [get_pins -of_objects [get_cells \"C_" + str(count) + "\"] -filter \"NAME=~*/" + pin + "\" ]",file=ft)
    #print("set p [get_pins -of_objects [get_bel_pins -of_objects [get_bels -of_objects " + site + "] -filter \"NAME=~*" + site_pip + "\"]]",file=ft)
    print("if {$p != \"\"} {set_property IS_INVERTED " + str(val) + " $p }",file=ft)
    print("set_property MANUAL_ROUTING " + site_type + " " + site,file=ft)


def add_sources():
    """
    Print needed source commands to TCL file
    """
    print("source ../../record_device.tcl",file=ft)
    print("source ../../drc.tcl",file=ft)
    print("set ::family " + args.family,file=ft)
    print("set part_name " + args.part,file=ft)

#
#def create_tile_pip(tile,pip):
#    print("lappend pip_list " + pip)
#

##########################################################
##                     DRC CHECKS                       ##
##########################################################


##############
## DRC MAIN ##
##############

def pre_placement_drc(checkpoint,tile_list):
    """
    Emit TCL code to run pre-placement checks.

    1. When using LUT in lutram mode, must use the DLUT (and possibly CLUT) for it to be legal.
       Emitted code fixes that.
    2. Mark FF's with the property IOB=TRUE

    Parameters
    ----------
    checkpoint : str
        Name of checkpoint.
        Format is: 'tile_type.site_index.site_type.bel.primitive'
        Example:   'CLBLL_L.0.SLICEL.A5FF.FDCE'
    tile_list : list 
        List of tiles to check for lutram fixing.
    """
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    if site_type == "SLICEM":
        for tile in tile_list:
            site = "[lindex [get_sites -of_objects [get_tiles " + tile + "]] " + site_index + "]"
            print("tcl_drc_lut_rams " + primitive + " " + bel + " " + site,file=ft)
    # Mark cells from the list of FF's (FDSE, FDRE, ...) with the property IOB=TRUE
    print("tcl_ff_iob",file=ft)
    

def post_placement_drc(pips):
    """
    Emit TCL code to do all the needed post placement DRC checks and then place and route the design.

    Refer to the code for each routine called to see what it does.

    Parameters
    ----------
    pips : int
        Flag to control what to do w.r.t LUT pins
    """
    # Fix DRC checks
    if pips == 0:
        print("tcl_drc_lut_pins",file=ft)
    else:
        print("tcl_lock_lut_pins",file=ft)
        print("tcl_drc_lut_routethru_eqn",file=ft)
    print("tcl_drc_bscan",file=ft)
    print("tcl_drc_lut_ram_pins",file=ft)
    print("tcl_drc_idelay",file=ft)
    print("tcl_drc_fix_iobuf_placement",file=ft)
    print("tcl_drc_diff_pairs",file=ft)
    # lock and implement design
    lock_design()
    if pips == 0:
        place_design()
        route_design()


def pre_bitstream_drc(primitive,site_type):
    print("tcl_fix_properties " + site_type,file=ft)
    print("tcl_drc_bram_write",file=ft)
    if "INVERTIBLE_PINS" not in primitive_dict["PRIMITIVE"][primitive]:
        print("refresh_cell " + primitive,file=ft)
    elif len(primitive_dict["PRIMITIVE"][primitive]["INVERTIBLE_PINS"]) != 0 and site_type not in ["SLICEL","SLICEM","FIFO18E1","FIFO36E1"]:
        if primitive not in ["FDSE", "FDRE", "FDPE", "FDCE", "LDCE", "LDPE", "LDCE"]:
            print("refresh_cell " + primitive,file=ft)

def pip_bitstream_drc():
    #print("removed_unused_cells",file=ft)
    #print("catch { set_property DONT_TOUCH 0 [get_cells -filter \"STATUS==UNPLACED && REF_NAME!=VCC && REF_NAME!=GND\"] }",file=ft)
    #print("catch { remove_cell [get_cells -filter \"STATUS==UNPLACED && REF_NAME!=VCC && REF_NAME!=GND\"] }",file=ft)
    #print("foreach S [get_sites -filter \"SITE_TYPE==SLICEM\"] {reset_property MANUAL_ROUTING $S}",file=ft)
    print("foreach S [get_sites -filter \"SITE_TYPE==SLICEL\"] {reset_property MANUAL_ROUTING $S}",file=ft)
    print("tcl_drc_pips_reg_pins",file=ft)
    print("tie_unused_pins",file=ft)
    print("catch {[route_design]}",file=ft)
    print("tcl_drc_bram_write",file=ft)
    print("catch { refresh_cell DSP48E1 } ",file=ft)
    print("catch { refresh_cell FDCE } ",file=ft)
    print("catch { refresh_cell LUT6 } ",file=ft)
    print("catch { refresh_cell CARRY4 } ",file=ft)
    print("catch { reset_property FIXED_ROUTE [get_nets -filter \"ROUTE_STATUS==ANTENNAS\"] }",file=ft)
    #print("catch { remove_net [get_nets -filter \"ROUTE_STATUS==CONFLICTS && NAME!~lutram*\"] }",file=ft)
    print("catch {[route_design]}",file=ft)
    #print("catch { remove_net [get_nets -filter \"ROUTE_STATUS==UNROUTED\"] }",file=ft)
    #print("catch {[route_design]}",file=ft)

    print("catch {route_design -nets [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"] }",file=ft)
    print("catch {set_property is_route_fixed 0 [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]}",file=ft)
    print("catch {set_property is_bel_fixed 0 [get_cells -of_objects [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]]}",file=ft)
    print("catch {set_property is_loc_fixed 1 [get_cells -of_objects [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]]}",file=ft)
    print("catch {route_design -nets [get_nets -filter \"ROUTE_STATUS==CONFLICTS\"]}",file=ft)
    print("catch {[route_design]}",file=ft)
    #




##########################################################
##                         FUZZER                       ##
##########################################################

def hex_values(bin_digits,value):
    #print(bin_digits,value)
    if bin_digits == 1:
        return ["'b0", "'b1"]
    if "h" in value:
        max_val = value.rsplit("h",1)[1]
        max_val = int(max_val.replace("}",""),16)
    elif "b" in value:
        max_val = value.rsplit("b",1)[1]
        max_val = int(max_val.replace("}",""),2)
    else:
        max_val =value.rsplit(" ",1)[1]
        max_val = int(max_val.replace("}",""))
    hex_vals = []
    for i in range(8):
        hex_vals.append("1"*pow(2,i) + "0"*pow(2,i))
        hex_vals.append("0"*pow(2,i) + "1"*pow(2,i))
    hex_val_repeat = [128, 128, 64, 64, 32, 32, 16, 16, 8, 8, 4, 4, 2, 2, 1, 1] 
    possible_values = ["\'b0","\'b" + ("1"*bin_digits)]
    count = 0
    inc = 0
    for i in range(len(hex_vals)):
        if i%2 == 0:
            count += 1
        sub_string = hex_vals[i]*hex_val_repeat[i]
        sub_string = sub_string[len(sub_string)-bin_digits:]
        sub_string = str(bin(int(sub_string,2) & max_val))
        possible_values.append(sub_string.replace("0b",str(bin_digits)+"\'b"))
        if (pow(2,count) > bin_digits):
            inc += 1
        if inc == 2:
            break
    return possible_values

def gen_bitstream(file_name):
    """
    Generate TCL commands to write a bitstream.

    Parameters
    ----------
    file_name : str
        Name of the btstream as in: 'DSP_L.1.DSP48E1.DSP48E1.DSP48E1'.
        This is the same as the checkpoint name elsewhere in this code.
    """
    global specimen_number, fuzz_path,tile_type,args
    if len(file_name.split(".")) == 6:
        tile_type, site_index, site_type, bel, primitive, tilegrid_ext = file_name.split(".")
    else:
        tile_type, site_index, site_type, bel, primitive = file_name.split(".")
    
    # TODO: why do we need to reset site type, reroute, then set site type again?
    reset_site_type(tile_type,site_index)
    pre_bitstream_drc(primitive,site_type)
    #if ("7" not in args.family):
    #    print("tcl_fuzz_pins",file=ft)
    reroute_physical_design()
    set_site_type(tile_type,site_index,site_type)
    print("tcl_drc_invalid_io_sitepips", primitive, site_type,file=ft)
    record_feature_file("data/" + fuzz_path + "/" + str(specimen_number) + "." + file_name)
    write_bitstream("data/" + fuzz_path + "/" + str(specimen_number) + "." + file_name + ".bit")
    specimen_number+=1


def get_column_list():
    """
    Make a list of tiles, one per column of the specified tile type.

    Returns
    -------
    [ str, ...]
        List of tiles: [ 'CLBLL_L_X5Y10', 'CLBLL_L_X9Y32' ]
    """
    global tile_type
    col_list = []
    col_tile_list = []
    for T in tilegrid:
        if tile_type == tilegrid[T]["TYPE"]:
            if tilegrid[T]["COL"] not in col_list:
                col_list.append(tilegrid[T]["COL"])
                col_tile_list.append(T)
    return col_tile_list


def random_properties(tile,site_index,site_type,bel,P):
    """
    For a given primitive P placed on a site in a tile, choose (and set) a random value for EACH of its properties.

    Ignore IO_STANDARD properties and properties with 'FILE' in their name.

    Parameters
    ----------
    tile : str
        Name of tile as in: 'CLBLL_L_X35Y0'
    site_index : str
        Site number as a string as in: '0'
    site_type : str
        The site type as in: 'SLICEL'
    bel : str
        The BEL name as in: 'A5FF'
    P : str
        The primitive name as in: 'FDCE'

    Returns
    -------
    [ str, ... ]
        List of values that were set.  
    """
    # P_dict is the primitive_dict entry and consists, typically, of 'INVERTIBLE_PINS' and 'PROPERTIES'
    P_dict = primitive_dict["PRIMITIVE"][P]
    V_list = []
    for prop in P_dict["PROPERTIES"]:
        # Ignore IOSTANDARD properties
        if prop not in ["IOSTANDARD"]:
            prop_type = P_dict["PROPERTIES"][prop]["PROPERTY_TYPE"]
            #print(prop, P_dict["PROPERTIES"][prop])
            if prop_type in ["hex","binary"]:
                V = random.choice(hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]))
                set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
            # We don't handle double typed properties
            elif prop_type in ["double"]:
                V = "double"
                print("PROPERTY:",prop," VALUE:",P_dict["PROPERTIES"][prop]["VALUE"])
            elif prop_type in ["int"]:
                if "BIN_DIGITS" in P_dict["PROPERTIES"][prop]:
                    V = random.choice(hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]))
                    V = int(V.split("\'b")[-1],2)
                    set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
                else:
                    V = random.choice(P_dict["PROPERTIES"][prop]["VALUE"])
                    set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
            else:
                if "FILE" not in prop:
                    V = random.choice(P_dict["PROPERTIES"][prop]["VALUE"])
                    set_property_by_loc(tile, site_index, site_type, bel, prop, V,P)
            if "INVERTED" not in prop:  # Don't return values for properties with "INVERTED" in name
                V_list.append(V)
    return V_list

# TODO: document this
def fuzz_tilegrid(col_tile_list,checkpoint_list):
    global tile_type, tile_dict,ft
    print("FUZZ TILEGRID")
    if len(checkpoint_list) == 0:
        print("NO POSSIBLE PLACEMENT TILEGRID SOLVER")
        return
    checkpoint = checkpoint_list[0]
    if int(args.checkpoint_choice)==-1:
        max_prop = 0 
        for C in checkpoint_list:
            tile_type, site_index, site_type, bel, primitive = C.split(".")
            if len(primitive_dict["PRIMITIVE"][primitive]["PROPERTIES"]) >= max_prop:
                max_prop = len(primitive_dict["PRIMITIVE"][primitive]["PROPERTIES"])
                checkpoint = C
    else:
        checkpoint = checkpoint_list[int(args.checkpoint_choice)]
    for j in range(int(args.checkpoint_count)):
        if j != 0:
            checkpoint = random.choice(checkpoint_list)
        tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
        ft = open("data/" + fuzz_path + "/" + checkpoint + ".tile.tcl","w",buffering=1)
        add_sources()
        open_checkpoint("checkpoints/" + checkpoint)
        disable_drc()
        for T in col_tile_list:
            v_prev = []
            for x in range(int(args.tilegrid_count)):
                #print("X:",x)
                #print("TILEGRID: ",tile_type,site_index,site_type,bel)
                if "PORT" in tile_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]["BEL"][bel]["PRIMITIVE"].keys():
                    io_stand_list = list(io for io in primitive_dict["PRIMITIVE"]["PORT"]["PROPERTIES"]["IOSTANDARD"]["VALUE"])
                    set_port_standard(io_stand_list[x])
                    random_properties(T, site_index, site_type, bel, "PORT")
                while(1):
                    v_list = random_properties(T, site_index, site_type, bel, primitive)
                    #print("LISTING:",v_list,v_prev)
                    if v_prev == [] or v_list != v_prev:
                        v_prev = v_list
                        break
                gen_bitstream(checkpoint + ".tile")
    ft.close()

def fuzzer():
    """
    Fuzz the given tile type.

    Returns nothing.
    """
    global tile_type, ft

    # For example db structure look in vivado_db/tile_dict.json
    db = tile_dict["TILE_TYPE"][tile_type]
    tile_list = []
    # Get list of tiles of tile_type, one per column
    col_tile_list = get_column_list()

    # Get list of tiles, ignoring explicitly UNBONDED ones
    for T in tilegrid:
        if tile_type == tilegrid[T]["TYPE"]:
            if "IS_BONDED" not in tilegrid[T] or tilegrid[T]["IS_BONDED"] == True:
                tile_list.append(T)
    if args.vrbs:
        print("TILE_LIST_LENGTH:",len(tile_list))
    # args.cell_count = "Maximum number of tiles to use per bitstream"
    # Downselect to that number if needed.
    if len(tile_list) > int(args.cell_count):
        tile_list = tile_list[0: int(args.cell_count)]
    # Ignoring the *IOB tiles, make sure all the tiles (one per column) collected above are included.
    # This guarantees at least one tile per column, even if the list got cut short above
    if tile_type not in ["LIOB33","LIOB33_SING","RIOB33","RIOB33_SING"]:
        for x in col_tile_list:
            if x not in tile_list:
                tile_list.append(x)

    if args.vrbs:
        print("Adusted TILE_LIST_LENGTH:",len(tile_list))
    cur_tile = 0
    checkpoint_list = []
    # Primitives and BELS
    if args.vrbs:
        print(f'SITE_INDEX_KEYS: {db["SITE_INDEX"].keys()}')

    # Code Explanation
    # foreach site index:
    #   foreach site type that can live at that site index:
    #       foreach BEL in the site:
    #           foreach primitive (excluding PORTs) that can be placed on the site:
    #               Make checkpoint name of: 'tile_type.site_index.site_type.bel.primitive' as in: 'CLBLL_L.0.SLICEL.A5FF.FDCE'
    #               Add checkpoint name to list of checkpoints
    #               Open TCL file
    #               Write TCL to:
    #                   Initialize a new designm
    #                   Create and place cells (C_0, C_1, ...), one on each tile, placing it on the proper BEL in the proper site
    #                   Write a .dcp checkpoint containing all these placed cells.  Ex: 'CLBLL_L.0.SLICEL.A5FF.FDCE.dcp'
    #               Next, fuzz the primitive (as long as it is not have PORT in its name)
    #                   This does an exhaustive enumeration of every primitive's properties and their values
    #                   It sets sets these on the cells, NOT the bels
    #                   It sets one property:value pair per cell (C_0, C_1, ...)
    #                   When it runs out of cells in the list it:
    #                       Emits a TCL write_bitstream command.  Filename is path/specimen.checkpointName.bit
    #                           Example: 0.DSP_L.0.DSP48E1.DSP48E1.DSP48E1.bit
    #                       Determines features turned on in the current desing adn writes .ft file
    #                       Increments the specimen number
    #               Next, fuzz the site pips, bel pins, do the randomized method, and write a final bitstream.
    #               When done, do a final write_bitstream and move on to the next primitive

    #   IMPORTANTLY:
    #       For tiles with simple primitives (CLBLL_*, IOB_*) there are enough cells in the checkpoint to be able to 
    #           put a single property:value on each.
    #       But, for all other tiles, there is not, and so new .bit/.ft files are created for each specimen after all the tiles get used.
    #           Example: there are only 40 DSP_L tiles and so the cells are from C_0 through C_39 (40 total)
    #               But, there are 111 property:value pairs to apply, meaning it will take 3 bitstreams for just that
    #               The random fuzzing and the PIP and belPin fuzzing also contribute, requiring 28 bitstreams to cover that.
    #   HOWEVER:
    #       After a write_bitstream, the circuit is not returned to its original state (of just placed cells).  This contradicts 
    #       Rather, the previous [set_property ... ] values are still in effect, 
    #           meaning only in the first specimen are features alone on a cell.  After that, they accumulate.
    #   It would seem the checkpoint written way up above (DSP_L.0.DSP48E1.DSP48E1.DSP48E1.dcp) should be reloaded when a bitstream is 
    #       written so C_0, C_1, ... are in their pristine state when the second specimen starts to set other properties on them?
    #   A statement at the bottom of p. 38 of Simpson's thesis ("and the base design is reopened") suggests that is the intent but the code (as well as the generated TCL files) don't reflect that.
    #   TODO: Track this down.
    #
    for i in db["SITE_INDEX"].keys():
        if int(i) < int(args.site_count):
            for j in db["SITE_INDEX"][i]["SITE_TYPE"].keys():  # "SLICEL", "SLICEM", ...
                # Not all sites have BELs
                if "BEL" in db["SITE_INDEX"][i]["SITE_TYPE"][j]:
                    for B in db["SITE_INDEX"][i]["SITE_TYPE"][j]["BEL"].keys():
                        # Ignore ["A5LUT","B5LUT","C5LUT","D5LUT"]
                        if B not in ["A5LUT","B5LUT","C5LUT","D5LUT"]:
                            for P in db["SITE_INDEX"][i]["SITE_TYPE"][j]["BEL"][B]["PRIMITIVE"].keys():
                                # Ignore port primitives
                                if P not in ["PORT"]:              
                                    checkpoint_name = tile_type+"."+i+"."+j+"."+B+"."+P 
                                    if int(args.fuzzer) == 1:
                                        # Create and start filling the TCL file
                                        ft = open("data/" + fuzz_path + "/" + checkpoint_name + ".tcl","w",buffering=1)
                                        print("\n#### Load scripts that will be called later and set family and part name", file=ft)
                                        add_sources()  # Add source cmds to .tcl file
                                    print(f"Checkpoint name: {checkpoint_name}")
                                    checkpoint_list.append(checkpoint_name)
                                    # If checkpoint already exists open it, otherwise create a new one.
                                    if os.path.exists("checkpoints/"  + checkpoint_name + ".dcp") and int(args.init) == 0:
                                        open_checkpoint("checkpoints/" + checkpoint_name)
                                        disable_drc()
                                    else:
                                        # Close previous design and open init.dcp
                                        print("\n#### Init design", file=ft)
                                        init_design()
                                        print("\n#### Disable DRC", file=ft)
                                        disable_drc()
                                        print("\n#### Set site type", file=ft)
                                        set_site_type(tile_type,i,j)
                                        cell_count = 0
                                        cell_name_str = ""
                                        placement_str = ""
                                        for x in range(len(tile_list)):
                                            # Make list of cell names
                                            cell_name_str += "C_" + str(cell_count) + " "
                                            placement_str += place_cell_str(tile_list[x],i,B,cell_count) + " "
                                            cell_count += 1
                                        # Using above two lists, create and place all the cells, running pre-placement check in between.
                                        print("\n#### Create cells", file=ft)
                                        create_cells(P, cell_name_str)
                                        print("\n#### Run pre_placement_drc", file=ft)
                                        pre_placement_drc(checkpoint_name,tile_list)
                                        print("\n#### Place cells", file=ft)
                                        place_cells(placement_str)
                                        # Emit code to do post-placement DRC Fixes and write a .dcp checkpoint
                                        print("\n#### Run post_placement_drc", file=ft)
                                        post_placement_drc(0)
                                        print("\n#### Write checkpoint", file=ft)
                                        write_checkpoint("checkpoints/" + checkpoint_name)
                                    # If not running JUST tilegrid calculation
                                    if int(args.tilegrid) != 2:    
                                        # if this is a port, fuzz the port along with each primitive
                                        if "PORT" in db["SITE_INDEX"][i]["SITE_TYPE"][j]["BEL"][B]["PRIMITIVE"].keys():
                                            for io_stand in primitive_dict["PRIMITIVE"]["PORT"]["PROPERTIES"]["IOSTANDARD"]["VALUE"]:
                                                set_port_standard(io_stand)
                                                # Run a fuzzer for the primitive combination
                                                if int(args.iterative) == 1:
                                                    fuzz_primitive(checkpoint_name,tile_list,1)
                                                randomized_method(checkpoint_name,tile_list,1)
                                                fuzz_site_pips(checkpoint_name,tile_list)
                                                randomized_method(checkpoint_name,tile_list,0)
                                                gen_bitstream(checkpoint_name)
                                        # Fuzz non-PORT primitives
                                        else: 
                                            # Do the iterative BEL property/value fuzzing...
                                            if int(args.iterative) == 1:
                                                print("\n#### Fuzz primitives", file=ft)
                                                fuzz_primitive(checkpoint_name,tile_list,0)
                                            # Next two fuzz_* calls (fuzz_size_pips and fuzz_bel_pins) do almost the exact thing - see docstrings for each.
                                            # TODO: Understand differences
                                            print("\n#### Fuzz site pips", file=ft)
                                            fuzz_site_pips(checkpoint_name,tile_list)
                                            print("\n#### Fuzz bel pins", file=ft)
                                            fuzz_bel_pins(checkpoint_name,tile_list)
                                            print("\n#### Randomized fuzz", file=ft)
                                            randomized_method(checkpoint_name,tile_list,0)
                                            print("\n#### Generate bitstream", file=ft)
                                            gen_bitstream(checkpoint_name)
                                    if int(args.fuzzer) == 1:
                                        ft.close()
    if int(args.tilegrid) != 0:
        fuzz_tilegrid(col_tile_list,checkpoint_list)

def get_next_count(cur,total,checkpoint):
    """
    Increment a count and, if it has hit its max (total), generate bitstream (incrementing specimen number) and reset count to 0.

    Parameters
    ----------
    cur : int
        Current count value
    total : int
        Limit for count value to reach
    checkpoint : str
        Name of checkpoint
        Format is: 'tile_type.site_index.site_type.bel.primitive'
        Example:   'CLBLL_L.0.SLICEL.A5FF.FDCE'

    Returns
    -------
    int
        New current count
    """
    #print(cur)
    cur += 1
    if cur == total:
        gen_bitstream(checkpoint)
        cur = 0
        open_checkpoint("checkpoints/" + checkpoint)
        disable_drc()
    #print("RETURNING:",cur)
    return cur
    
def fuzz_site_pips(checkpoint,tile_list):
    """
    Fuzz every possible site pip.

    With the exception of the "hardcoded fix" below - this is identical to fuzz_site_pips().
    Not sure the difference.

    Parameters
    ----------
    checkpoint : str
        Name of checkpoint
        Format is: 'tile_type.site_index.site_type.bel.primitive'
        Example:   'CLBLL_L.0.SLICEL.A5FF.FDCE'
    tile_list : [  str, ... ]
        List of tiles to use (already have primitives placed in them).
    """

    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    db = bel_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]
    tile_count = 0
    len_tile_list = len(tile_list)
    # hardcoded fix - CLBLL FF primitives don't work well becaues of the SRUSED site pip - just only use A6LUT, plus this is faster to do only the one
    if site_type in ["SLICEL", "SLICEM"] and bel+"."+primitive != "A6LUT.LUT6":
        return
    #open_checkpoint("checkpoints/" + checkpoint)
    pol_selector = 0
    if "SITE_PIP" in db:
        for SP in db["SITE_PIP"].keys():
            # Only do if not polarity selector
            if "INV" not in SP:
                # Loop across possible site pip values
                for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                    create_site_pip(tile_list[tile_count],site_index,SP,V)
                    tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
            elif "CLK" in SP:
                if tile_type not in ["BRAM_L","BRAM_R"]:
                    # Loop across possible site pip values
                    for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                        create_site_pip(tile_list[tile_count],site_index,SP,V)
                        tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
    #gen_bitstream(checkpoint)

def fuzz_bel_pins(checkpoint,tile_list):
    """
    Fuzz every possible site pip.

    Not sure why this routine is called fuzz_bel_pins().  Seems to focus on fuzzing site pips.
    With the exception of the "hardcoded fix" - this is identical to fuzz_site_pips().

    Parameters
    ----------
    checkpoint : str
        Name of checkpoint
        Format is: 'tile_type.site_index.site_type.bel.primitive'
        Example:   'CLBLL_L.0.SLICEL.A5FF.FDCE'
    tile_list : [  str, ... ]
        List of tiles to use (already have primitives placed in them).
    """
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    db = bel_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]
    tile_count = 0
    len_tile_list = len(tile_list)
    #open_checkpoint("checkpoints/" + checkpoint)
    pol_selector = 0
    if "SITE_PIP" in db:
        for SP in db["SITE_PIP"].keys():
            # Only do if not polarity selector
            if "INV" not in SP:
                if args.vrbs:
                    print(f'FUZZ_BEL_PINS BEL={SP}, SITE_PIP_KEYS: {db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys()}')
                # Loop across possible site pip values
                for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                    create_site_pip(tile_list[tile_count],site_index,SP,V)
                    tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
            elif "CLK" in SP:
                if tile_type not in ["BRAM_L","BRAM_R"]:
                    # Loop across possible site pip values
                    if args.vrbs:
                        print(f'FUZZ_BEL_PINS BEL={SP}, SITE_PIP_KEYS: {db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys()}')
                    for V in db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys():
                        create_site_pip(tile_list[tile_count],site_index,SP,V)
                        tile_count = get_next_count(tile_count,len_tile_list,checkpoint)
    #gen_bitstream(checkpoint)


def fuzz_primitive(checkpoint,tile_list,is_port):
    """
    Emit TCL code to fuzz a primitive in terms of outputting its properties and values.

    This is an exhaustive enumeration, known as the "iterative" method in the command line args.  
    In contrast, see randomized_method(), which tries a bunch of randomly selected 

    Parameters
    ----------
    checkpoint : str
        Name of checkpoint. 
        Format is: 'tile_type.site_index.site_type.bel.primitive'
        Example:   'CLBLL_L.0.SLICEL.A5FF.FDCE'
    tile_list : [ str, ... ]
        List of tiles to use (already have primitives placed in them), just need property values assigned.
    is_port : int
        1 = is a port
    """
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    if is_port == 1:
        primitive="PORT"
    count = len(tile_list)
    cell_count = 0
    ## Get info for specific primitive (example for FDCE: INVERTIBLE_PINS, PROPERTIES)
    P_dict = primitive_dict["PRIMITIVE"][primitive]
    # Iterative Brute Force Method
    for prop in P_dict["PROPERTIES"]:
        if prop not in ["IOSTANDARD"]:
            prop_type = P_dict["PROPERTIES"][prop]["PROPERTY_TYPE"]
            if prop_type in ["hex","binary"]:
                for V in hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]):
                    set_property(cell_count,prop,V,primitive)
                    cell_count = get_next_count(cell_count,count,checkpoint)
            elif prop_type in ["double"]:
                print("PROPERTY:",prop," VALUE:",P_dict["PROPERTIES"][prop]["VALUE"])
            elif prop_type in ["int"]:
                if "BIN_DIGITS" in P_dict["PROPERTIES"][prop]:
                    for V in hex_values(P_dict["PROPERTIES"][prop]["BIN_DIGITS"],P_dict["PROPERTIES"][prop]["VALUE"]):
                        print(V,prop)
                        V = int(V.split("\'b")[-1],2)
                        set_property(cell_count,prop,V,primitive)
                        cell_count = get_next_count(cell_count,count,checkpoint)
                else:
                    for V in P_dict["PROPERTIES"][prop]["VALUE"]:
                        set_property(cell_count,prop,V,primitive)
                        cell_count = get_next_count(cell_count,count,checkpoint)
            else:
                for V in P_dict["PROPERTIES"][prop]["VALUE"]:
                    set_property(cell_count,prop,V,primitive)
                    cell_count = get_next_count(cell_count,count,checkpoint)
    
    #pol_selector = 0
    #for pin in P_dict["INVERTIBLE_PINS"]:
    #    pol_selector = 1
    #    for inv in [0,1]:
    #        print(cell_count,len(tile_list))
    #        create_polarity_selector(cell_count,pin,inv,tile_list[cell_count],site_index,site_type)
    #        cell_count = get_next_count(cell_count,count,checkpoint)
    #if pol_selector == 1:
    #    route_design()
    #gen_bitstream(checkpoint)


def randomized_method(checkpoint,tile_list,is_port):
    """
    Do randomized property fuzzing.

    For a random number of trials:
    1. Choose a tile from tile_list that previously had a primitive placed onto it.
    2. Call random_properties() to set the properties of the specified primitive to random values in that tile.  
    3. Also, if site pips exist in this specified site type, create and set a random site pip to a random config value in each tile.

    Parameters
    ----------
    checkpoint : str
        Name of checkpoint
        Format is: 'tile_type.site_index.site_type.bel.primitive'
        Example:   'CLBLL_L.0.SLICEL.A5FF.FDCE'
    tile_list : [ Tile, ... ]]
        List of tiles to use (already have primitives placed in them).
    is_port : int
        1 = is a port, 0 = is not a port
    """
    tile_type, site_index, site_type, bel, primitive = checkpoint.split(".")
    if is_port == 1:
        primitive="PORT"
    cell_count = 0
    count = len(tile_list)
    db = bel_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][site_index]["SITE_TYPE"][site_type]
    for x in range(int(args.random_count)):
        # random properties
        #print(cell_count)
        random_properties(tile_list[cell_count], site_index, site_type, bel, primitive)
        # Do random site pip
        if len(db["SITE_PIP"].keys()) != 0:
            SP = random.choice(list(db["SITE_PIP"].keys()))
            if "INV" not in SP:
                V = random.choice(list(db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys()))
                create_site_pip(tile_list[cell_count],site_index,SP,V)
            elif "CLK" in SP:
                if tile_type not in ["BRAM_L","BRAM_R"]:
                    V = random.choice(list(db["SITE_PIP"][SP]["SITE_PIP_VALUE"].keys()))
                    create_site_pip(tile_list[cell_count],site_index,SP,V)
        cell_count = get_next_count(cell_count,count,checkpoint)
    #gen_bitstream(checkpoint)


def run_tcl_script(tcl_file):
    os.system("vivado -mode batch -source data/" + fuzz_path + "/" + tcl_file + " -stack 2000")

def set_ft(fp):
    """
    Set this module's global 'ft' variable.

    This is a global in another module - this imports it to be a global here.

    Parameters
    ----------
    fp : file
        Open file
    """
    global ft
    ft = fp

def set_args(in_args):
    """
    Set this module's global 'args' variable

    This is a global in another module - this imports it to be a global here.

    Parameters
    ----------
    in_args : argparse args structure
        Command line args
    """
    global args
    args = in_args


def run_data_generator(in_fuzz_path,in_args):
    """
    Run the fuzzer and then run Vivado to process all the TCL files generated.

    Parameters
    ----------
    in_fuzz_path : str
        Numbered sub-directory in '<family>/<part>/data' whre work is being done
    in_args : argparse args structure
        Command line args
    """
    global tile_type, fuzz_path, args
    tile_type = in_args.tile_type[0]
    fuzz_path = in_fuzz_path
    args = in_args
    # Run the actual fuzzer code to create TCL files
    fuzzer()
    if int(args.tilegrid) != 2:
        # Run the generated TCL scripts in Vivado
        fileList = os.listdir("data/" + fuzz_path + "/")
        fileList[:] = [x for x in fileList if ".tile" not in x]
        if int(args.parallel) == 0:
            for file in fileList:
                if ".tcl" in file:
                    run_tcl_script(file)
        else:
            pool = Pool(processes=int(args.parallel))
            pool.map(run_tcl_script, fileList)
        fileList = os.listdir("data/" + fuzz_path + "/")
        for file in fileList:
            if ".tcl" in file and ".tile" in file:
                run_tcl_script(file)
    else:  # args.tilegrid==2 means only run tilegrid.
        fileList = os.listdir("data/" + fuzz_path + "/")
        for file in fileList:
            if ".tcl" in file and ".tile" in file:
                print("FILE TO RUN:",file.replace(".tile",""))
                run_tcl_script(file.replace(".tile",""))
                run_tcl_script(file)
