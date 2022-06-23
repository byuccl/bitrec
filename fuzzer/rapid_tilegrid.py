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

import random
import json
import jpype
import jpype.imports
import pickle
import os
from jpype.types import *

import data_generator as dg
#from data_analysis import parse_feature_file
#jpype.startJVM(classpath=["rapidwright-2021.1.1-standalone-lin64.jar"])

from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.bitstream import ConfigArray
from com.xilinx.rapidwright.bitstream import Bitstream
from com.xilinx.rapidwright.bitstream import BlockType
from com.xilinx.rapidwright.bitstream import Frame

def get_int_tile_dict():
    """
    Build dictionary int_tile_dict.

    Structure of int_tile_dict: { int: int, ... } where first int is the TILE_Y for an INT tile
    and the second is Y coordinate of the corresponding tile in the dg.tilegrid  dictionary % 50 or 60, depending on family.
    Curiously, most of the keys are negative numbers such as: -320696 for "INT_L_X0Y0".
    Looks to be a translation table for the row numbers of INT tiles and is based on it being 7 series vs. Ultrascale.
    By the way, these match the TILE_Y entries in the final tilgrid.json file (both computed here and in bitrec/byu_db).

    Global Effects
    --------------
    Creates and initializes the int_tile_dict data structure.
    """
    global args, int_tile_dict
    int_tile_dict = {}
    for T in dg.tilegrid:
        if dg.tilegrid[T]["TYPE"] in ["INT_L", "INT_R", "INT"]:
            if args.family in ["artix7","spartan7","kintex7","virtex7"]:
                int_tile_dict[dg.tilegrid[T]["TILE_Y"]] = dg.tilegrid[T]["Y"]%50
            else:
                int_tile_dict[dg.tilegrid[T]["TILE_Y"]] = dg.tilegrid[T]["Y"]%60


def get_byte_offset(RT):
    """
    Calculate the offset to the bits for a tile.

    Parameters
    ----------
    RT : Device.Tile
        The tile in  question.

    Returns
    -------
    int
        The offset to the start of the bits for this tile.  
        This is the value that gets stored in the "offset" field of the "bits" in the tilegrid.json file.
    """
    global args, int_tile_dict
    T = str(RT)
    height = dg.tilegrid[T]["HEIGHT"]
    if args.family in ["artix7", "spartan7","kintex7","virtex7","zynq7"]:
        crc = [50]
        if height == 2:
            int_y = dg.tilegrid[T]["TILE_Y"]
        elif height%2 == 0:
            int_y = dg.tilegrid[T]["TILE_Y"] - int(height/4*3200) + 1600
        else:
            int_y = dg.tilegrid[T]["TILE_Y"] - (int(height/4))*3200
        words_per_int = 2
    elif args.family in ["kintexu","zynqu","virtexu"]:
        crc = [60,61,62]
        int_y = dg.tilegrid[T]["TILE_Y"]
        words_per_int = 2
    else:
        crc = [90,91,92,93,94,95]
        int_y = dg.tilegrid[T]["TILE_Y"]
        words_per_int = 3
    
    if int_y not in int_tile_dict:
        absolute_difference_function = lambda list_value : abs(list_value - int_y)
        int_y = min(int_tile_dict, key=absolute_difference_function)
        offset = int_tile_dict[int_y] * words_per_int
    else:
        offset = int_tile_dict[int_y] * words_per_int
    tile_type = str(RT.getTileTypeEnum())
    if tile_type in ["HCLK_IOI3","HCLK_L_BOT_UTURN","HCLK_L","HCLK_R_BOT_UTURN","HCLK_R"]:
        print("IN TILE:",T,tile_type)
        offset = 50
    elif offset >= crc[0]:
        offset += len(crc)
    print(T,offset)
    return offset


def init_rapidwright(part_name):
    """
    Set the device global and create a design for it.

    Parameters
    ----------
    part_name : str
        Name of the part to use.
    """
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)

def get_blocks():
    """
    Calculate the "bits" part of the tilegrid and update that into the existing tilegrid's JSON file.

    Global Effects
    --------------
    None.

    """
    global device, args

    fj = open("vivado_db/tilegrid.json")
    tilegrid = json.load(fj) 
    fj.close()
    # Reset the tilegrid if needed (remove all the "bits" entries)
    for x in tilegrid:
        if "bits" in tilegrid[x]:
            tilegrid[x].pop("bits",None)

    # Create a com.xilinx.rapidwright.bitstream.Configarray object
    # From RW docs: "Represents the array of configuration blocks that configures the device. It is composed of an array of ConfigRows, each of which is an array of config Blocks."
    C = ConfigArray(device)
    none_tiles = set()
    tile_bit_data = {}
    row_data = {}
    col_data = {}
    # device.getTiles(): "Gets and returns this device's 2D array of tiles that define the layout of the FPGA.": Tile[][].
    for row in device.getTiles():
        for T in row:
            try:
                # "C.getConfigBlock(): Gets the configuration block that corresponds to the provided tile and block type.": Block
                Block = C.getConfigBlock(T,BlockType.CLB)
                # Ex.: "CLBLL_L_"
                base = str(T).split("X")[0]
                # Block.getAddress(): "Gets the configuration block address as used in the Frame Address Register (FAR)."
                address = hex(Block.getAddress())
                # Tile.getRow() -> int
                tile_row = T.getRow()
                row_data[tile_row] = hex(0xFFFFFFFF0000 & int(address,16))
                # Tile.getColumn() -> int
                col = T.getColumn()
                col_data[col] = hex(0xFFFF & int(address,16))
                x = str(T)
                tilegrid[x]["bits"] = {"CLB_IO_CLK":{}}
                tilegrid[x]["bits"]["CLB_IO_CLK"]["baseaddr"] = address
                tilegrid[x]["bits"]["CLB_IO_CLK"]["frames"] = Block.getFrameCount()
                tilegrid[x]["bits"]["CLB_IO_CLK"]["offset"] = get_byte_offset(T)
                tilegrid[x]["bits"]["CLB_IO_CLK"]["words"] = tilegrid[x]["HEIGHT"]
                if "BRAM" in x:
                    Block = C.getConfigBlock(T,BlockType.BRAM_CONTENT)
                    tilegrid[x]["bits"]["BLOCK_RAM"] = {}
                    tilegrid[x]["bits"]["BLOCK_RAM"]["baseaddr"] = hex(Block.getAddress())
                    tilegrid[x]["bits"]["BLOCK_RAM"]["frames"] = Block.getFrameCount()
                    tilegrid[x]["bits"]["BLOCK_RAM"]["offset"] = tilegrid[x]["bits"]["CLB_IO_CLK"]["offset"]
                    tilegrid[x]["bits"]["BLOCK_RAM"]["words"] = tilegrid[x]["bits"]["CLB_IO_CLK"]["words"]
            except:
                base = str(T).split("X")[0]
                none_tiles.add(base)
                continue    
    for cr in row_data:
        print(cr,row_data[cr])

    prev = -1
    add_cols = {}
    for x in col_data:
        cur = int(col_data[x],16)>>7
        if cur != prev + 1:
            print("NOT",cur,prev,x,col_data[x])
            add_cols[x-2] = hex((prev+1)<<7)  
        prev = cur
    for x in add_cols:
        col_data[x] = add_cols[x]

    for col in col_data:
        print(col,col_data[col])

    
    #col_data[78] = "F80" # Need to figure this out CLK_HROW_TOP_R
    if "7" in args.family:
        ls1 = ["INT_R","RIOI3","RIOI3_TBYTETERM","RIOI3_TBYTESRC","RIOI3_SING","HCLK_R"]
        ls2 = ["INT_L","LIOI3","LIOI3_TBYTETERM","LIOI3_TBYTESRC","LIOI3_SING","HCLK_L"]
        ls1 += ["CMT_TOP_L_LOWER_B","CMT_TOP_L_UPPER_T","CMT_FIFO_L","HCLK_CMT_L","HCLK_R_BOT_UTURN"]
        ls2 += ["CMT_TOP_R_LOWER_B","CMT_TOP_R_UPPER_T","CMT_FIFO_R","HCLK_CMT","HCLK_L_BOT_UTURN"]
        ls = ls1+ls2

        clk_tiles = ["HCLK_IOI3","CLK_BUFG_REBUF","CLK_HROW_TOP_R","CLK_HROW_BOT_R","CLK_BUFG_TOP_R","CLK_BUFG_BOT_R"]

        for i in range(2):
            for x in tilegrid:
                if tilegrid[x]["TYPE"] in ls:
                    T = device.getTile(x)
                    tile_row = T.getRow()
                    row_d = row_data[tile_row]
                    col = T.getColumn()
                    col_d = None
                    direction = -1
                    if tilegrid[x]["TYPE"] in ls1:
                        direction = 1
                    for i in range(5):
                        offset = col+(direction*i)
                        if offset in col_data:
                            col_d = col_data[offset]
                            col_data[col] = col_d
                            break
                    
                    if col_d == None:
                        print(T,None)
                    else:
                        address = int(row_d,16) | int(col_d,16)
                        tilegrid[x]["bits"] = {"CLB_IO_CLK":{}}
                        tilegrid[x]["bits"]["CLB_IO_CLK"]["baseaddr"] = hex(address)
                        tilegrid[x]["bits"]["CLB_IO_CLK"]["frames"] = 42
                        tilegrid[x]["bits"]["CLB_IO_CLK"]["offset"] = get_byte_offset(T)
                        tilegrid[x]["bits"]["CLB_IO_CLK"]["words"] = tilegrid[x]["HEIGHT"]
            ls = clk_tiles


    for x in none_tiles:
        print(x)
    #names = set()
    base_dict = {}

    fj = open("vivado_db/tilegrid.json", 'w')
    json_database = json.dumps(tilegrid, indent=2, sort_keys=True)
    print(json_database, file=fj)
    fj.close()






def run_tilegrid_solver(in_args):
    """
    Finish tilegrid.json

    This follows the running of the "get_db.tcl" script infuzzer.py.  That script creates a tilegrid.json file.
    This routine adds the "bits" part to the already-existing tilegrid.json file.
    This uses RW to provide the info.  The old method did it all with TCL, which was much slower.

    Parameters
    ----------
    in_args : argparser args object
        Contains the command line args.
    """
    global args, tile_type, tile_dict, primitive_map, nets, ft, specimen_number
    #tile_type = in_args.tile_type[0]
    args = in_args
    dg.set_args(in_args)

    # Set device and create design.
    init_rapidwright(args.part)

    # Build a row number lookup table for all the INT_L, INT_R, INT tiles.
    get_int_tile_dict()

    get_blocks()

    print("Done with run_tilegrid_solver...")

