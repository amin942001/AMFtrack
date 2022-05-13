"""Utils for defining environement variables and defining paths"""

from scipy import sparse
import numpy as np
import os
from datetime import datetime
from amftrack.pipeline.functions.image_processing.extract_graph import (
    sparse_to_doc,
)
import cv2
import json
import pandas as pd
from amftrack.util.dbx import download, upload, load_dbx, env_config
from tqdm.autonotebook import tqdm
from time import time_ns
from decouple import Config, RepositoryEnv
from pymatreader import read_mat


DOTENV_FILE = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    + "/local.env"
)
env_config = Config(RepositoryEnv(DOTENV_FILE))

path_code = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
target = env_config.get("DATA_PATH")
storage_path = env_config.get("STORAGE_PATH")
fiji_path = env_config.get("FIJI_PATH")
test_path = os.path.join(storage_path, "test")  # repository used for tests
pastis_path = env_config.get("PASTIS_PATH")
temp_path = env_config.get("TEMP_PATH")
slurm_path = env_config.get("SLURM_PATH")


def pad_number(number):
    """
    Convert number to string and padd with a zero
    Ex:
    1 -> 01
    23 -> 23
    """
    if number < 10:
        return f"0{number}"
    else:
        return str(number)


def get_path(date, plate, skeleton, row=None, column=None, extension=".mat"):
    root_path = (
        r"//sun.amolf.nl/shimizu-data/home-folder/oyartegalvez/Drive_AMFtopology/PRINCE"
    )
    date_plate = f"/2020{date}"
    plate = f"_Plate{plate}"
    if skeleton:
        end = "/Analysis/Skeleton" + extension
    else:
        end = "/Img" + f"/Img_r{pad_number(row)}_c{pad_number(column)}.tif"
    return root_path + date_plate + plate + end


def get_dates_datetime(directory, plate):
    listdir = os.listdir(directory)
    list_dir_interest = [
        name
        for name in listdir
        if name.split("_")[-1] == f'Plate{0 if plate<10 else ""}{plate}'
    ]
    ss = [name.split("_")[0] for name in list_dir_interest]
    ff = [name.split("_")[1] for name in list_dir_interest]
    dates_datetime = [
        datetime(
            year=int(ss[i][:4]),
            month=int(ss[i][4:6]),
            day=int(ss[i][6:8]),
            hour=int(ff[i][0:2]),
            minute=int(ff[i][2:4]),
        )
        for i in range(len(list_dir_interest))
    ]
    dates_datetime.sort()
    return dates_datetime


def get_dirname(date, plate):
    return f'{date.year}{0 if date.month<10 else ""}{date.month}{0 if date.day<10 else ""}{date.day}_{0 if date.hour<10 else ""}{date.hour}{0 if date.minute<10 else ""}{date.minute}_Plate{0 if plate<10 else ""}{plate}'


def shift_skeleton(skeleton, shift):
    shifted_skeleton = sparse.dok_matrix(skeleton.shape, dtype=bool)
    for pixel in skeleton.keys():
        #             print(pixel[0]+shift[0],pixel[1]+shift[1])
        if (
            skeleton.shape[0] > np.ceil(pixel[0] + shift[0]) > 0
            and skeleton.shape[1] > np.ceil(pixel[1] + shift[1]) > 0
        ):
            shifted_pixel = (
                np.round(pixel[0] + shift[0]),
                np.round(pixel[1] + shift[1]),
            )
            shifted_skeleton[shifted_pixel] = 1
    return shifted_skeleton


def transform_skeleton_final_for_show(skeleton_doc, Rot, trans):
    skeleton_transformed = {}
    transformed_keys = np.round(
        np.transpose(np.dot(Rot, np.transpose(np.array(list(skeleton_doc.keys())))))
        + trans
    ).astype(np.int)
    i = 0
    for pixel in list(transformed_keys):
        i += 1
        skeleton_transformed[(pixel[0], pixel[1])] = 1
    skeleton_transformed_sparse = sparse.lil_matrix((27000, 60000))
    for pixel in list(skeleton_transformed.keys()):
        i += 1
        skeleton_transformed_sparse[(pixel[0], pixel[1])] = 1
    return skeleton_transformed_sparse


def get_skeleton(exp, boundaries, t, directory):
    i = t
    plate = exp.plate
    listdir = os.listdir(directory)
    dates = exp.dates
    date = dates[i]
    directory_name = get_dirname(date, plate)
    path_snap = directory + directory_name
    skel = read_mat(path_snap + "/Analysis/skeleton_pruned_realigned.mat")
    skelet = skel["skeleton"]
    skelet = sparse_to_doc(skelet)
    Rot = skel["R"]
    trans = skel["t"]
    skel_aligned = transform_skeleton_final_for_show(
        skelet, np.array([[1, 0], [0, 1]]), np.array([0, 0])
    )
    output = skel_aligned[
        boundaries[2] : boundaries[3], boundaries[0] : boundaries[1]
    ].todense()
    kernel = np.ones((5, 5), np.uint8)
    output = cv2.dilate(output.astype(np.uint8), kernel, iterations=2)
    return (output, Rot, trans)


def get_param(
    folder, directory
):  # Very ugly but because interfacing with Matlab so most elegant solution.
    path_snap = os.path.join(directory, folder)
    file1 = open(path_snap + "/param.m", "r")
    Lines = file1.readlines()
    ldict = {}
    for line in Lines:
        to_execute = line.split(";")[0]
        relation = to_execute.split("=")
        if len(relation) == 2:
            ldict[relation[0].strip()] = relation[1].strip()
        # exec(line.split(';')[0],globals(),ldict)
    files = [
        "/Img/TileConfiguration.txt.registered",
        "/Analysis/skeleton_compressed.mat",
        "/Analysis/skeleton_masked_compressed.mat",
        "/Analysis/skeleton_pruned_compressed.mat",
        "/Analysis/transform.mat",
        "/Analysis/transform_corrupt.mat",
        "/Analysis/skeleton_realigned_compressed.mat",
        "/Analysis/nx_graph_pruned.p",
        "/Analysis/nx_graph_pruned_width.p",
        "/Analysis/nx_graph_pruned_labeled.p",
    ]
    for file in files:
        ldict[file] = os.path.isfile(path_snap + file)
    return ldict


def update_plate_info_local(directory: str) -> None:
    """
    An acquisition repositorie has a param.m file inside it.
    """
    listdir = os.listdir(directory)
    source = f"/data_info.json"

    with open(target) as f:
        plate_info = json.load(f)
    # plate_info = json.load(open(target, "r"))
    with tqdm(total=len(listdir), desc="analysed") as pbar:
        for folder in listdir:
            path_snap = os.path.join(directory, folder)
            if os.path.isfile(os.path.join(path_snap, "param.m")):
                params = get_param(folder, directory)
                ss = folder.split("_")[0]
                ff = folder.split("_")[1]
                date = datetime(
                    year=int(ss[:4]),
                    month=int(ss[4:6]),
                    day=int(ss[6:8]),
                    hour=int(ff[0:2]),
                    minute=int(ff[2:4]),
                )
                params["date"] = datetime.strftime(date, "%d.%m.%Y, %H:%M:")
                params["folder"] = folder
                total_path = os.path.join(directory, folder)
                plate_info[total_path] = params
            pbar.update(1)
    with open(target, "w") as jsonf:
        json.dump(plate_info, jsonf, indent=4)


def update_plate_info(directory: str, local=False) -> None:
    """*
    1/ Download `data_info.json` file containing all information about acquisitions.
    2/ Add all acquisition files in the `directory` path to the `data_info.json`.
    3/ Upload the new version of data_info (actuliased) to the dropbox.
    An acquisition repositorie has a param.m file inside it.
    """
    # TODO(FK): add a local version without dropbox modification
    listdir = os.listdir(directory)
    source = f"/data_info.json"
    if local:
        plate_info = {}
    else:
        download(source, target, end="")
        plate_info = json.load(open(target, "r"))
    with tqdm(total=len(listdir), desc="analysed") as pbar:
        for folder in listdir:
            path_snap = os.path.join(directory, folder)
            if os.path.isfile(os.path.join(path_snap, "param.m")):
                params = get_param(folder, directory)
                ss = folder.split("_")[0]
                ff = folder.split("_")[1]
                date = datetime(
                    year=int(ss[:4]),
                    month=int(ss[4:6]),
                    day=int(ss[6:8]),
                    hour=int(ff[0:2]),
                    minute=int(ff[2:4]),
                )
                params["date"] = datetime.strftime(date, "%d.%m.%Y, %H:%M:")
                params["folder"] = folder
                total_path = os.path.join(directory, folder)
                plate_info[total_path] = params
            pbar.update(1)
    with open(target, "w") as jsonf:
        json.dump(plate_info, jsonf, indent=4)
    if not local:
        upload(target, f"{source}", chunk_size=256 * 1024 * 1024)


def get_data_info(local=False):
    source = f"/data_info.json"
    if not local:
        download(source, target, end="")
    data_info = pd.read_json(target, convert_dates=True).transpose()
    data_info.index.name = "total_path"
    data_info.reset_index(inplace=True)
    return data_info


def get_current_folders_local(directory: str) -> pd.DataFrame:

    plate_info = pd.read_json(target, convert_dates=True).transpose()
    plate_info.index.name = "total_path"
    plate_info.reset_index(inplace=True)
    listdir = os.listdir(directory)
    return plate_info.loc[
        np.isin(plate_info["folder"], listdir)
        & (plate_info["total_path"] == directory + plate_info["folder"])
    ]  # TODO(FK): use os.join here


def get_current_folders(
    directory: str, file_metadata=False, local=False
) -> pd.DataFrame:
    """
    Returns a pandas data frame with all informations about the acquisition files
    inside the directory.
    WARNING: directory must finish with '/'
    """
    # TODO(FK): solve the / problem
    plate_info = get_data_info(local)
    listdir = os.listdir(directory)
    return plate_info.loc[
        np.isin(plate_info["folder"], listdir)
        & (plate_info["total_path"] == directory + plate_info["folder"])
    ]


def get_folders_by_plate_id(plate_id, begin=0, end=-1, directory=None):
    data_info = get_data_info() if directory is None else get_current_folders(directory)
    folders = data_info.loc[
        10**8 * data_info["Plate"] + data_info["CrossDate"] == plate_id
    ]
    dates_datetime = [
        datetime.strptime(row["date"], "%d.%m.%Y, %H:%M:")
        for index, row in folders.iterrows()
    ]
    dates_datetime.sort()
    dates_datetime_select = dates_datetime[begin:end]
    dates_str = [
        datetime.strftime(date, "%d.%m.%Y, %H:%M:") for date in dates_datetime_select
    ]
    select_folders = folders.loc[np.isin(folders["date"], dates_str)]
    return select_folders


def update_analysis_info(directory):
    listdir = os.listdir(directory)
    update_plate_info(directory)
    all_folders = get_current_folders(directory)
    analysis_dir = [fold for fold in listdir if fold.split("_")[0] == "Analysis"]
    infos_analysed = {}
    for folder in analysis_dir:
        metadata = {}
        version = folder.split("_")[-1]
        op_id = int(folder.split("_")[-2])
        dt = datetime.fromtimestamp(op_id // 1000000000)
        path = f"{directory}{folder}/folder_info.json"
        infos = json.load(open(path, "r")) if os.path.isfile(path) else []
        infos.sort()
        if len(infos) > 0:
            select = all_folders.loc[all_folders["folder"].isin(infos)]
            column_interest = [column for column in select.columns if column[0] != "/"]
            metadata["version"] = version
            for column in column_interest:
                if column != "folder":
                    metadata[column] = list(select[column])[0]
            metadata["date_begin"] = infos[0]
            metadata["date_end"] = infos[-1]
            metadata["number_timepoints"] = len(infos)
            metadata["path_exp"] = f"{folder}/experiment.pick"
            metadata["path_global_hypha_info"] = f"{folder}/global_hypha_info.json"
            metadata["path_time_hypha_info"] = f"{folder}/time_hypha_info"
            metadata["path_time_plate_info"] = f"{folder}/time_plate_info.json"
            metadata["path_global_plate_info"] = f"{folder}/global_plate_info.json"
            metadata["date_run_analysis"] = datetime.strftime(dt, "%d.%m.%Y, %H:%M:")
            infos_analysed[folder] = metadata
        with open(f"{directory}global_analysis_info.json", "w") as jsonf:
            json.dump(infos_analysed, jsonf, indent=4)


def get_analysis_info(directory):
    analysis_info = pd.read_json(
        f"{directory}global_analysis_info.json", convert_dates=True
    ).transpose()
    analysis_info.index.name = "folder_analysis"
    analysis_info.reset_index(inplace=True)
    return analysis_info


def get_data_tables(op_id=time_ns(), redownload=True):
    API = str(np.load(os.getenv("HOME") + "/pycode/API_drop.npy"))
    dir_drop = "data_tables"
    root = os.getenv("TEMP")
    # op_id = time_ns()
    if redownload:
        path_save = f"{root}global_hypha_info{op_id}.pick"
        download(f"/{dir_drop}/global_hypha_infos.pick", path_save)
        path_save = f"{root}time_plate_infos{op_id}.pick"
        download(f"/{dir_drop}/time_plate_infos.pick", path_save)
        path_save = f"{root}time_hypha_info{op_id}.pick"
        download(f"/{dir_drop}/time_hypha_infos.pick", path_save)
    path_save = f"{root}time_plate_infos{op_id}.pick"
    time_plate_info = pd.read_pickle(path_save)
    path_save = f"{root}global_hypha_info{op_id}.pick"
    global_hypha_info = pd.read_pickle(path_save)
    path_save = f"{root}time_hypha_info{op_id}.pick"
    time_hypha_info = pd.read_pickle(path_save)
    return (time_plate_info, global_hypha_info, time_hypha_info)


if __name__ == "__main__":
    directory = r"/data/felix/"
    update_plate_info(directory)
