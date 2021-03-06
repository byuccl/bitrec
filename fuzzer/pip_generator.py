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

import json
import os
import argparse
import sys
import random
import pickle
import data_generator as dg
from data_analysis import parse_feature_file


##================================================================================##
##                                  PIP FUZZER                                    ##
##================================================================================##

def create_pip_design():
    global tile_dict, ft
    cell_count = 0
    site_pin_cell_pin_dict = {}
    site_pin_bel_pin_dict = {}
    primitive_placement_dict = {}
    ft = open("data/" + fuzz_path + "/pip.tcl","w",buffering=1)
    dg.set_ft(ft)
    print("source ../../record_device.tcl",file=ft)
    print("source ../../drc.tcl",file=ft)
    print("source ../../fuzz_pip.tcl",file=ft)
    print("set ::family " + args.family,file=ft)
    print("set part_name " + args.part,file=ft)
    dg.init_design()
    place_tile_types = ["CLBLL_L","CLBLL_R","CLBLM_L","CLBLM_R","CLE_M_R","CLE_M","CLEL_L","CLEL_R"]
    for tile_type in tile_dict["TILE_TYPE"].keys():
        for i in tile_dict["TILE_TYPE"][tile_type]["SITE_INDEX"].keys():
            tile_list = []
            for T in dg.tilegrid:
                if tile_type == dg.tilegrid[T]["TYPE"]:
                    if "IS_BONDED" not in dg.tilegrid[T] or dg.tilegrid[T]["IS_BONDED"] == True:
                        tile_list.append(T)

            db = tile_dict["TILE_TYPE"][tile_type]["SITE_INDEX"][i]
            site_pins = db["SITE_PINS"]
            
            placement_dict = {}
            for j in db["SITE_TYPE"].keys():
                for BP in db["SITE_TYPE"][j]["BEL_PINS"]:
                    if j in ["RAMB36E1","FIFO36E1"]: # RAMB36 and FIFO36E1 [get_site_pins of bel_pins] doesn't return the correct site pin - SP name matches BP though
                        if tile_type + "." + i + "." + SP not in site_pin_bel_pin_dict:
                            site_pin_bel_pin_dict[tile_type + "." + i + "." + BP] = [j + "." + BP]
                        else:
                            site_pin_bel_pin_dict[tile_type + "." + i + "." + BP] += [j + "." + BP]
                    else:
                        for SP in db["SITE_TYPE"][j]["BEL_PINS"][BP]:
                            if tile_type + "." + i + "." + SP not in site_pin_bel_pin_dict:
                                site_pin_bel_pin_dict[tile_type + "." + i + "." + SP] = [j + "." + BP]
                            else:
                                site_pin_bel_pin_dict[tile_type + "." + i + "." + SP] += [j + "." + BP]
                if "BEL" in db["SITE_TYPE"][j]:
                    for B in db["SITE_TYPE"][j]["BEL"].keys():
                        if B not in ["A5LUT","B5LUT","C5LUT","D5LUT"]:
                            chosen_primitive = ""
                            pins = []
                            pin_length = 0
                            for P in db["SITE_TYPE"][j]["BEL"][B]["PRIMITIVE"].keys():
                                if P not in ["PORT"]:    
                                    if len(db["SITE_TYPE"][j]["BEL"][B]["PRIMITIVE"][P]) > pin_length:
                                        pins = db["SITE_TYPE"][j]["BEL"][B]["PRIMITIVE"][P]
                                        pin_length = len(pins)
                                        chosen_primitive = P
                            placement_dict[B] = chosen_primitive
                            # I may need to factor in the needed bel pin into this
                            primitive_placement_dict['.'.join([tile_type,i,j,B])] = chosen_primitive
            # Only place CLB tiles - others as needed
            if tile_type in tile_type in place_tile_types:                
                for B in placement_dict:
                    P = placement_dict[B]
                    if P != "":
                        checkpoint_name = tile_type+"."+i+"."+j+"."+B+"."+P 
                        cell_name_str = ""
                        placement_str = ""
                        for x in range(len(tile_list)):
                            cell_name_str += "C_" + str(cell_count) + " "
                            placement_str += dg.place_cell_str(tile_list[x],i,B,cell_count) + " "
                            cell_count += 1
                        dg.create_cells(P, cell_name_str)
                        dg.pre_placement_drc(checkpoint_name,tile_list)
                        dg.place_cells(placement_str)
    #DRC Fixes
    dg.post_placement_drc(1)
    fs = open("vivado_db/site_pin_dict.txt","w",buffering=1)
    fj = open("vivado_db/placement_tcl_dict.txt","w",buffering=1)
    dg.write_checkpoint("vivado_db/pip")
    os.system("vivado -mode batch -source data/" + fuzz_path + "/pip.tcl -stack 2000")
    site_pin_dict = ""
    for x in site_pin_bel_pin_dict:
        site_pin_dict += x + " {"
        for y in site_pin_bel_pin_dict[x]:
            site_pin_dict += y + " "
        site_pin_dict += "} "
    print(site_pin_dict,file=fs) 
    fs.close()

    
    placement_tcl_dict = ""
    for x in primitive_placement_dict:
        if primitive_placement_dict[x] != "":
            placement_tcl_dict += x + " " + primitive_placement_dict[x] + " "
    print(placement_tcl_dict,file=fj) 
    fj.close()




def check_pip_files():
    global fuzz_path, pip_dict
    fileList = os.listdir("data/" + fuzz_path + "/")
    for file in sorted(fileList):
        if ".tile" not in file and ".bit" not in file and ".dcp" not in file and ".ft" in file:
            if os.path.exists("data/" + fuzz_path + "/" + file.replace(".ft", '.bit')):
                specimen, tile_type, pip_ext, ext = file.split(".")
                # Parse Feature file
                f = open("data/" + fuzz_path + "/" + file)
                tile_feature_dict = parse_feature_file(f, fuzz_path + "." + specimen, tile_type)
                print("PARSED FEATURE")
                f.close()
                for T in tile_feature_dict:
                    if tile_type in T:
                        for F in tile_feature_dict[T]:
                            if F not in pip_dict:
                                pip_dict[F.split(".")[-1]] = set(tile_feature_dict[T])
                            else:
                                pip_dict[F.split(".")[-1]] = set(tile_feature_dict[T]) - pip_dict[F]
    print("PRINTING PIP DICT:")
    for F in pip_dict:
        print(F,len(pip_dict[F]),pip_dict[F])


def get_tile_list(tile_type):
    fj = open("vivado_db/tilegrid.json")
    tilegrid = json.load(fj) 
    fj.close()
    tile_list = []
    max_x = 0
    max_y = 0
    for T in tilegrid:
        if tilegrid[T]["TYPE"] == tile_type:
            tile_list.append(T)
    return tile_list

def fuzz_pips():
    global tile_dict, ft, tile_type, specimen_number
    pips_per_bitstream = 80
    
    ft = open("data/" + fuzz_path + "/fuzz_pips.tcl","w",buffering=1)
    dg.set_ft(ft)
    print("source ../../record_device.tcl",file=ft)
    print("source ../../drc.tcl",file=ft)
    dg.open_checkpoint("vivado_db/pip")
    dg.disable_drc()
    print("source ../../fuzz_pip.tcl",file=ft)
    print("set ::family " + args.family,file=ft)
    print("set part_name " + args.part,file=ft)
    #for tile_type in bel_dict["TILE_TYPE"].keys():
    #tile_type = "INT_L"
    print("init_pip_fuzzer " + tile_type,file=ft)

    tile_list = get_tile_list(tile_type)
    count = 0
    values = list(dg.bel_dict["TILE_TYPE"][tile_type]["TILE_PIP"].keys())
    random.shuffle(values)
    random.shuffle(tile_list)
    for P in values:
        if P not in pip_dict or len(pip_dict[P]) <= 1:
            print("create_route " + P + " [list] " + tile_list[count],file=ft)
            count += 1
            if count >= pips_per_bitstream:
                count = 0
                dg.pip_bitstream_drc()
                #write_checkpoint("data/" + fuzz_path + "/" + str(specimen_number) + ".pips")
                print("record_device_pips data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.ft",file=ft)
                dg.write_bitstream("data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.bit")
                specimen_number+=1
                dg.open_checkpoint("vivado_db/pip")
                print("init_pip_fuzzer " + tile_type,file=ft)
    dg.pip_bitstream_drc()
    print("record_device_pips data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.ft",file=ft)
    dg.write_bitstream("data/" + fuzz_path + "/" + str(specimen_number) + "." + tile_type + ".pips.bit")
    specimen_number+=1
    os.system("vivado -mode batch -source data/" + fuzz_path + "/fuzz_pips.tcl")
    
        # parse all feature files
    # repeat with while loop

def run_pip_generator(in_fuzz_path,in_args):
    global fuzz_path, args,tile_type, tile_dict, pip_dict, specimen_number
    tile_type = in_args.tile_type[0]
    fuzz_path = in_fuzz_path
    args = in_args
    dg.set_args(in_args)

    fj = open("vivado_db/tile_dict.json")
    tile_dict = json.load(fj) 
    fj.close()

    # Instead of created a placed/routed design, need to iteratively create it...
    pip_dict = {}
    if os.path.exists("vivado_db/pip.dcp") == False:
        create_pip_design()
    if int(args.fuzzer) == 1:
        specimen_number = 0
        count = 0
        while (count < 10):
            fuzz_pips()
            check_pip_files()
            count += 1
