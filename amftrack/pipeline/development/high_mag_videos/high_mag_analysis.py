import pandas as pd
from IPython.display import clear_output
import re
from amftrack.pipeline.development.high_mag_videos.kymo_class import *
from amftrack.pipeline.development.high_mag_videos.plot_data import (
    save_raw_data,
    plot_summary,
    read_video_data
)
import sys
import os
import imageio.v3 as imageio
import matplotlib.pyplot as plt
import cv2
from tifffile import imwrite
from tqdm import tqdm
from amftrack.pipeline.functions.image_processing.extract_graph import (
    from_sparse_to_graph,
    generate_nx_graph,
    clean_degree_4,
)
import scipy
import matplotlib as mpl

from amftrack.pipeline.launching.run import (
    run_transfer,
)
from amftrack.pipeline.launching.run_super import run_parallel_transfer
import dropbox
from amftrack.util.dbx import upload_folders, download, read_saved_dropbox_state, save_dropbox_state, load_dbx, \
    download, get_dropbox_folders, get_dropbox_video_folders
from subprocess import call
import logging
import datetime
import glob
import json
from amftrack.pipeline.launching.run_super import run_parallel

logging.basicConfig(stream=sys.stdout, level=logging.debug)
mpl.rcParams['figure.dpi'] = 300

def index_videos_dropbox(analysis_folder, video_folder, dropbox_folder, REDO_SCROUNGING=False):
    analysis_json = f"{analysis_folder}{dropbox_address[6:]}all_folders_drop.json"
if os.path.exists(analysis_json):
    all_folders_drop = pd.read_json(analysis_json)
excel_json = f"{analysis_folder}{dropbox_address[6:]}excel_drop.json"
if os.path.exists(excel_json):
    excel_drop = pd.read_json(excel_json, typ='series')
if not os.path.exists(analysis_json) or REDO_SCROUNGING:
    print("Redoing the dropbox scrounging, hold on tight.")
    all_folders_drop, excel_drop, txt_drop = get_dropbox_video_folders(dropbox_address, True)

    clear_output(wait=False)
    print("Scrounging complete, merging files...")
    
    excel_addresses = np.array([re.search("^.*Plate.*\/.*Plate.*$", entry, re.IGNORECASE) for entry in excel_drop])
    excel_addresses = excel_addresses[excel_addresses != None]
    excel_addresses = [address.group(0) for address in excel_addresses]
    excel_drop = np.concatenate([excel_addresses,txt_drop])
    if not os.path.exists(f"{analysis_folder}{dropbox_address[6:]}"):
        os.makedirs(f"{analysis_folder}{dropbox_address[6:]}")
    all_folders_drop.to_json(analysis_json)
    pd.Series(excel_drop).to_json(excel_json)
    


class HighmagDataset(object):
    def __init__(self,
                 dataframe:pd.DataFrame):
        self.dataset = dataframe
        self.video_objs = [VideoDataset(row) for index, row in self.dataset.iterrows()]
        self.edge_objs = [video.edge_objs for video in self.video_objs].flatten()

        
    def filter_edges(self, column, compare, constant):
        return None
        
    def filter_videos(self, column, compare, constant):
        return None

    def bin_dataset(self, column, bins):
        return None
    
    def return_video_frame(self):
        return self.dataset
    
    def return_edge_frame(self):
        edge_frame
    
    def return_edge_objs(self):
        return self.edge_objs

    def return_vid_objs(self):
        return self.video_objs


class VideoDataset(object):
    def __init__(self,
                 series):
        self.dataset = series
        if os.path.exists(self.dataset['analysis_folder']+'edges_data.csv'):
            self.edges_frame = pd.read_csv(self.dataset['analysis_folder']+'edges_data.csv')
            self.edge_objs = [EdgeDataset(pd.concat([row, self.dataset])) for index, row in self.edges_frame.iterrows()]
            self.dataset['nr_of_edges'] = len(self.edges_frame)
        else:
            print(f"Couldn't find the edges data file. Check analysis for {self.dataset['unique_id']}")
            self.dataset['nr_of_edges'] = 0


    def show_summary(self):
        if os.path.exists(self.dataset['analysis_folder'] + 'Detected edges.png'):
            print('Index, edge name')
            print(self.edges_frame['edge_name'].to_string())
            extraction_img = imageio.imread(self.dataset['analysis_folder'] + 'Detected edges.png')
            fig, ax = plt.subplots()
            ax.imshow(extraction_img)
            ax.set_axis_off()
            ax.set_title(f"{self.dataset['unique_id']}")
            fig.tight_layout()

    def show_segmentation(self):
        if os.path.exists(self.dataset['analysis_folder'] + 'Video segmentation.png'):
            extraction_img = imageio.imread(self.dataset['analysis_folder'] + 'Video segmentation.png')
            fig, ax = plt.subplots()
            ax.imshow(extraction_img)
            ax.set_axis_off()
            fig.tight_layout()

    def scatter_speeds_video(self):
        fig, ax = plt.subplots()
        # ax.grid(True)
        ax.axhline(c='black', linestyle='--', alpha=0.5)
        ax.scatter(self.edges_frame.index, self.edges_frame['speed_mean'], c='black', label='effMean')
        ax.errorbar(self.edges_frame.index, self.edges_frame['speed_right'],
                    self.edges_frame['speed_right_std'],
                    c='tab:orange', label='to tip', marker='o', linestyle='none', capsize=10)
        ax.errorbar(self.edges_frame.index, self.edges_frame['speed_left'],
                    self.edges_frame['speed_left_std'],
                    c='tab:blue', label='to root', marker='o', linestyle='none', capsize=10)
        ax.legend()
        ax.set_xticks(self.edges_frame.index)
        ax.set_xticklabels(self.edges_frame['edge_name'], rotation=45)
        ax.set_title(f"Edge speed overview for {self.dataset['unique_id']}")
        ax.set_ylabel("Velocity $(\mu m /s)$")
        fig.tight_layout()



class EdgeDataset(object):
    def __init__(self,
                 dataframe):
        self.mean_data = dataframe
        self.edge_name = self.mean_data['edge_name']
        self.time_data = pd.read_csv(self.mean_data['analysis_folder']+'edge '+self.mean_data['edge_name']+os.sep+self.mean_data['edge_name']+'_data.csv')

    def show_summary(self):
        summ_img = imageio.imread(self.mean_data['analysis_folder']+'edge '+self.mean_data['edge_name']+os.sep+self.mean_data['edge_name']+'_summary.png')
        fig = plt.figure()
        ax = fig.add_axes([0, 0, 1, 1], frameon=False, aspect=1)
        ax.imshow(summ_img)
        ax.set_axis_off()

    def plot_flux(self):
        fig, ax = plt.subplots()
        ax.plot(self.time_data['times'], self.time_data['flux_mean'])
        fig.tight_layout()

