import json
import os
import argparse

# Some generators and accessor functions
def genProps(bel):
    for propkey, prop in bel["CONFIG"].items():
        initbus = "BUS" in prop and prop["BUS"] == "BLOCK_RAM"
        yield (initbus, propkey, prop["VALUE"])


def genVals(prop):
    for valkey, val in prop.items():
        yield (valkey, val)


def getOff(val):
    if "OFF" in val:
        return sorted(val["OFF"])
    else:
        return []


def getOn(val):
    if "ON" in val:
        return sorted(val["ON"])
    else:
        return []


def genSites(dat):
    for sitenum in range(len(dat["SITE_INDEX"])):
        yield sitenum


def getAlts(dat, sitenum):
    return dat["SITE_INDEX"][str(sitenum)]["SITE_TYPE"]


def genBels(site):
    for belkey, bel in site["BEL"].items():
        yield (belkey, bel)


def checkIdenticalPropValues(sitekey, belkey, propkey, prop):
    for mekey, meval in genVals(prop):
        meon = getOn(meval)
        meoff = getOff(meval)
        if len(meon) == 0 and len(meoff) == 0:
            return
        for themkey, themval in genVals(prop):
            if mekey == themkey:
                continue
            themon = getOn(themval)
            themoff = getOff(themval)
            if len(themon) == 0 and len(themoff) == 0:
                continue
            if meon == themon and meoff == themoff:
                print(
                    f"ERROR: duplicate prop vals:  site: {sitekey} bel: {belkey} prop: {mekey} otherprop: {themkey}, there may be others for {mekey}, continuing..."
                )
                break


def checkUnsolved(propkey, prop, mekey, meval):
    meon = getOn(meval)
    meoff = getOff(meval)
    if len(meon) == 0 and len(meoff) == 0:
        print(f"UNSOLVED: {propkey}  {mekey}")


def prettyPrint(checkdups, checkunsolved, tile, ignore_bram_inits):

    files = [f for f in os.listdir(".") if f.startswith("db.") and f.endswith(".json")]
    files.sort()

    if tile is not None:
        files = [f"db.{tile}.json"]

    for fil in files:
        print(f"Processing {fil}")
        with open(fil) as f:
            dat = json.load(f)

        # print(f"\n##################################################################################################")
        # print(f"\nDoing tile: {fil}")
        # Sites are numbered with an index
        for sitenum in genSites(dat):
            # The site types allowed for a given site index can be 1 or >1 (in which case there are alternate site types)
            altsites = getAlts(dat, sitenum)
            # Decide if there are alternate site types...
            if len(altsites) < 2:
                siteSpecifier = "Site type"
            else:
                siteSpecifier = "Alternate type"
            print(f"\nTile file = {fil}    Site index = {sitenum}")

            # Loop across the site types for the given site
            for sitekey, site in altsites.items():
                print(f"  {siteSpecifier}: {sitekey}")

                # Sites have bels, loop across those
                for belkey, bel in genBels(site):
                    print(f"      BEL: {belkey}")

                    # Bels have properties, loop across those
                    for inits, propkey, prop in genProps(bel):
                        if (ignore_bram_inits == True) and (inits == True):
                            continue
                        # Properties have values, loop across those
                        print(f"         PROP: {propkey} ")
                        for valkey, val in genVals(prop):

                            ## Property values have OFF and ON bits, grab those
                            off = getOff(val)
                            on = getOn(val)
                            if len(off) == 0:
                                off = "[]"
                            if len(on) == 0:
                                on = "[]"
                            print(f"           {valkey} {on} !{off}")
                            if checkunsolved:
                                checkUnsolved(propkey, prop, valkey, val)

                        if checkdups:
                            checkIdenticalPropValues(sitekey, belkey, propkey, prop)


def main():
    parser = argparse.ArgumentParser(
        description="Pretty print database files and check for duplicates."
    )
    parser.add_argument("--tile")
    parser.add_argument("--ignore_bram_inits", action="store_true")
    parser.add_argument("--checkdups", action="store_true")
    parser.add_argument("--checkunsolved", action="store_true")
    args = parser.parse_args()
    prettyPrint(args.checkdups, args.checkunsolved, args.tile, args.ignore_bram_inits)


if __name__ == "__main__":
    main()
