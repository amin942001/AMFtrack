import os
import numpy as np
import unittest
from amftrack.util.sys import (
    update_plate_info_local,
    get_current_folders_local,
    test_path,
)
from amftrack.pipeline.functions.image_processing.experiment_class_surf import (
    Experiment,
)
from amftrack.pipeline.functions.image_processing.experiment_util import (
    get_random_edge,
    distance_point_edge,
)
from test import helper

# @unittest.skipUnless(helper.has_test_plate(), "No plate to run the tests..")
class TestExperiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = test_path + "/"  # TODO(FK): fix this error
        plate_name = "20220330_2357_Plate19"
        update_plate_info_local(directory)
        folder_df = get_current_folders_local(directory)
        selected_df = folder_df.loc[folder_df["folder"] == plate_name]
        i = 0
        plate = int(list(selected_df["folder"])[i].split("_")[-1][5:])
        folder_list = list(selected_df["folder"])
        directory_name = folder_list[i]
        cls.exp = Experiment(plate, directory)
        cls.exp.load(
            selected_df.loc[selected_df["folder"] == directory_name], labeled=False
        )

    def test_get_random_edge(self):
        get_random_edge(self.exp)
        get_random_edge(self.exp)


class TestExperimentLight(unittest.TestCase):
    def test_distance_point_edge(self):
        class EdgeMock:
            def __init__(self, list_coord):
                self.list_coord = list_coord

            def pixel_list(self, t):
                return self.list_coord

        edge = EdgeMock([[2, 3], [3, 3], [3, 4], [4, 5], [5, 5], [6, 6], [7, 7]])
        self.assertEqual(
            distance_point_edge([2, 3], edge, 0, step=1),
            0,
        )
