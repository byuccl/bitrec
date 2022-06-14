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
import pickle
#from bit_parser import print_frame
from bit_parser import parse_bitstream

from jpype.types import *
#import data_generator as dg

from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim
from com.xilinx.rapidwright.design.tools import LUTTools
luttools = LUTTools()

##==========================================##
##            DIFF ANALYSIS                 ##
##==========================================##


def load_pkl_obj(file_name):
    pkl_obj = {}
    if os.path.exists(file_name):
        with open(file_name, 'rb') as handle:
            pkl_obj = pickle.load(handle)
    return pkl_obj


def save_pkl_obj(file_name, pkl_obj):
    with open(file_name, 'wb') as handle:
        pickle.dump(pkl_obj, handle, protocol=pickle.HIGHEST_PROTOCOL)


def print_dict(dict_obj, f):
    if f == None:
        for F in dict_obj:
            print(F, dict_obj[F])
    else:
        for F in dict_obj:
            # for x in dict_obj[F]:
            print(F, dict_obj[F], file=f)

def eqn_to_init(eqn):
    #print(eqn)
    pin_map = {'A6': 'I5', 'A5': 'I4','A4': 'I3','A3': 'I2','A2': 'I1','A1': 'I0'}
    if "(0)" in eqn:
        eqn_str = "64\'h0"
    elif "(1)" in eqn:
        if "O6=" in eqn:
            eqn_str = "64\'hFFFFFFFFFFFFFFFF"
        else:
            eqn_str = "64\'h00000000FFFFFFFF"
    elif "O6=0x" in eqn: 
        eqn_str = eqn.split("0x")[-1]
        eqn_str = "64\'h" + str(eqn_str)
    elif "O6=" in eqn: 
        for key in pin_map.keys():
            eqn = eqn.upper().replace(key, pin_map[key])
        eqn = eqn.replace("O6=","O=")
        eqn_str = luttools.getLUTInitFromEquation(eqn,6)
        eqn_str = str(eqn_str)
    elif "O5=0x" in eqn:  
        eqn_str = eqn.split("0x")[-1]
        eqn_str = "32\'h" + str(eqn_str)
    elif "O5" in eqn:  
        for key in pin_map.keys():
            eqn = eqn.upper().replace(key, pin_map[key])
        eqn = eqn.replace("O5=","O=")
        eqn_str = luttools.getLUTInitFromEquation(eqn,5)
        eqn_str = str(eqn_str)
    elif "64" in eqn:
        #print("Returning eqn str:",eqn)
        eqn_str = eqn
    else:
        print("\tUNKNOWN EQN:",eqn)
        eqn_str = "64\'h0"
    #print("\t",eqn_str)
    return eqn_str

def parse_feature_file(f, specimen, tile_type):
    """
    Parse feature file and build data structure tile_feature_dict.

    Feature file is listing of features.  This dict simply groups all from same tile together into one dictionary entry.

    Parameters
    ----------
    f : file
        Opened feature file.
    specimen : int
        Specimen number.
    tile_type : str
        Ex.: "DSP_R"

    Returns
    -------
    tile_feature_dict
        tile_feature_dict = { 
            'CLB.0005.0.DSP_R_X9Y195': [
                'C:0:DSP48E1:DSP48E1:ACASCREG:1',
                'C:0:DSP48E1:DSP48E1:ADREG:1',
                'C:0:DSP48E1:DSP48E1:AUTORESET_PATDET:NO_RESET',
                ...
                ],
            'CLB.0005.0.DSP_R_X35Y195': [
                'C:0:DSP48E1:DSP48E1:ACASCREG:2',
                'C:0:DSP48E1:DSP48E1:MASK:![0]',
                ...
                ],
            ...
        }
    """
    print(f)
    tile_feature_dict = {}
    content = f.readlines()
    content = [x.strip() for x in content]
    for line in content:
        vals = line.split(":", 1)
        # only grab features for target tile type
        if tile_type + "_X" in vals[0]:
            config_bus = "CLB"
            if tile_type in ["BRAM_L", "BRAM_R", "BRAM"]:
                vals2 = vals[1].split(":")
                if len(vals2) == 5:
                    if "RAMB" in vals2[2]:
                        if "INIT" in vals2[3] and vals2[3] not in ["INIT_A", "INIT_B", "EN_SDBITERR_INIT_V6"]:
                            config_bus = "BLO"
            if config_bus+"."+specimen+"."+vals[0] not in tile_feature_dict:
                tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] = []
            if "EQN" in vals[1]:
                eqn = vals[1].rsplit(":",1)[-1]
                init = eqn_to_init(vals[1].rsplit(":",1)[1])
                vals[1] = vals[1].rsplit(":",1)[0] + ":" + init
                #print(eqn,init,vals[1])
            if "\'h" in vals[1]:
                base, num = vals[1].rsplit(":", 1)
                count, num = num.split("\'h")
                num = int(num, 16)
                mask = 1
                for i in range(int(count)):
                    if num & mask:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":["+str(i)+"]"]
                    else:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":!["+str(i)+"]"]
                    mask = mask << 1
            elif "\'b" in vals[1]:
                base, num = vals[1].rsplit(":", 1)
                count, num = num.split("\'b")
                num = int(num, 2)
                mask = 1
                for i in range(int(count)):
                    if num & mask:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":["+str(i)+"]"]
                    else:
                        tile_feature_dict[config_bus+"."+specimen+"."+vals[0]] += [config_bus[0]+":"+base+":!["+str(i)+"]"]
                    mask = mask << 1
            else:
                tile_feature_dict[config_bus+"."+specimen +"."+vals[0]] += [config_bus[0]+":"+vals[1]]

    # Combine 5LUT and 6LUT properties
    if "CLB" in tile_type or "CLE" in tile_type:
        for T in tile_feature_dict:
            #print("DATA:",tile_feature_dict[T])
            tmp = tile_feature_dict[T].copy()
            for F in tile_feature_dict[T]:
                if "5LUT" in F and "EQN" in F:
                    #print("\tHas 5lut:",F)
                    bus, site, site_type, bel, config, val = F.split(":")
                    bel6 = bel.replace("5","6")
                    new_val = ":".join([bus, site, site_type, bel6, config, val])
                    old_vals = []
                    if "!" in val:
                        old_vals.append(":".join([bus, site, site_type, bel6, config, val.replace("!","")]))
                        old_vals.append(":".join([bus, site, site_type, bel6, config, val]))
                        old_vals.append(F)
                    else:
                        old_vals.append(":".join([bus, site, site_type, bel6, config, "!" + val]))
                        old_vals.append(":".join([bus, site, site_type, bel6, config, val]))
                        old_vals.append(F)
                    #print("VALS:",old_vals,new_val)
                    for x in old_vals:
                        if x in tmp:
                            tmp.remove(x)
                    if new_val not in tmp:
                        tmp.append(new_val)
            tile_feature_dict[T] = tmp.copy()
            #print("\tNew data:",tile_feature_dict[T])
    return tile_feature_dict


def parse_files():
    """
    Load bitstreams, feature file contents into data structures and then write .pkl files containing both
    bitstream and feature file info.
    """
    global fuzz_path
    file_count = 0
    fileList = os.listdir("data/" + fuzz_path + "/")
    for file in sorted(fileList):
        # Parse just bitstream files
        if ".tile" not in file and ".bit" in file and ".dcp" not in file:
            print(file)
            file_count += 1

            # Parse Bitstream
            if int(args.pips) == 1:
                specimen, tile_type, pip_ext, ext = file.split(".")
            else:
                specimen, tile_type, site_index, site_type, bel, primitive, ext = file.split(".")
            f = open("data/" + fuzz_path + "/" + file, "rb")
            tile_bit_dict = parse_bitstream(f, args.family, tilegrid, tile_type, fuzz_path + "." + specimen)
            print("PARSED BIT")
            f.close()

            # Parse Feature file
            f = open("data/" + fuzz_path + "/" + file.replace(".bit", '.ft'))
            tile_feature_dict = parse_feature_file(f, fuzz_path + "." + specimen, tile_type)
            print("PARSED FEATURE")
            f.close()

            # Write out pkl file consisting of [ parsedFeatures, bitstreamFeatures ]
            save_pkl_obj("data/" + fuzz_path + "/" + file.replace("bit","pkl"), [tile_feature_dict, tile_bit_dict])


def get_solved_bel_bits(bel_dict,tile_type):
    bel_bits = set()
    if tile_type in ["INT_L","INT_R"]:
        for x in ["CLBLL_L","CLBLM_L","CLBLL_R","CLBLM_R"]:
            fj = open("db/db."+tile_type+".json")
            tile_bel_dict = json.load(fj) 
            fj.close()
            bel_bits |= get_solved_bel_bits(tile_bel_dict,x)
        bel_bits |= {"0_48","0_12","0_16","0_44","0_36","0_52","0_56","0_32","0_8","0_16","0_0","0_4","0_20","0_24","0_28"}
        bel_bits |= {"1_3","1_7","1_19","1_47","1_39","1_51","1_55","1_35","1_15","1_31","1_11", "1_43","1_59","1_27","1_23"}
    else:
        bel_bits = set()
        if (type(bel_dict) is dict):
            if "BUS" in bel_dict and bel_dict["BUS"] == "BLOCK_RAM":
                return bel_bits
            for key in bel_dict:
                if key != "TILE_PIP":
                    bel_bits |= get_solved_bel_bits(bel_dict[key],tile_type)
        elif (type(bel_dict) is list):
            for x in bel_dict:
                bel_bits |= set(b.replace("!","") for b in x)
    return bel_bits



def condense_data():
    """
    Process all the data in all the .pkl files into a different set of data strucutures

    Returns
    -------
    features : list
        A list of ALL the features turned on across ALL the tiles in ALL the specimens
        [ 'C:1:DSP48E1:CARRYININV:CARRYIN', 'C:Tile_Pip:DSP_R.DSP_IMUX44_0->DSP_1_A22', ...]
    bits : list
        A list of ALL the bits turned on across ALL the tiles in ALL the specimens
        [ '27_288', '27_19', 24_219', ...]
    feature_dict: dict
        Mapping from feature name to feature number where feature number corresponds to index in 'features' list.
        { 'C:1:DSP48E1:CARRYININV:CARRYIN': 0, 'C:Tile_Pip:DSP_R.DSP_IMUX44_0->DSP_1_A22': 1, ...}
    bit_dict: dict
        Mapping from bit name to bit number where bit number corresdponds to index in 'bits' list.
        { '27_288': 0, '26_43': 1, ... }
    tile_data : dict
        For a given tile, lists all the bits turned on in it and the features configured in it.
        { 'CLB.0005.0.DSP_R_X9Y95' : 
                { 'bits': [115, 40, 460, 250],
                  'features': [162, 739, ...]
                }
          'CLB.0005.0.DSP_R_X35Y40': ..
        }
    tile_data_rec: dict
        For a given feature number, list all the tiles it is set in
        { 0: ['CLB.0005.0.DSP_R_X9Y195', 'CLB.0005.0.DSP_R_X35Y195', , ... ],
          1: ['CLB.0005.14.DSP_R_X9Y195', 'CLB.0005.14.DSP_R_X35Y195', ... ]
        }
    """
    global feature_dict,tile_data_rev
    fileList = os.listdir("data/" + fuzz_path + "/")
    features = set()
    bits = set()
    data = {}
    tile_data = {}
    
    # Create the features and bits data structures (see description in docstring above)
    for file in sorted(fileList):
        if ".pkl" in file:
            tile_feature_dict, tile_bit_dict = load_pkl_obj("data/" + fuzz_path + "/" + file)
            #print("OUTPUT:",tile_feature_dict)
            #print("BIT:",tile_bit_dict)
            for x in tile_feature_dict:
                features = features | set(tile_feature_dict[x])
                bits |= set(tile_bit_dict[x])

    # TODO The next 6 lines of code are iterating across sets (which are unordered).
    # This assumes the enumerate ordering in the for loops will be the same order they end up in 25 lines below 
    # when they are turned into lists.
    # Shouldn't the conversion to lists happen before the next 6 lines of code?
    feature_dict = {}
    bit_dict = {}
    # Make mappings from feature names to feature numbers
    # E.g. feature_dict['C:1:DSP48E1:CARRYININV:CARRYIN'] = 0, feature_dict['C:Tile_Pip:DSP_R.DSP_IMUX44_0->DSP_1_A22'] = 1, ...
    for i,f in enumerate(features):
        feature_dict[f] = i
    # Make mappings from bit names to bit numbers
    # E.g. bit_dict['27_288'] = 0, bit_dict['26_43'] = 1, ...
    for i,b in enumerate(bits):
        bit_dict[b] = i

    # Create the tile_data data structure (see description in docstring above)
    for file in sorted(fileList):
        if ".pkl" in file:
            tile_feature_dict, tile_bit_dict = load_pkl_obj("data/" + fuzz_path + "/" + file)
            for x in tile_feature_dict:
                #print("\t",x)
                tile_data[x] = {}
                tile_data[x]["bits"] = []
                tile_data[x]["features"] = []
                for y in tile_feature_dict[x]:
                    tile_data[x]["features"].append(feature_dict[y])
                for y in tile_bit_dict[x]:
                    tile_data[x]["bits"].append(bit_dict[y])
    features = list(features)
    bits = list(bits)

    # Create the tile_data_rev data structure (see desciption in docstring above)
    tile_data_rev = {}
    for x in range(len(features)):
        tile_data_rev[x] = []

    for x in tile_data:   # Ex.: 'CLB.0005.0.DSP_R_X9Y195'
        for y in tile_data[x]["features"]:
            tile_data_rev[y] += [x]    

    #for x in tile_data_rev:
    #    print(x,tile_data_rev[x])

    return tile_data, features, bits, feature_dict, tile_data_rev


def sensitivity_analysis(tile_data):
    """
    Create list of bits always ON for each feature.

    Parameters
    ----------
    tile_data : dict
        For a given tile, lists all the features turned on in that tile and all the bits turned on in that tile.
        Keys are names.  Ex: CLB.0005.0.DSP_R_X9Y195"   (bus . fuzz_path . specimen . tile)
        Values are: { 'bits': [ 116, 140, 461, ... ],
                       'features': [ 162, 739, 642, ...]
                    }
    Returns
    -------
    solved_feature_dict = 
                { 0: set(onBit, onBit, ...), 
                  1: set(onBit, onBit, ...),
                  2: set(onBit, onBit, ...),
                            ...
                }
        For feature[k], solved_feature_dict[k] contains set of bits always ON for feature[k]
    """
    global tile_type, features, bits, tile_data_rev, args
    solved_feature_dict = {}
    
    # 1. foreach feature, initialize solved_feature_dict with first tile's set of bits on for that feature
    for F in tile_data_rev:
        print("INIT",F,features[F],tile_data_rev[F][0],list(bits[b] for b in tile_data[tile_data_rev[F][0]]["bits"]))
        solved_feature_dict[F] = set(tile_data[tile_data_rev[F][0]]["bits"])

    # 2. Find 'always on' bits by AND-ing rest of bits found when that feature is on
    if tile_type in ["BRAM_L", "BRAM_R", "BRAM"]:
        # if it is a bram, the bus needs to match
        for T in tile_data:
            bit_set = set(tile_data[T]["bits"])
            for F in tile_data[T]["features"]:
                if features[F][0] == T[0]:
                    solved_feature_dict[F] = solved_feature_dict[F] & bit_set
    else:
        for T in tile_data:
            # Get a set of all bits turned on in a tile.  Ex.: the bits in 'CLB.0005.0.DSP_R_X9Y195'
            bit_set = set(tile_data[T]["bits"])
            for F in tile_data[T]["features"]:
                #if "INT_L.SS6END2->>WW2BEG2" in features[F]:
                #    print("AND",solved_feature_dict[F],bit_set)

                # Foreach feature, perform AND of new bits with initialized mask from above
                # When done, this leaves behind all the bits that are ALWAYS on when a particular feature is present
                solved_feature_dict[F] = solved_feature_dict[F] & bit_set
    
    print("SOLVED FEATURE DICT")
    for x in solved_feature_dict:
        # x is the feature index
        #   features[x] = 'C:0:DSP48E1:DSP48E1:AREG:0'   (name of feature)
        #   solved_feature_dict[x] = {3, 5, 6}     (indices into bits[] of bits always on for feature)
        #   bits[3:7] = ['26_261', '27_214', '0_227', '26_249']   (bits those map to)
        print(x, features[x], "\n  ", solved_feature_dict[x], "\n  ", list(bits[b] for b in solved_feature_dict[x]))

    # Return set of bits that are always ON for each feature
    return solved_feature_dict


def sensitivity_analysis_v2(tile_data):
    """
    Perform the alternate sensitivity analysis.

    What is being done is looking for a pair of tiles, T1 and T2, 
        whose sets of on features only differ by exactly one feature/
    That is, if feature set T1 - feature set T2 results in one additional feature, 
        that tells us what bits program the additional feature.

    TODO: It would seem it should also look for T2 - T1 ?  
    See issue #18.

    Parameters
    ----------
    tile_data : _type_
        _description_

    Returns
    -------
    _type_
        _description_
    """
    global tile_type, features, solved_feature_dict
    solved_feature_dict = {}

    # BEN - commented out (default not used)
    # default = list(tile_data.keys())[0]
    # tile_data_keys = [ 'CLB.0005.0.DSP_R_X9Y195', 'CLB.0005.0.DSP_R_X35Y70', ... ]
    tile_data_keys = list(tile_data.keys())
    for i in range(len(tile_data_keys)):
        T1 = tile_data_keys[i]
        # TODO: Where does "BLO." occur?
        if "BLO." not in T1:
            for j in range(i+1, len(tile_data_keys)):
                T2 = tile_data_keys[j]
                if "BLO." not in T2:
                    diff_features = set(tile_data[T1]["features"]) - set(tile_data[T2]["features"])
                    #print(T1,T2,diff_features)
                    if len(diff_features) == 1:
                        diff_bits = set(tile_data[T1]["bits"]) - set(tile_data[T2]["bits"])
                        for x in diff_features:
                            solved_feature_dict[x] = diff_bits
                            print(T1, T2, list(features[x] for x in diff_features), list(bits[x] for x in diff_bits))

    return solved_feature_dict


def remove_lut_bits(solved_feature_dict):
    global tile_type, features, bits, tile_data_rev, args
    print("REMOVING LUT BITS:")
    if tile_type in ["CLEL_L","CLEL_R","CLEM_R","CLEM","CLE_M"]:
        lut_bits = set()
        for F in solved_feature_dict: 
            f = features[F].rsplit(":", 1)[0]
            if "6LUT" in f:
                lut_bits |= solved_feature_dict[F]
        print("LUT BITS:",list(bits[x] for x in lut_bits))
        for F in solved_feature_dict: 
            f = features[F].rsplit(":", 1)[0]
            if "6LUT" not in f:
                print("Removing:",features[F],list(bits[x] for x in solved_feature_dict[F]))
                solved_feature_dict[F] = solved_feature_dict[F] - lut_bits
                print("Now:",features[F],list(bits[x] for x in solved_feature_dict[F]))
        
    return solved_feature_dict

def filter_bits(solved_feature_dict):
    """
    Remove PIP bits (if doing BELs) or BEL bits (if doing PIPs) and then build feature sets and possible values.

    Parameters
    ----------
    solved_feature_dict : dict(featureNum: setOfBits)
       For each featureNum specifies the bits that are always on for it

    Returns
    -------
    feature_sets : dict(propertyName:setOfBits)
        For each property (not property:value pair) specify all bits that were on for ANY of its values minus
            the bits that were on for ALL of its values
    possible_values : dict(propertyName, [ value1, value2, ...])
        For each property specify ALL the possible values it may have
    """
    global tile_type, features, bits, tile_data_rev, args
    possible_values = {}
    feature_sets = {}
    # Doing BEL properties, remove the PIP bits
    if int(args.pips) != 1:
        pip_bits = set()
        # Get set of all bits involved with tile pips
        for i in range(len(features)):
            if "Tile_Pip" in features[i]:
                pip_bits = pip_bits | solved_feature_dict[i]
        # Remove the tile pip bits from all other features' bits (they represent bit pollution)
        for i in range(len(features)):
            if features[i][0] != "B":   # Don't do BRAM bus features
                solved_feature_dict[i] = solved_feature_dict[i] - pip_bits
        if "7" not in args.family:
            solved_feature_dict = remove_lut_bits(solved_feature_dict)
        # Create the per-property sets of bits
        always_bits = {}
        for F in solved_feature_dict:
            f = features[F].rsplit(":", 1)[0]
            v = features[F].rsplit(":", 1)[1]
            if f not in feature_sets:
                feature_sets[f] = set(solved_feature_dict[F])
                always_bits[f] = set(solved_feature_dict[F])
                possible_values[f] = [v]
            else:
                # What is set of bits have you seen on for ANY values of this property?
                feature_sets[f] |= solved_feature_dict[F]
                # What is set of bits have you seen on for ALL values of this property?
                always_bits[f] &= solved_feature_dict[F]
                # Tabulate possible values for this property
                possible_values[f] += [v]
#            if f == testProp:
#                print(F, testProp, v, feature_sets[f], always_bits[f], possible_values[f])
#        print("\nFeature sets: ", feature_sets)
#        for k,v in feature_sets.items():
#            print(k, v)
#        print("\n\nAlways bits: ")
#        for k,v in always_bits.items():
#            print(k, v)
#        print("\nPossible values: ")
#        for k,v in possible_values.items():
#            print(k, v)
        # Remove the bits that were always on for ALL values of property from a given property:value
        for f in feature_sets:
            feature_sets[f] = feature_sets[f]-always_bits[f]
        if "7" not in args.family:
            for f in feature_sets:
                if "[" in possible_values[f][0]:
                    for x in possible_values[f]:
                        bit_set = feature_sets[f]
                        for y in possible_values[f]:
                            if x!=y:
                                bit_set = bit_set - solved_feature_dict[features.index(f + ":" + y)]
                        solved_feature_dict[features.index(f + ":" + x)] = bit_set

    else: # Doing PIP bits, remove the BEL bits
        
        if os.path.exists("db/db."+tile_type+".json") == 0:
            print("[YRAY ERROR]: BEL Fuzzer needs to be run before Pip Fuzzer")
        fj = open("db/db."+tile_type+".json")
        tile_bel_dict = json.load(fj) 
        fj.close()
        bel_bits = get_solved_bel_bits(tile_bel_dict,tile_type)
        bel_bit_idx = set()
        for x in bel_bits:
            if x in bits:
                bel_bit_idx.add(bits.index(x))
        print("BEL BITS:",bel_bits)
        print("BEL BITS:",bel_bit_idx)
        for i in range(len(features)):
            if features[i][0] != "B" and "Tile_Pip" in features[i] and i in solved_feature_dict:
                solved_feature_dict[i] = solved_feature_dict[i] - bel_bit_idx
        # Create the per-pip mux set of bits (Pips that have the same destination)
        always_bits = {}
        for F in solved_feature_dict:
            print(F)
            f = features[F].rsplit(">", 1)[1]
            v = features[F].rsplit(">", 1)[0]
            if f not in feature_sets:
                print("INIT",f,solved_feature_dict[F])
                feature_sets[f] = set(solved_feature_dict[F])
                always_bits[f] = set(solved_feature_dict[F])
                possible_values[f] = [v]
            else:
                print("AND",f,solved_feature_dict[F])
                feature_sets[f] |= solved_feature_dict[F]
                always_bits[f] &= solved_feature_dict[F]
                possible_values[f] += [v]
        #print("FEATURE SETS:")
        # Hardcoded filter: Pips in range 0-25 are in the INT_L/R tiles
        if "7" in args.family:
            if "INT" not in tile_type:
                min_frame = 0
                max_frame = 25
                #for f in feature_sets:
                #    feature_sets[f] = feature_sets[f]-always_bits[f]
            else:
                min_frame = 26
                max_frame = 255
            for f in feature_sets:
                tmp = set()
                for b in feature_sets[f]:
                    if min_frame <= int(bits[b].split("_")[0]) <= max_frame:
                        tmp.add(b)
                feature_sets[f] = feature_sets[f]-tmp


    print("FEATURE SETS:")
    for f in feature_sets:
        print(f,list(bits[b] for b in feature_sets[f]))
    return (feature_sets, possible_values)
    

class Feature():
    def __init__(cls, feat_str):
        '''
        C:0:DSP48E1:INMODE0INV:INMODE0
        C:0:DSP48E1:DSP48E1:BREG:1
        '''
        data = feat_str.split(':')

        # Tile pip
        if len(data) == 1:
            cls.bus = "CLB_IO_CLK"
            cls.type = "TILE_PIP"
            return
        elif len(data) == 2:
            cls.type = "TILE_PIP_OF_BEL"
            return

        if len(data) < 4:
            print(f"Data too short {feat_str}", file=sys.stderr)
        if data[0] == 'C':
            cls.bus = "CLB_IO_CLK"
        elif data[0] == 'B':
            cls.bus = "BLOCK_RAM"
        else:
            print(f"Invalid bus when creating feature with string {feat_str}")
        cls.site_idx = data[1]
        cls.site_type = data[2]
        if len(data) == 5:
            cls.type = "BEL"
            cls.bel = data[3]
            cls.prop = data[4]
        elif len(data) == 4:
            cls.type = "SITE_PIP"
            cls.site_pip = data[3]
        else:
            print(f"Error making Feature class. Bad string: {feat_str}")


def get_bits(tile_data, property_bit_set, featureIndices, propertyPossibleValues):
    """
    _summary_

    Parameters
    ----------
    tile_data : _type_
        _description_
    property_bit_set : set
        All the bits on for ANY value of this property
    featureIndices : list
        List of indices of the features that pertain to this property.  
        This and the next list go together.  
        This one holds the indices of the 'n' features (property:value) for this property.
        The next one holds the 'n' values.
    possibleValues : list
        List of possible values for this property.  

    Returns
    -------
    _type_
        _description_
    """
    global tile_data_rev
    ret = {}
    for v in propertyPossibleValues:
        ret[v] = set()
    # Go through every feature associated with the propery of interest
    for idx,f in enumerate(featureIndices):  
        # Go through every tile associated with the feature 'f'
        for T in tile_data_rev[f]:
        #if f in tile_data[T]["features"]:
            # Get ALL the bits turned on in this tile
            allTheTileBits = tile_data[T]["bits"]
            # For the bits associated with all values of this property,
            #   - If they are turned on in this tile, include them 
            #        - they are configuring feature 'f'
            #   - If they are not turned on in this tile, include their negation 
            #        - They must be used to configure another value for this property
            tmp = [bits[x] if x in allTheTileBits else f"!{bits[x]}" for x in property_bit_set]
            tmp.sort()
            # Add the resulting bits.  If already exists, will not add it a second time.
            ret[propertyPossibleValues[idx]].add(tuple(tmp))
    for k, v in ret.items():
        ret[k] = tuple(v)
    #print(bit_set,features,vals,ret)
    return ret

def merge_json(db,bel_dict):
    if (type(bel_dict) is dict):
        for key in bel_dict:
            if key not in db:
                #print("ADDED KEY:",key,bel_dict[key])
                db[key] = bel_dict[key]
            else:
                db[key] = merge_json(db[key],bel_dict[key])
    #else:
    #    db = bel_dict
    return db



def add_missing_features(db):
    global tile_type
    if int(args.pips) != 1:
        fj = open("vivado_db/bel_dict.json")
        bel_dict = json.load(fj) 
        fj.close()
        tile_bel_dict = bel_dict["TILE_TYPE"][tile_type]
    else:
        if os.path.exists("db/db."+tile_type+".json") == 0:
            print("YRAY ERROR: BEL Fuzzer needs to be run before Pip Fuzzer")
        fj = open("db/db."+tile_type+".json")
        tile_bel_dict = json.load(fj) 
        fj.close()

    db = merge_json(db,tile_bel_dict)
    print("FINISHED MERGE")
    return db



def second_analysis(tile_data, properties, values, solved_feature_dict):
    """
    _summary_

    Parameters
    ----------
    tile_data : dict
        For a given tile, lists all the bits turned on in it and the features configured in it.
        { 'CLB.0005.0.DSP_R_X9Y95' : 
                { 'bits': [115, 40, 460, 250],
                  'features': [162, 739, ...]
                }
          'CLB.0005.0.DSP_R_X35Y40': ..
        }
    properties : dict(propertyName:setOfBits)
        For each property (not property:value pair) specify all bits that were on for ANY of its values minus
            the bits that were on for ALL of its values
    values : dict(propertyName, [ value1, value2, ...])
        For each property specify ALL the possible values it may have
    solved_feature_dict : dict(featureNum: setOfBits)
       For each featureNum specifies the bits that are always on for it

    Returns
    -------
    _type_
        _description_
    """
    global feature_dict
    res = {"SITE_INDEX": {}, "TILE_PIP": {}}
    sites = res["SITE_INDEX"]
    for feature, bit_set in properties.items():
        if feature == testProp:
            print("Second analysis", feature)
        feat = Feature(feature)
        if feat.type == "TILE_PIP":
            prop_rules = {}
            vals = values[feature]
            print("TOP",feature,vals)
            #if feature not in res["TILE_PIP"]:
                #print("\tINIT RES",feature)
                #res["TILE_PIP"][feature] = {"INPUTS":{}}
            feature_strs = []
            prop_rules = {}
            for v in vals:
                print("\tPIP SECOND",feature,v)
                feature_str = v + ">" + feature
                pip_name = feature_str.split(":")[1]
                bit_pip_set = solved_feature_dict[feature_dict[feature_str]]
                print("\tBITS:",bit_pip_set)
                bit_pip_set = properties[feature]
                print("\tBIT SET 2:",bit_pip_set)
                feature_strs = [feature_dict[feature_str]]
                v = v.split(".")[1]
                prop_rules.update(get_bits(tile_data, bit_pip_set, feature_strs, [v]))
            for x in prop_rules:
                print("\tSetting",x,prop_rules[x])
                #res["TILE_PIP"][feature]["INPUTS"][x] = {"BITS":prop_rules[x]}
                res["TILE_PIP"][x + ">" + feature] = {"BITS":prop_rules[x]}
        elif feat.type == "TILE_PIP_OF_BEL":
            # Don't solve for pips in the bel fuzzer
            continue
        else:    # Is of type BEL
            if feat.site_idx not in sites:
                sites[feat.site_idx] = {"SITE_TYPE": {
                    feat.site_type: {"BEL": {}, "SITE_PIP": {}}}}
            elif feat.site_type not in sites[feat.site_idx]["SITE_TYPE"]:
                sites[feat.site_idx]["SITE_TYPE"][feat.site_type] = {
                    "BEL": {}, "SITE_PIP": {}}
            site_info = sites[feat.site_idx]["SITE_TYPE"][feat.site_type]
            if feat.type == "SITE_PIP":
                feature_strs = []
                vals = values[feature]
                for v in vals:
                    feature_strs.append(feature_dict[f"{feature}:{v}"])
                prop_rules = get_bits(tile_data, bit_set, feature_strs, vals)
                site_info["SITE_PIP"][feat.site_pip] = {
                    "SITE_PIP_VALUE": prop_rules}
            elif feat.type == "BEL":
                if feat.bel not in site_info["BEL"]:
                    site_info["BEL"][feat.bel] = {"CONFIG": {}}
                bel_info = site_info["BEL"][feat.bel]["CONFIG"]
                vals = values[feature]
                if '[' not in vals[0]:
                    feature_strs = []
                    # Build list of indices for all features (property:value pairs) associated with this property
                    for v in vals:
                        feature_strs.append(feature_dict[f"{feature}:{v}"])
                    # Decide which bits get included and which get inverted
                    prop_rules = get_bits(tile_data, bit_set, feature_strs, vals)
                    bel_info[feat.prop] = {"VALUE": prop_rules, "BUS": feat.bus}
                else:
                    prop_rules = {}
                    for v in vals:
                        if "!" not in v:
                            feature_str = (f"{feature}:{v}")
                            bit_hex_set = solved_feature_dict[feature_dict[feature_str]].symmetric_difference(solved_feature_dict[feature_dict[feature_str.replace("[","![")]])
                            feature_strs = [feature_dict[feature_str]]
                            prop_rules.update(get_bits(tile_data, bit_hex_set, feature_strs, [v]))
                    bel_info[feat.prop] = {"VALUE": prop_rules, "BUS": feat.bus}
    return res

##==========================================##
##            APPEND DATABASE               ##
##==========================================##


def run_data_analysis(in_fuzz_path, in_args):
    global fuzz_path, args, tile_type, tilegrid, bel_dict, feature_dict
    global bits, features
    global testProp
    tile_type = in_args.tile_type[0]
    fuzz_path = in_fuzz_path
    args = in_args

    print("Starting Differential Analysis")

    fj = open("vivado_db/tilegrid.json")
    tilegrid = json.load(fj)
    fj.close()
    fj = open("vivado_db/bel_dict.json")
    bel_dict = json.load(fj)
    fj.close()

    testProp = 'C:0:DSP48E1:DSP48E1:AUTORESET_PATDET'

    # In the comments in this file:
    #   The word 'property' refers to a BEL property as in: 'C:1:DSP48E1:DSP48E1:ADREG'
    #   The word 'feature' refers to a property:value combo as in 'C:1:DSP48E1:DSP48E1:ADREG:0'

    # 1. Load bitstreams, feature file contents into data structures and then write .pkl files containing both
    #    bitstream and feature file info.
    parse_files()

    # 2. Convert .pkl files into data structures used for data analysis.
    #    See comments in condense_data() docstrings for details on data structures
    tile_data, features, bits,feature_dict,tile_data_rev = condense_data()

    # 3. Foreach feature, create list of bits ALWAYS on when that feature is on
    if tile_type in ["INT_L","INT_R","INT"] or int(args.pips) != 1:
        solved_feature_dict = sensitivity_analysis(tile_data)
    else:
        solved_feature_dict = sensitivity_analysis_v2(tile_data)

    # 4. Make list of all the bits that affect each property
    #    Make a second list of the possible values for each property
    #    See docstring in filter_bits for details on properties and values
    properties, values = filter_bits(solved_feature_dict)
    print(properties,values)
    
    db = second_analysis(tile_data, properties, values,solved_feature_dict)

    db = add_missing_features(db)

    
    fj = open("db/db."+tile_type+".json", 'w')
    json_database = json.dumps(db, indent=2, sort_keys=True)
    print(json_database, file=fj)
    fj.close()
    print("DONE")
    return

