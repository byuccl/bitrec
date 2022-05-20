import json


def summarize_tile_pips():
    with open("artix7/xc7a100ticsg324-1L/vivado_db/bel_dict.json") as fj:
        bel_dict = json.load(fj)

    d = bel_dict["TILE_TYPE"]

    for tt in sorted(d.keys()):
        alwys = 0
        dflt = 0
        rtthru = 0
        pp = 0

        print(tt, end='')
        for key in d[tt]["TILE_PIP"]:
            #print(f"   {key}", end="")
            typ = d[tt]['TILE_PIP'][key]['TYPE']
            #print(f"  {typ}")
            if typ == "ALWAYS":
                alwys += 1
            elif typ == "DEFAULT":
                dflt += 1
            elif typ == "ROUTETHRU":
                rtthru += 1
            else:
                pp += 1
        bar = '' if pp==0 else '          # ' if pp<10 else '          ### ' if pp<50 else'          ##### ' if pp<100 else'          ################## '
        print(f"    {alwys}:{dflt}:{rtthru}:{pp}{bar}")

summarize_tile_pips()

        