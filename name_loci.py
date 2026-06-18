import os
import shutil
import json

import glob
import re

with open("loci.json", "r") as f:
    loci_data = json.load(f)

for locus_name, locus_info in loci_data.items():

    # if last character in name is a number
    if re.match(r".*\d$", locus_name):
        # rename the file to include the number at the start
        shutil.copy("loci/" + locus_name + ".png", f"loci_name/{locus_info["name"]} - {locus_name[0]}{locus_name[-1]}" + ".png")
    else:
        shutil.copy("loci/" + locus_name + ".png", f"loci_name/{locus_info["name"]} - {locus_name[0]}" + ".png")
