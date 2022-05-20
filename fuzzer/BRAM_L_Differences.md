# BRAM_L Differences
The numbers listed below are line numbers in the db.INT_L.json file that was generated using the most recent code.  

The term 'new' below refers to the most recent code–generated database. The word 'old' below refers to what was in the bitrec/byu_db folder.

## "0" - RAMBFIFO36E1
- Lots of diffs that can't be attributed to ordering or something else  
  
### Examnple From RAMBFIFO36E1
- ALMOST_EMPTY_OFFSET
  - From [0] through [12] only two values solved for (others unsolved)
  - [11] not solved for in old but solved for in new
  - [12] only half of the 16 bits are the same between old and new
- Similar for ALMOST_FULL_OFFSET
- DATA_WIDTH has 7800 lines for its values and little in common between old and new

- As a result of a few spotchecks, I did not spend a whole lot of time on this one, I focused more on the ones below for starters.

## "1"
- Starts at 197440

### SITE TYPE FIFO18E1, BEL FIFO18E1
- Starts at 197444
- Lots of diffs that can't be attributed to ordering or something else.  These include the following:
  - TYPE 1 Differences
    - Bits in new are a subset of old - did the analysis simply get better?  (197553 is an example)
  - TYPE 2 Differences
    - Some features solved for in old are missing in new - is it the luck of the random draw?  (197634 is an example)
  - TYPE 3 Differences
    - The bits are just different with no apparent pattern (197692 is an example)

### SITE TYPE RAMB18E1, BEL RAMB18E1
- Starts at 200312
- 293425
  - The start of differences.  These look to be simply due to ordering (of disjunctions in conjunction)
    - After taking these into account, everything matches up

## "2"
- Starts at 293724

### SITE TYPE FIFO18E1, BEL FIFO18E1
- 293727
  - There was no FIFO18E1 section in the old one but there is in the new one!!

### SITE TYPE RAMB18E1, BEL RAMB18E1
- Starts at 294137
- 387276
  - Other than 3 diffs due to ordering (of disjunctions in conjunction), everything matches up.

## TILE_PIPS
- Starts at 387551
  - New pip structure looks different:

NEW =
"BRAM_RAMB18_DOPBDOP0->BRAM_LOGIC_OUTS_B3_3": {
      "BITS": [],
      "TYPE": "PIP"
    },

OLD =
"BRAM_ADDRARDADDRL0->>BRAM_FIFO18_ADDRATIEHIGH0": [
  []
],

- I did not compare the tile pip bits between old and new
