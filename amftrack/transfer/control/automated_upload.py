import os
import sys

sys.path.insert(0, os.getenv("HOME") + "/pycode/MscThesis/")
# sys.path.insert(0,r'C:\Users\coren\Documents\PhD\Code\AMFtrack')

import pandas as pd
from amftrack.util.sys import (
    update_plate_info,
    get_current_folders,
)

from datetime import datetime, timedelta
import imageio
import os
from amftrack.util.dbx import upload_folders
from tqdm.autonotebook import tqdm
from time import time_ns
import subprocess

directory_origin = r"/mnt/sun-temp/TEMP/PRINCE_syncing/"
dir_drop = "DATA/PRINCE"
update_plate_info(directory_origin, local=True)
all_folders_origin = get_current_folders(directory_origin, local=True)

all_folders_origin["date_datetime"] = pd.to_datetime(
    all_folders_origin["date"].astype(str), format="%d.%m.%Y, %H:%M:"
)
selection = (datetime.now() - all_folders_origin["date_datetime"]) >= timedelta(days=60)
old_folders = all_folders_origin.loc[selection]
old_folders["Plate"] = (
    old_folders["Plate"].str.replace("R", "66666").str.replace("[^0-9]", "")
)
upload_folders(old_folders, dir_drop=dir_drop, delete=True)
