"""
The utils for tests are here.
There are several sorts of utils for tests:
- boolean functions to skip tests that haven't the data requiered
- function that create complicate objects like Experiment or Mock objects
"""

import cv2
import numpy as np
import os
from amftrack.util.sys import (
    test_path,
    get_current_folders_local,
    update_plate_info_local,
)
from amftrack.pipeline.functions.image_processing.experiment_class_surf import (
    Experiment,
)

video_path = os.path.join(test_path, "video")


def has_video():
    """
    Check if there is a video present to run tests on videos.
    The video should be several images of the same size in directory `video`.
    """
    video_path = os.path.join(test_path, "video")
    if os.path.isdir(video_path):
        return True
    return False


def make_video() -> None:
    """
    Makes a fake video and a video directory used to test video utils
    """
    video_path = os.path.join(test_path, "video")
    if not os.path.isdir(video_path):
        os.mkdir(video_path)

        im1 = np.triu(np.ones((10, 10)) * 100)
        im2 = np.triu(np.ones((10, 10)) * 10)
        for i in range(2):
            cv2.imwrite(os.path.join(video_path, f"image{i}.png"), im1)
        cv2.imwrite(os.path.join(video_path, f"image{2}.png"), im2)


def has_test_repo():
    "Tests if the general test repository is present"
    return os.path.isdir(test_path)


def make_test_repo():
    if not os.path.isdir(test_path):
        os.mkdir(test_path)


def has_test_plate():
    "Check if a Prince plate is present, for tests that use it"
    if has_test_repo():
        if len(os.listdir(test_path)) > 0:
            # TODO(FK): check if this is really a testing plate instead
            return True
    else:
        return False


def make_experiment_object():
    "Build an experiment object using the plate that is in the test repository."
    directory = test_path
    plate_name = "20220330_2357_Plate19"  # TODO(FK): find the name automaticaly (can be different based on the person)
    update_plate_info_local(directory)
    folder_df = get_current_folders_local(directory)
    selected_df = folder_df.loc[folder_df["folder"] == plate_name]
    i = 0
    plate = int(list(selected_df["folder"])[i].split("_")[-1][5:])
    folder_list = list(selected_df["folder"])
    # directory_name = folder_list[i]
    exp = Experiment(directory)
    # exp.load(selected_df.loc[selected_df["folder"] == directory_name], labeled=False)
    exp.load(selected_df, labeled=False)
    exp.load_tile_information(0)
    return exp


class EdgeMock:
    """
    A fake Edge object without having to make an experiment object
    """

    def __init__(self, list_coord):
        self.list_coord = list_coord

    def pixel_list(self, t):
        return self.list_coord
