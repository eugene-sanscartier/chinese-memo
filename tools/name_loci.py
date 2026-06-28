import os
import shutil
import json
from pathlib import Path

import glob
import re

ROOT_DIR = Path(__file__).resolve().parent
AUTHORED_DIR = ROOT_DIR / "data" / "source" / "authored"
LOCI_ASSETS_DIR = ROOT_DIR / "assets" / "loci"
LOCI_NAME_DIR = ROOT_DIR / "data" / "cache" / "loci_name"
LOCI_NAME_DIR.mkdir(parents=True, exist_ok=True)

with open(AUTHORED_DIR / "loci.json", "r") as f:
    loci_data = json.load(f)

for locus_name, locus_info in loci_data.items():

    # if last character in name is a number
    if re.match(r".*\d$", locus_name):
        # rename the file to include the number at the start
        shutil.copy(LOCI_ASSETS_DIR / f"{locus_name}.png", LOCI_NAME_DIR / f"{locus_info['name']} - {locus_name[0]}{locus_name[-1]}.png")
    else:
        shutil.copy(LOCI_ASSETS_DIR / f"{locus_name}.png", LOCI_NAME_DIR / f"{locus_info['name']} - {locus_name[0]}.png")
