

# THE PY FUZZER

# 1. Quick Start Guide  

## 1.1 Requirements
* Currently supported **Python 3.8.10**
* **Vivado 2020.2** is installed and sourced: 
```
source /tools/Xilinx/Vivado/2020.2/settings64.sh   # To setup Vivado
```

* RapidWright 2021.2.0 - this file needs to be installed within the `bitrec/fuzzer` folder (on the same level as `run_snapshot.py`)  
```
cd cd bitrec/fuzzer
wget https://github.com/Xilinx/RapidWright/releases/download/v2021.2.0-beta/rapidwright-2021.2.0-standalone-lin64.jar
```

## 1.2 Initial Sanity Check Run

Run the fuzzer for the DSP_L tile, targeting the artix7 using the default part xc7a100ticsg324-1L

```
cd bitrec/fuzzer
python3 run_snapshot.py --family=artix7 --tile=DSP_L
```

- This will take approximately 30 minutes to run (depending on the machine). 
- It will generate about 56 bitstreams in the directory `artix7/xc7a100ticsg324-1L/data/0000`. 
- Final output products (the database entries derived by the fuzzer) will be found in `artix7/xc7a100ticsg324-1L/db/db.DSP_L.json` where the actual bit numbers for the various features have been filled in.
- Errors such as "*Site <xxx> cannot be sitetype ...*" are expected at the beginning of the fuzzer. 

The first time you run the fuzzer for a family the program `get_db.tcl` will be run, which will generate the required file structure, as well as 4 json dictionaries for the fuzzer to use.  These files can be found in `artix7/xc7a100ticsg324-1L/db/vivado-db`.  Of the 30 minutes of time mentioned above, about half is for creating this initial file structures and the four files.  Subsequent runs do not require this step.

## 1.3 File Structure
After completing the above run, the following file structure will result:

📦artix7  
┗ 📂xc7a100ticsg324-1L  
┃ ┣ 📂checkpoints  
┃ ┃ ┣ 📜DSP_L.0.DSP48E1.DSP48E1.DSP48E1.dcp  
┃ ┃ ┗ 📜DSP_L.1.DSP48E1.DSP48E1.DSP48E1.dcp  
┃ ┣ 📂data  
┃ ┃ ┣ 📂0000  
┃ ┃ ┃ ┣ 📜0.DSP_L.0.DSP48E1.DSP48E1.DSP48E1.bit  
┃ ┃ ┃ ┣ 📜0.DSP_L.0.DSP48E1.DSP48E1.DSP48E1.ft  
┃ ┃ ┃ ┣ 📜0.DSP_L.0.DSP48E1.DSP48E1.DSP48E1.pkl  
┃ ┃ ┃ ┣ 📜27.DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tile.bit  
┃ ┃ ┃ ┣ 📜27.DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tile.ft  
┃ ┃ ┃ ┣ 📜DSP_L.0.DSP48E1.DSP48E1.DSP48E1.tcl  
┃ ┃ ┃ ┣ 📜DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tcl  
┃ ┃ ┃ ┗ 📜DSP_L.1.DSP48E1.DSP48E1.DSP48E1.tile.tcl  
┃ ┃ ┃ ┗ etc..  
┃ ┣ 📂db  
┃ ┃ ┣ 📜db.DSP_L.json  
┃ ┣ 📂fuzzer_data  
┃ ┗ 📂vivado_db  
┃ ┃ ┣ 📜bel_dict.json  
┃ ┃ ┣ 📜init.dcp  
┃ ┃ ┣ 📜primitive_dict.json  
┃ ┃ ┣ 📜tile_dict.json  
┃ ┃ ┗ 📜tilegrid.json  

## 1.4 Continuing On
Each tile type could be individually fuzzed by executing the command above with a different tile type and that is often done.  

However, the sections below show how to do all tile types at once, as well as the options available to the `run_snapshot.py` program.
<hr>

# 2. The `run_snapshot.py` Program

## 2.1 Overview
The `run_snapshot.py` program is a python script which is used to drive the actual fuzzer (`fuzzer.py`).  It contains lists of tile types to be fuzzed for a variety of parts from 7 Series, Ultrascale, and Ulstrascale+.  For each tile type it provides reasonable default parameters.

There are two major types of fuzzing to be done.  The first is called *BEL fuzzing* and deals with the configurable properties on BELs.  Two typical examples of such configurable BEL properties are: (a) the FFINIT property for a SLICE flip flop and (b) the EQN property used to initialize the contents of an A6LUT in a SLICE. 

The second type of fuzzing to be done is called *PIP fuzzing* and is used to fuzz the PIPs in INT tiles.


## 2.2 BEL Fuzzing

To fuzz the basic cells in the artix7 family, run the following (this will take 12+ hours):  

```
python3 run_snapshot.py --family=artix7
```

Examining the code for `run_snapshot.py` shows this will do the following tile types: CLBLL_L, CLBLL_R, 
CLBLM_L, CLBLM_R, DSP_L, DSP_R, BRAM_L BRAM_R, INT_L, INT_R, LIOI3, RIOI3, LIOB33, RIOB33, 
CMT_FIFO_L, CMT_FIFO_R, CFG_CENTER_MID, CLK_HROW_BOT_R, CLK_HROW_TOP_R, CLK_BUFG_BOT_R, CLK_BUFG_TOP_R, 
HCLK_CMT_L, HCLK_CMT, HCLK_IOI3.  These represent the most commonly used tile types.  
   
The extended tile types could be added to the list by executing:
```
python3 run_snapshot.py --family=artix7 --extended=1
```

This will add the following additional tile types: "LIOI3_TBYTESRC,
LIOI3_TBYTETERM, LIOI3_SING, RIOI3_TBYTESRC, RIOI3_TBYTETERM, RIOI3_SING, LIOB33_SING, RIOB33_SING, MONITOR_BOT, PCIE_BOT, GTP_CHANNEL_0, GTP_COMMON.

As can be seen, this is not all the tile types in the 7 Series but represents those solved for thus far.

A similar examination of the `run_snapshot.py` program will show what tile types can be fuzzed in the Ultrascale and Ultrascale+ families.

### 2.2.1 Run Snapshot Arguments
By default, `run_snapshot.py` will fuzz the basic tile types and nothing else.  From the arguments below it can be seen that there are parameters to prevent this (maybe you already did it previousoy) and also to fuzz the extended tiles or do PIP fuzzing.
<pre>
parser.add_argument('--family',default="spartan7")      # Selects the FPGA architecture family
parser.add_argument('--part',default="DEFAULT")         # Selects the FPGA part - family's default part is chosen if no part is given
parser.add_argument('--tilegrid_only',default="0")      # 1: Only runs the tilegrid generation for the part 0: Run both database and tilegrid generation
parser.add_argument('--basic',default="1")              # 1: Runs fuzzer on the basic set of tiles 0: doesn't run on the basic tiles
parser.add_argument('--extended',default="0")           # 1: Runs fuzzer on the extended set of tiles 0: only runs on the basic tiles
parser.add_argument('--pips',default="0")               # 1: Runs fuzzer on pips 0: dont run pip fuzzer
parser.add_argument('--tile',default="NONE")            # NONE: Runs all tiles, or <TILE_NAME> Will run only the single tile
</pre>

### 2.2.2 Explanatory Notes on BEL Fuzzing
- Every fuzzer run is family and part specific, so everything will be generated under a family and a part folder, in this case `artix7/xc7a100ticsg324-1L`.   
- Fuzzer data will be stored in the `data` folder. Every run of the fuzzer will create a new sequentially named folder, starting at `0000`. These files within the `0000` folder have the syntax of `specimen_number.TILE_TYPE.SITE_INDEX.SITE_TYPE.BEL.PRIMITIVE.extension`.  
- The next tile will have its results placed into `0001` and so on.
- The fuzzer will attempt to place all possible primitives on every site-type/BEL combination.  As it does this it will generate a collection of designs (specimens), each represented by a bitstream (.bit) file.  
- The .ft files are the textual representation of each such design.  The .bit file is the bitstream for the design, and the .pkl file containes a Python pickled array of two elements, containing the combination of the .ft and .bit files, but on a per-tile basis.   
- The .tcl files are the scripts generated by the fuzzer and which are run by Vivado to generate all of the specimen designs within the folder.
- The .tile files are the specimens that are specific to solving for the tilegrid - designs whose differences are limited to a single column in the device.  
- The checkpoint designs are the placed and routed designs and are located in the `checkpoints` folder.  
- The `db` folder contains the final output of the fuzzer with one JSON file per tile type. 
- The `vivado_db` folder contains several files used by the fuzzer. 
   - `init.dcp` - this is the "initialized" state of the FPGA for the targeted part. The fuzzer will open this checkpoint as opposed to re-creating a new empty design for speedup purposes.  
   - `bel_dict.json` - this contains a dictionary of all tile types, their sites and respective site types, and all BELs and their respective properties.  
   - `primitive_dict.json` - this contains a list of every primitive with all cell properties and their possible values.  
   - `tile_dict.json` - This contains a dictionary of every tile type, their sites and respective site types, and what primitives are place-able on every BEL.   Additionally, all cell pins are shown with their respective BEL pins.  
   - `tilegrid.json` - this contains a dictionary of every tile, all grid coordinates, and bitstream address information. This is the important file for bitstream->netlist purposes.  
- The final database (such as that found in `bitrec/byu_db`) consists of two things: (1) all the .json files from the `artix7/xc7a100ticsg324-1L/db` directory and (2) the `tilegrid.json` file from the `artix7/xc7a100ticsg324-1L/vivado_db` directory.


## 2.3 PIP Fuzzing
The above BEL fuzzing process solves for not only BEL properties but also site pips (sometimes also known as routing PIPs).  However, it does not solve for tile PIPs (what we normally think of as general routing pips in the interconnect of an FPGA).  PIP fuzzing specifically solves for those kinds of PIPs.

For 7 Series parts only INT_L and IN T_R tiles need to have pip fuzzing done (it would be INT tiles for Ultrascale and US+).  To fuzz INT_L for 7 Series you would execute:
```
python3 run_snapshot.py --family=artix7 --tile=INT_L --pips=1
```
This takes approximately 8-21 hours on one our lab machines.  Why the variation?  

Imagine fuzzing a single PIP.  To do so the tools run a net through that PIP that originates in a site pin in some tile and terminates in another site pin in the same or a different tile.  The challenge is it can become difficult to have the PIP being fuzzed be the only  thing turned on in the INT tile or interest.  For example, if the only way to get a net run through a PIP is to also run it through another PIP in the same tile then the analysis won't be able to distinguish the bits for the two PIPs since they are always programmed together.  

What the PIP fuzzer does is first to attempt to fuzz all the PIPs.  It then goes through and does an analysis of whether the prior run resulted in data which was able to fully distinguish the bits for the various PIPs it fuzzed. Those that still are not distinguishable are left on the list and another iteration of the algorithm is run.  After each iteration the tool prints out how many PIPs are not yet fully solved for.  

As an example, for the 7 Series and the INT_L tile, it takes 21 hours to run 25 iterations.  When it is finished, there are still 95 pips which it is not able to prove it has fully solved (but it may have).  The current approach is to run for some extended period of time (some set number of iterations), realizing that there still may be some ambiguity on some PIPs. See the comments below ("PIP Fuzzer Additional Explanation") for more details on this ambiguity.  
   
As mentioned above, the PIP Fuzzer runs for some number of iterations (20 is the default for INT_L and INT_R in 7 Series).  When running, if you would like to stop it iterating, you can create a file named "STOP" in the location the fuzzer is working in (`0001` for example).  At the end of the current iteration the program will see this file, quit iterating even if the `pip_list` is not empty, process what it has thus far, and write the results into the database files.  Thus, you can cause it to gracefully finish early if you get tired of waiting for all the iterations to complete. 

### 2.3.1 Vivado Crashes When Fuzzing PIPs
Vivado segfaults every once in a while when fuzzing PIPs and we have never able to consistently recreate it.  What we have found is "if you do too much in a single TCL script it may segfault".  Segfaults just mean that all of the data for that iteration didn't get process.  But the design of the program is such that the next iteration will pick up where the current iteration left off and complete the needed work.  So, the segfaults are not a problem.

### 2.3.2 PIP Fuzzer Additional Explanation
The PIP fuzzer works by sitting in a while loop.  In each execution of the loop it will iterate over every unsolved PIP and will generate 1 net that traverses through each such PIP. When done, it will check "if each PIP can be unambiguously distinguished from all other PIPs", which means that for each PIP it is the only thing used within the tile, or if another PIP is used then it will need to create a net with the target PIP plus a different used PIP using either (1) a different mux, or (2) an example of each PIP within the same mux (where a PIP mux is defined as all of the PIPs with the same destination node). The while loop will then repeat, generating a new net to further disambiguate all currently ambiguous PIPs, and then break once all PIPs are disambiguated. 

Also, in Vivado a "PIP junction" is what we mean when we say "PIP mux", that is: "a collection of PIPs that all share a destination, where the bitstream bits select what source is being used (a mux...)". However, Vivado doesn't consider a PIP junction a "first class object", so they are inaccessible when it comes to the TCL interface.

The upshot of all this is if you don't run the PIP fuzzer for long enough - the `len(pip_list)` in `run_pip_generation()` never reaches 0, then there is a chance that those PIPs left in the `pip_list` data structure are not going to be fully solved (there will be pollution - extra bits from other independent PIPs within the equation).

But it is just *a chance* they are not fully solved.  To understand why consider pip "A1" where the only way to reach pip A1 is to traverse PIP junction B (junction B's destination node is PIP A1's source node).  Further consider that junction A and B are within the same tile. Junction B has 3 different inputs B1-B3, controlled by bitstream bits X, Y and Z. Consider if junction B's rules are:
```
B1: XY
B2: XZ
B3: Z
```
Our goal is to have examples within our data set of 'B1 A1', 'B2 A1' and 'B3 A1', but we were never able to create 'B3 A1' because of either DRC check violations, or maybe this 'B3 A1' is a difficult complete net to create (think routing difficulty because B3 could only be connected in the INT_L tile on the top of the FPGA or something like that).  In this case it will never be removed from the pip_list and the while loop will never exit. 

The rule for A1 will think that X is a part of A1 because it was never "toggled within our data set". (we saw XY and XZ in addition to the A1 bits).  So to completely disambiguate A1, we need to see it in conjunction with all three cases of B1-B3.  However, we won't know the rules for junction B until we solve for them, so we can only settle on "at least one example of each".  But, if we were able to generate an example of 'B1 A1' and 'B3 A1', but not 'B2 A1', then we are fine because we will have seen X toggle - hence the statement above regarding the "chance of it not being solved for".  That is, there is also a chance that it was solved for".  Most pip junctions have ~23 different sources, so hitting 20 of the 23 is usually sufficient but not guaranteed.

# 3. Database Gaps
There are known gaps in the coverage of the database:

1. DRC Property Fixes   
   Not all configurations of a primitive are valid. These invalid combinations of configurations are enumerated in the DRC checks under the "AVAL" group of DRC checks (under All Rules, Netlist, Instance, Invalid attribute value, in the DRC report window). These DRC checks may be supressed, and Vivado will still generate a valid bitstream, however the issue is that the properties that Vivado reports for a given bel will not match the contents of the bitstream. Essentially, the bel properties can be in an invalid state, and Vivado will generate a bitstream ,ignoring some of these properties to fit it back into a valid state, and the only indication of vivado "ignoring bel properties" are in the DRC AVAL checks. This check is harder to identify. Turning on AVAL drc checks is a good way, as well as incorporating hardcoded fixes to ensure the invalid property combinations are never met.  

2. DRC Placement Fixes  
   These rules have to do with being able to generate a bitstream or not. For a given primitive, there exists rules that need to be followed to place the primitive in a valid manner. The difference from "DRC Property Fixes" is that the bitstream generation won't even run if these rules are invalid. Some example rules are LUTRAMs, where to place a LUTRAM on a A6LUT bel, you also have to place a LUTRAM on the D6LUT. Failed bitstreams are a good indication of failing this check. Solutions to this problem have to be hardcoded and based on experience, DRC checks, and documentation.  

3. Dependent Bits  
   There exist bits that configure multiple properties at the same time. One example is in the DSP_L tile, where the ACASCREG and AREG need to be the same value at all times (values 0, 1 or 2), except for in the case where ACASCREG=1, then AREG can equal 2. There exists a single set of bits to choose between AREG equaling 0, 1 or 2, as to be expected. However there exist no bits to indicate the values of ACASCREG, and instead there exists a bit that is 1 for the special case when ACASCREG == AREG, and 0 otherwise. This case in the DSP (along with the BCASCREG/BREG properties), is the only current example we have, but this may occur in other tiles as well (possibly many). For future work, the solution is to have a second pass at the differential analysis, running on just the bits that were never associated with a property, and search for all situations that the bit was on, and off. A more complex algorithm can then deduce the dependency. Fixing this situation would also fix others that we have not yet detected.  

4. "Polluted" PIP bits  
   This occurs when a property value's on bits have more than just the bits that configure the given feature, and in our current state of our fuzzer, is inseperable from the bits that configure a nearby PIP. This is due to the fact that our BEL Fuzzer doesn't solve for PIPs (a separate set of code, the PIP Fuzzer does). One solution is to incorporate Prjxray's database of bits, and filter those out of each property. Future work can also add a PIP fuzzer.  

5. Invisible Properties  
   This one is the hardest to detect, hardest to fix, and is always lurking in the background, because we don't know if it is localized to a few tiles, or if other tiles have similar properties. This occurs in at least 2 tile types we know of:
   - CMT_TOP_L/R_LOWER_B and CMT_TOP_L/R_UPPER_T
   - MMCM and PLL
I alkso more than likely occurs in the Phaser In and Phaser Out tiles as well.  This tile however is fairly low on the priorty list. 
   
   The issue is that, normally, BEL property values directly map onto bits that are written into the bitstream.  But, in the cases above, the BEL properties go through a "transformation phase" that is not visible to the user in any way. For example, properties that are encoded into the MMCM primitive, such as `delay_time`, `phase`, and `clk_cycle` are transformmed into different variables such as `high time`, `low time`, and `edge`. It is these later properties that are actually encoded into the bitstream.  The sign of this occurring is the property type of "double", where a property is given a string double type, however it is never directly written to the bitstream. 
   
   The only current solution to this for MMCM/PLL is by reading Xilinx documentation - XAPP888 for example.  From this we can deduce the memory mapping for the MMCM and PLLE2 primitives and future work can hard code this mapping directly into our database - Prjxray has essentially done the same. 
   
   However, no similar documentation for the Phase tiles has been found to date.  

# 4. Fuzzer.py Arguments  

Then filen `run_snapshot.py` is just a wrapper for `fuzzer.py`, using known working arguments for each tile - some tiles need more data than others, which is dependent on the number of BEL properties a tile contains. Some arguments are used for testing purposes, as well as rerunning portions of the fuzzer.  

However, `fuzzer.py` can be run directly without the use of `run_snapshot.py`.  Here are its arguments:

<pre>
parser.add_argument('tile_type', nargs=1)                   # Selects the target tile type
parser.add_argument('--family',default="spartan7")          # Selects the FPGA architecture family
parser.add_argument('--part',default="xc7s25csga324-1")     # Selects the FPGA part
parser.add_argument('--init',default=1)                     # 1:reinitialize checkpoint files, 0:use old checkpoints
parser.add_argument('--checkpoints',default=1)              # 1:Write checkpoint files for every bitstream
parser.add_argument('--fuzzer',default=1)                   # 1:Run data generation 0: skip data generation, just run differential analysis
parser.add_argument('--drc',default=0)                      # 1:Enable Vivado DRC checks, 0:Disable Vivado DRC Checks
parser.add_argument('--diff_folder',default="NONE")         # Specifiy a different folder to run diff analysis on - EX. "0011"
parser.add_argument('--verbose',default=0)                  # 1: Outputs initialized differential data and bitstream data to file
parser.add_argument('--tilegrid',default=1)                 # 1: Run if needed, 0: don't run, 2: only run tilegrid 
parser.add_argument('--iterative',default=1)                # 1: Runs iterative method, 0: random only
parser.add_argument('--random_count',default=200)           # Number of randomized cells to create
parser.add_argument('--tilegrid_count',default=2)           # Number of tilegrid specimens to create per column
parser.add_argument('--cell_count',default=510)             # Maximum number of tiles to use per bitstream
parser.add_argument('--site_count',default=100)             # Maximum number of sites to fuzz - useful for tiles with identical sites
parser.add_argument('--checkpoint_choice',default=-1)       # Site values of the checkpoint to open for the tilegrid fuzzer
parser.add_argument('--checkpoint_count',default=1)         # Number of different checkpoint files to run tilegrid generation on
parser.add_argument('--parallel',default=8)                 # Runs tile in parallel for N number of processes
parser.add_argument('--pips',default=0)                     # 1: Turns on the pip_fuzzer, 0: turns it off
</pre>


