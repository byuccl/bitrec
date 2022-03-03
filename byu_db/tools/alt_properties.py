import json
import os
import argparse
from collections import defaultdict

# Some generators and accessor functions
def genProps(bel):
    for propkey, prop in bel["CONFIG"].items():
        initbus = "BUS" in prop.keys()
        yield (initbus, propkey, prop["VALUE"])


def genVals(prop):
    for valkey, val in prop.items():
        yield (valkey, val)


def getOff(val):
    return sorted(val["OFF"])


def getOn(val):
    return sorted(val["ON"])


def genSites(dat):
    for sitenum in range(len(dat["SITE_INDEX"])):
        yield sitenum


def getAlts(dat, sitenum):
    return dat["SITE_INDEX"][str(sitenum)]["SITE_TYPE"]


def genBels(site):
    for belkey, bel in site["BEL"].items():
        yield (belkey, bel)


def sitenumLookup(dat, sitenum):
    s = dat["SITE_INDEX"][sitenum]
    return s


def altsiteLookup(dat, sitenum, altsitekey):
    s = sitenumLookup(dat, sitenum)["SITE_TYPE"][altsitekey]
    return s


def belLookup(dat, sitenum, altsitekey, belkey):
    b = altsiteLookup(dat, sitenum, altsitekey)["BEL"][belkey]
    return b


def propLookup(dat, sitenum, altsitekey, belkey, propkey):
    p = belLookup(dat, sitenum, altsitekey, belkey)["CONFIG"][propkey]
    return p


def valLookup(dat, sitenum, altsitekey, belkey, propkey, valkey):
    v = propLookup(dat, sitenum, altsitekey, belkey, propkey)["VALUE"][valkey]
    return v


def bitsLookup(dat, sitenum, altsitekey, belkey, propkey, valkey):
    s = dat["SITE_INDEX"][sitenum]["SITE_TYPE"][altsitekey]
    b = s["BEL"][belkey]
    p = b["CONFIG"][propkey]
    v = valLookup(dat, sitenum, altsitekey, belkey, propkey, valkey)
    return (v["ON"], v["OFF"])


def onbitsLookup(dat, sitenum, altsitekey, belkey, propkey, valkey):
    return bitsLookup(dat, sitenum, altsitekey, belkey, propkey, valkey)[0]


def offbitsLookup(dat, sitenum, altsitekey, belkey, propkey, valkey):
    return bitsLookup(dat, sitenum, altsitekey, belkey, propkey, valkey)[1]


uniq = set()


def printUnique(s):
    if s not in uniq:
        print(s)
        uniq.add(s)


def findSelectDisable(fil, propVals, sitenum, select):
    tile = fil.split(".")[1]
    for me in propVals.keys():
        myprops = set()
        for prop in propVals[me].keys():
            myprops.add(prop)
        theirprops = set()
        for x in propVals.keys():
            if x != me:
                for propkey, prop in propVals[x].items():
                    theirprops.add(propkey)
        private_props = myprops.difference(theirprops)
        if len(private_props) > 0:
            private_props = sorted(private_props)
            for propkey in private_props:
                print(f"\n# SITE:SELECT:{tile}@{sitenum}:{me}:{propkey}")
                for valkey, val in propVals[me][propkey].items():
                    printUnique(
                        f"## SITE:SELECT:{tile}@{sitenum}:{me}:{propkey}:{valkey}\nSITE:SELECT:{tile}@{sitenum}:{me}:{propkey} {val[0]} !{val[1]}"
                    )


def buildDict(d, keys):
    if keys[0] not in d.keys():
        d[keys[0]] = dict()
    if keys[1] not in d[keys[0]].keys():
        d[keys[0]][keys[1]] = dict()


def findAlternates(tile, ignore_bram_inits, verbose):

    files = [
        f
        for f in os.listdir(".")
        if f.startswith("db.") and f.endswith(".json") and f != "tilegrid.json"
    ]
    files.sort()

    if tile is not None:
        files = []
        files.append(f"db.{tile}.json")

    for fil in files:
        with open(fil) as f:
            dat = json.load(f)

        for sitenum in genSites(dat):
            # The site types allowed for a given site index can be 1 or >1 (in which case there are alternate site types)

            # Decide if there are alternate site types...
            if len(getAlts(dat, sitenum)) < 2:
                continue
            if verbose:
                print(f"\nTile file = {fil}    Site index = {sitenum}")

            propVals = dict()

            # Loop across the alternate site types for the given site
            for altsitekey, altsite in getAlts(dat, sitenum).items():
                # proplist is a set of the properties for an alt site
                if verbose:
                    print(f"  Alternate: {altsitekey}")

                # Sites have bels, loop across those
                for belkey, bel in genBels(altsite):
                    if verbose:
                        print(f"      BEL: {belkey}")

                    # Bels have properties, loop across those
                    for inits, propkey, prop in genProps(bel):
                        if (ignore_bram_inits == True) and (inits == True):
                            pass
                        else:

                            # Properties have values, loop across those
                            for valkey, val in genVals(prop):
                                off = val["OFF"] if "OFF" in val else []
                                on = val["ON"] if "ON" in val else []

                                buildDict(propVals, [altsitekey, propkey])
                                propVals[altsitekey][propkey][valkey] = [
                                    sorted(on),
                                    sorted(off),
                                ]
                                if verbose:
                                    print(
                                        f"              PROP: {altsitekey} {propkey} {valkey} =  {propVals[altsitekey][propkey][valkey]}"
                                    )
                            # end for valkey
                    # end for propkey
                # end for belkey
            # end for altsitekey

            # At this point we have a data structure show properties for each alternate site
            findSelectDisable(fil, propVals, sitenum, True)

            if verbose:
                print("enddisable")
        # end for sitenum
    # end for fil


# end def findAlternates


def main():
    parser = argparse.ArgumentParser(
        description="Check database files for alternate site types and output info accordingly."
    )
    parser.add_argument("--tile")
    parser.add_argument("--ignore_bram_inits", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    findAlternates(args.tile, args.ignore_bram_inits, args.verbose)


if __name__ == "__main__":
    main()
