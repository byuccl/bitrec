#!/usr/bin/env python3

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
import sys
import argparse
import random
import pickle
from time import sleep

import jpype
import jpype.imports
from jpype.types import *

# Next line needs to be run before any com.xilinx.rapidwright.. things can be imported (like in pips_rapid.py)
jpype.startJVM(classpath=["rapidwright-2021.2.0-standalone-lin64.jar"])

import pips_rapid
import data_analysis
import data_generator as dg
#from pip_generator import *
import rapid_tilegrid
#from tilegrid_solver import *


def make_folders():  
    if args.diff_folder != "NONE":
        return args.diff_folder
    for x in ["data","checkpoints","vivado_db","db", "fuzzer_data"]:
        try: 
            os.makedirs(args.family + "/" + args.part + "/" + x + "/", exist_ok=True)
        except OSError as error: 
            print(error)  
    for i in range(1000):
        if os.path.exists(args.family + "/" + args.part + "/data/" + str(i).zfill(4)) == False:
            os.mkdir(args.family + "/" + args.part + "/data/" + str(i).zfill(4))
            return str(i).zfill(4)

def prettyPrintJSON(fname):
    with open(fname) as fj:
        tmp = json.load(fj) 
    with open(fname, "w") as fj:
        json_database = json.dumps(tmp, indent=2,sort_keys=True)
        print(json_database,file=fj)


parser = argparse.ArgumentParser()
parser.add_argument('tile_type', nargs=1)                   # Selects the target tile type
parser.add_argument('--family',default="spartan7")         # Selects the FPGA architecture family
parser.add_argument('--part',default="xc7s25csga324-1")    # Selects the FPGA part
#parser.add_argument('--family',default="kintexu")           # Selects the FPGA architecture family
#parser.add_argument('--part',default="xcku025-ffva1156-2-e")# Selects the FPGA part
parser.add_argument('--init',default=1)                     # 1:reinitialize checkpoint files, 0:use old checkpoints
parser.add_argument('--checkpoints',default=1)              # 1:Write checkpoint files for every bitstream
parser.add_argument('--fuzzer',default=1)                   # 1:Run data generation 0: skip data generation, just run differential analysis
parser.add_argument('--drc',default=0)                      # 1:Enable Vivado DRC checks, 0:Disable Vivado DRC Checks
parser.add_argument('--diff_folder',default="NONE")         # Specifiy a different folder to run diff analysis on - EX. "0011"
parser.add_argument('--verbose',default=0)                  # 1: Outputs initialized differential data and bitstream data to file
parser.add_argument('--tilegrid',default=0)                 # 1: Run if needed, 0: don't run, 2: only run tilegrid 
parser.add_argument('--iterative',default=1)                # 1: Runs iterative method, 0: random only
parser.add_argument('--random_count',default=200)           # Number of randomized cells to create
parser.add_argument('--tilegrid_count',default=2)           # Number of tilegrid specimens to create per column
parser.add_argument('--cell_count',default=510)             # Maximum number of tiles to use per bitstream
parser.add_argument('--site_count',default=100)             # Maximum number of sites to fuzz - useful for tiles with identical sites
parser.add_argument('--checkpoint_choice',default=-1)       # Site values of the checkpoint to open for the tilegrid fuzzer
parser.add_argument('--checkpoint_count',default=1)         # Number of different checkpoint files to run tilegrid generation on
parser.add_argument('--parallel',default=8)                 # Runs tile in parallel for N number of processes
parser.add_argument('--pips',default=0)                     # 1: Turns on the pip_fuzzer, 0: turns it off
parser.add_argument('--pip_iterations',default=0)           # Number of iterations to run the pip fuzzer for

parser.add_argument("--vrbs", action='store_true')

args = parser.parse_args()
is_first_run = 0
if os.path.exists(args.family + "/" + args.part + "/vivado_db/init.dcp") == False:
    print("Running first time FPGA Family and Part Database generation")
    is_first_run = 1
    os.system("vivado -mode batch -source get_db.tcl -tclarg " + args.family + " " + args.part)
    prettyPrintJSON(args.family + "/" + args.part + "/vivado_db/primitive_dict.json")
    prettyPrintJSON(args.family + "/" + args.part + "/vivado_db/bel_dict.json")
    prettyPrintJSON(args.family + "/" + args.part + "/vivado_db/tilegrid.json")
    prettyPrintJSON(args.family + "/" + args.part + "/vivado_db/tile_dict.json")


top_fuzz_path = make_folders()
print("Running in directory: " + top_fuzz_path, file = sys.stderr)

os.chdir(args.family + "/" + args.part + "/")

# The data_generator module needs to pre-load a bunch of database files before it can do its work
dg.data_generator_init()

if is_first_run == 1:
    print("Running tilegrid solver...")
    rapid_tilegrid.run_tilegrid_solver(args)

if int(args.pips) == 1 and int(args.fuzzer) == 1:
    pips_rapid.run_pip_fuzzer(top_fuzz_path,args)
elif int(args.fuzzer) == 1:
    dg.run_data_generator(top_fuzz_path,args)
    
data_analysis.run_data_analysis(top_fuzz_path,args)
        
os.chdir("../..")

# Force exit
print(f"[LOG]: Exiting fuzzer for tile={args.tile_type}", file=sys.stderr)
os._exit(0)
