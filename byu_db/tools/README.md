# byu_db

These are the database files from BYU's fuzzer project

In addition to database files, this directory contains a couple of utilities:

## alt_properties.py
- Analyzes files and outputs info on alternate site types for use in downstream tools
- Currently produces SITE_SELECT for properties that exist in for a given alt site type but not in others.
    - It does this based on property names (which it puts into the comment for each SITE:SELECT) but then translates that to the bit pattern for that property in the actual uncommented SITE:SELECT line.
- Lookint at its output we see lots of unsolved properties - those should maybe be eliminated and not output...  Maybe we could just output the comment but not the empty rule.
- It has a flag to ignore BRAM INIT properties since they don't really contribute but just create thousands of rules
- It also has a flag to let you do just one tile type rather than everything
- What needs to be added is kind of the inverse rule of properties that exist only in OTHER alt site types' BELs.
    - These would be shown as: SITE:DISABLE rules
    - If one of these fired then you would know that it WASN'T the alt site type it applies to.  Similar logic to what is already there but find properties that everyone else has 
- The code has a findSelectDisable() routine that is intended to also do DISABLE rules but which has not been finished to do so - please finish it.
- Then, we need to do some debugging - look at the rules and decide if they make sense.  Then, might need to add new flags for certain things.  Example: does it make sense to generate empty rules because certain properties have not been solved for?
- Finally there is a question of being more careful than keying only off of property names.  That is if alt sites A, B have a property called XYZ and C doesn't have it, we want to generate a SITE:DISABLE for alt site C containing the bits for XYZ.  However, that assumes that the bit pattern for XYZ is identical when it shows up in either A or B.  While I *assume* that is the case we ought to be careful and put in a check for that to be sure (would be a terribly hard bug to find if we didn't have such a check and it proved not to be a valid assumption).  So, this ought to be added to the logic.


## dbAnalyzer.py
- Analyzes files and can do any of:
    - prettyprint the database for viewing
    - check for values of a given property to see if there are duplicates and flag them
    - print out all unsolved property values

## seldis.py
`seldis.py` prints out site:enable/disable metarules, allowing us to
determine which alternate sites are either being used, or are definitely
not being used.  With no arguments, it runs through all the tiles,
and generates the rules for each tile's alternate sites.  Optionally,
you can specify the `--tile <tilename>` option to run it only on a
particular tile.

## beldis.py
`beldis.py` prints out bel:enable/disable metarules, allowing us
to determine which bels are either being used, or are definitely not
being used.  At the top of the file, there is an allowlist of bels for
which it will generate rules. With no arguments, it runs through all the
tiles, and generates the rules for each bel that is found in the tile
as well as the allowlist.  tile's bels.  Optionally, you can specify the
`--tile <tilename>` option to run it only on a particular tile.

## sppip.py
`sppip.py` outputs a list of site ppips in the format of project xray's
ppips file.  With no arguments, it generates the ppips for every tile
that has a database file.  With the `--tile <tilename>` option, you can
instruct it to run on a single tile.
