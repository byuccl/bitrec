import os
import json
from re import A

fileList = os.listdir("/tmp/db")
for file in sorted(fileList):
    if not file.endswith(".json"):
        continue
    print(file)
    with open("/tmp/db/" + file) as f:
        j = json.load(f)

    for top in j:
        if top != "SITE_INDEX":
            continue

        for snk in j[top]:
            #print('  ', snk)
            for st in j[top][snk]["SITE_TYPE"]:
                #print("    ", st)
                for b1 in j[top][snk]["SITE_TYPE"][st]:
                    if b1 == "SITE_PIP":
                        continue
                    for bel in j[top][snk]["SITE_TYPE"][st][b1]:
                        #print("      ", bel)
                        for prop in j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"]:
                            #print("        ", prop)
                            for val in j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"][prop]["VALUE"]:
                                if len(j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"][prop]["VALUE"][val]) > 1:
                                    print(snk, st, bel, prop, val, end='')
                                    print(" : ", len(j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"][prop]["VALUE"][val]), end='')
                                    #print(" ", j[top][snk]["SITE_TYPE"][st][b1][bel]["CONFIG"][prop]["VALUE"][val], end='')
                                    print()
