import jpype
import jpype.imports
from jpype.types import *
import sys
import argparse

jpype.startJVM(classpath=["rapidwright-2021.2.0-standalone-lin64.jar"])

from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim

def msg(s, hdr='', file=sys.stdout, end="\n"):
    print(f"{hdr}{str(s)}", file=sys.stdout, end=end)

def errmsg(s, hdr='', end="\n"):
    msg(s, hdr, file=sys.stderr, end=end)

def getTileOfType(device, tile_type):
    for T in device.getAllTiles():
        if T.getTileTypeEnum().toString() == tile_type:
            return T
    return None


def init_rapidwright(part_name):
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)
    return (device,design)

def processPIP(device, pipName, lodepth, hidepth):
    pip = device.getPIP(pipName)
    msg(pip)


def main():
    global args, allowedSLICEMpins

    parser = argparse.ArgumentParser()
    parser.add_argument('--family',default="spartan7")         # Selects the FPGA architecture family
    parser.add_argument('--part',default="xc7a100ticsg324-1L")    # Selects the FPGA part
    parser.add_argument('--verbose',default=0)                  # 1: Outputs initialized differential data and bitstream data to file
    parser.add_argument('--pip',default="INT_L_X50Y102/INT_L.GFAN0->>BYP_ALT1")
    parser.add_argument('--pipfile')
    parser.add_argument("--vrbs", action='store_true')
    parser.add_argument('--lodepth',default=4)
    parser.add_argument('--hidepth',default=5)
    args = parser.parse_args()
    globals.args = args
    globals.allowedSLICEMpins = allowedSLICEMpins

    device, design = init_rapidwright(args.part)

    # Build list of allowable SLICEM pins
    slice = getTileOfType(device, "CLBLL_L").getSites()[0]
    assert str(slice.getSiteTypeEnum()) == "SLICEL"
    allowedSLICEMpins = [slice.getPinName(i) for i in range(slice.getSitePinCount())]

    # Get pips to process
    if args.pipfile is None:
        pips = [ args.pip ]
    else:
        pips = []
        with open(args.pipfile) as f:
            lines = f.readlines()
        for l in lines:
            if l.startswith("## "):
                l = l.split(" ")[2]
            pips.append(l.strip())

    for pipName in pips():
        processPIP(device, pipName, args.lodepth, args.hidepth)


if __name__ == "__main__":
    main()