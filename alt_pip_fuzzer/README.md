# Alternate PIP Fuzzer Approach
This directory contains code investigating a more deterministic way to fuzz tile pips.  The motivation for it was the observation that the `pips_rapid.py` program (1) has to iterate to solve for pips and (2) it can never guarantee it has the right data to solve for all PIPs.  That is, running it for hundreds of iterations always leaves behind a few PIPs it is unable to be certain it has solved for.

The motivation for this new approach came from tracing out why some PIPs were never fully solved for (or at least the program was not certain they had not been solved for).  The observation was that for a single net running through a PIP in a tile, *if that PIP is the only PIP turned on in that tile* then it should be trivial to solve for that PIP's bits.

However, there are times when it requires that other PIPs are also on in the tile with the PIP of interest.  This is when these other PIPs are needed to connect signals up to the PIP of interest.  To handle this, the algorithm runs twice - that is, it routes nets through the PIP of interest but in two different tiles.  And, it ensures those two nets are ***disjoint*** in all respects.  Doing this should provide clear examples to determine the bits required for the PIP of interest.

Once such disjoint pairs of nets have been created for all PIPs of interest in the design, then they can be packed into chip designs, bitstreams generated, and the resulting bitstreams analyzed  to determine the bit rules for each PIP.

The work in this directory embodies the first two steps.  That is, `findPipPairs.py` creates disjoint net pairs for each PIP and writes the results to `pipresults.txt`.   Then, `placePipPairs.py` packs those net pairs into designs.  The resulting `packedresults.json` file specifies the nets to be placed into each design.

The advantage of this proposed approach is speed and determinism - the first step (`findPipPairs.py`) runs for all the PIPs in an INT_L tile in less than 20 minutes.  The `placePipPairs.py` step then runs in under a second.

The next step in this work would be to adapt the existing `pips_rapid.py` code to take the resulting net definitions and incorporate them into its Tcl/Vivado flow.   Since this step has not been done, this alternate PIP fuzzing approach has not been proven to work in all cases - and so that is the remaining work to be done.  

# Step 1: Running `findPipPairs.py`
A typical run would be:
```
python3 findPipPairs.py --pipfile=allpips.txt --startdepth=3
```
The tool performs the following steps:
1. Builds a list of PIPs to solve for from the provided `allpips.txt` file.
2. For every PIP in its list, searches uphill from the PIP, looking for site pins it can use as the driver for a net.  
In this work it enumerates *all* such uphill paths with a maximum length of 3 (due to the command line parameter).
3. If then identifies all pairs of these uphill paths that are disjoint and save them in a list.  By disjoint we mean they don't use the same PIPs.
4. It then does Step 2 again, but searches downhill for site pins to use as sinks for a net.
5. It then does Step 3 again, but for pairs of downhill paths.
6. Next, it finds solutions where an uphill pair of paths can be matched up with a downhill pair of paths and all 4 sub-paths in the pairs are disjoint.  I then uses them to construct two different disjoint nets that pass through the PIP of interest.  
7. There will be cases where no solutions are found in Step 6 (possibly due to not enough uphill/downhill paths).  The corresponding  *unsolved for* PIPs are collected in a list, the depth is incremented, and Steps 2-6 are run again.  
This can be repeated as many times as is desired.  

For the INT_L tile, a depth of 6 is sufficient to solve for all PIPs.  The reason it starts at a search depth of 3 and then increments it as needed is speed.  An INT_L has about 3,600 PIPs - 2,500 of them can be solved for quickly with a search depth of 3, another ~850 will then be found with a search depth of 4, and so on.  

The solution is the collection of all of the results obtained by running Steps 1-7 on the list of PIPs with increasing search depths until all are solved.  As mentioned, a depth of 6 is enough to ultimately solve for all the PIPs in an INT_L tile.  However, in the event not all PIPs are solved for, the unsolved ones will be listed in the `pipresults.txt` file.  And, Step 2 below can still be run on the results for the PIPs that were solved for.

# Step 2: Running `placePipPairs.py`
A typical run for this would be:
```
python3 placePipPairs.py
```
This runs in less than a second.  The program examines the net pairs produced by Step 1 and packs as many as it can into a design.  It then repeats the process with the remaining PIPs in a next design.  Thus, it may take 20, 30, or more designs to fully hold all the net pairs needed.   

The results will be placed into a file called `packedResults.json`.  This a dictionary where the keys are the names of the designs and the values are the net pairs that should be packed into those designs.

Corey Simpson's initial work demonstrated that packing too much into a design causes Vivado's router to fail.  So, a limit may be specified as to how many pairs to pack into a design.  Specifying 2000 for the limit results in designs with the following number of net pairs: 841, 631, 538, 440, 352, 285, 202, 153, 88, 47, 20, 5, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1.  But, even 841 is too many net pairs for one design.  Specifying a limit of 30 or 40 is similar to the limit of 75 PIPs specified in `pips_rapid.py`.  Some experimentation may be required to get it just right.  The tradeoff is more smaller designs vs. fewer larger designs.

# Step 3: Finishing the Process
The remaining (undone) steps would be:
1. For each design from the `packedResults.json` file, create Tcl code to create the design, place the cells needed for the net endpoints, and create the nets to connect those endpoints (both logically and physically).  The `pips_rapid.py` module already has code to do that so this step would be an adaptation of that code.  
2. The Tcl files would then be executed to map the designs to bitstreams and to feature (.ft) files.  
3. The resulting data (.bit and .ft files) would then be run through the original fuzzer's data analysis code as before.  This code would be unchanged.

In Step 1 above, cells are created and placed onto BELs in sites so that the nets will have legal endpoints.  The original `pips_rapid.py` code placed limits on the types of sites allowed to host cells (mainly TIEOFF and SLICEL sites).  And, its cell creation in Step 1 only supports those site types.

Experimentation has shown that this limited set of sites was preventing some PIPs from being solved for.  Thus, the list in `placePipPairs.py` was enlarged to also allow SLICEM, TIEOFF, and BUFHCE sites (see the `is_valid_SP` routine).  This allows all INT_L pips to be solved for.  Accordingly, the code in `pips_rapid.py` which creates cells in Step 1 above would need to be augmented to support these new site types and their pins.

Finally, note that when it runs, the `placePipPairs.py` program prints out the site types and pins that are required to be supported to solve for all PIPs to help illustrate what needs to be done.  

# The `ts.tcl` Program
In testing,the `ts.tcl` script was written to automate the process of using Tcl to find uphill/downhill paths to compare to what the program was finding...