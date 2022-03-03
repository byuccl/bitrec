import os

files = [f for f in os.listdir(".") if f.endswith(".fail")]
files.sort()

for fil in files:
    with open(fil) as f:
        print(f"")
        for lin in f.readlines():
            s = lin.split(":")
            # for i in range(len(s)):
            #    print(f"{fil.split('.')[1]} {i} {s[i]}")
            print(f"{s[5]} {s[6]} {s[7]}")
