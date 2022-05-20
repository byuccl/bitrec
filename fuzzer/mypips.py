import jpype
import jpype.imports
from jpype.types import *
import sys

jpype.startJVM(classpath=["rapidwright-2020.2.4-standalone-lin64.jar"])

from com.xilinx.rapidwright.device import Device
from com.xilinx.rapidwright.device import Series
from com.xilinx.rapidwright.design import Design
from com.xilinx.rapidwright.design import Unisim

def msg(s, hdr='', file=sys.stdout, end="\n"):
    print(f"{hdr}{str(s)}", file=sys.stdout, end=end)

def errmsg(s, hdr='', end="\n"):
    msg(s, hdr, file=sys.stderr, end=end)


def init_rapidwright(part_name):
    global device, design
    device = Device.getDevice(part_name)
    design = Design("temp",part_name)
    return (device,design)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--family',default="spartan7")         # Selects the FPGA architecture family
    parser.add_argument('--part',default="xc7a100ticsg324-1L")    # Selects the FPGA part
    parser.add_argument('--verbose',default=0)                  # 1: Outputs initialized differential data and bitstream data to file
    parser.add_argument('--pip',default="INT_L_X50Y102/INT_L.GFAN0->>BYP_ALT1")
    parser.add_argument('--pipfile')
    parser.add_argument("--vrbs", action='store_true')

    device, design = init_rapidwrite(args.part)

    # Build list of allowable SLICEM pins
    slicem = getTileOfType("CLBLM_L").getSlices()[1]


if __name__ == "__main__":
    main()