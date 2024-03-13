import glob
import pandas as pd
from pathlib import Path
from amftrack.pipeline.functions.transport_processing.high_mag_videos.high_mag_analysis import (
    HighmagDataset,
)
def load_video_dataset(plate_id_video,videos_folder,analysis_folder,analysis_folder_root):
    analysis_folder = f"{analysis_folder}{plate_id_video}/"

    img_infos = glob.glob(f"{analysis_folder}/**/video_data.json", recursive=True)
    vid_anls_frame = pd.DataFrame()
    add_infos = []
    for address in img_infos:
        add_infos.append(pd.read_json(address, orient="index").T)
    vid_anls_frame = pd.concat([vid_anls_frame] + add_infos, ignore_index=True)

    vid_anls_frame = vid_anls_frame.sort_values("unique_id").reset_index(drop=True)
    vid_anls_frame_select = vid_anls_frame.loc[vid_anls_frame["plate_id"] == plate_id_video]
    analysis_folder = "/projects/0/einf914/analysis_videos/CocoTransport/"
    analysis_folder = f"{analysis_folder}{plate_id_video}/"

    img_infos = glob.glob(f"{analysis_folder}/**/video_data_network.json", recursive=True)
    vid_anls_frame = pd.DataFrame()
    add_infos = []
    for address in img_infos:
        add_infos.append(pd.read_json(address, orient="index").T)
    vid_anls_frame = pd.concat([vid_anls_frame] + add_infos, ignore_index=True)

    vid_anls_frame = vid_anls_frame.sort_values("unique_id").reset_index(drop=True)
    vid_anls_frame_select_network = vid_anls_frame.loc[vid_anls_frame["plate_id"] == plate_id_video]
    vid_anls_frame_merged = vid_anls_frame_select.merge(
    vid_anls_frame_select_network[['xpos_network', 'ypos_network', 'unique_id']], on='unique_id')
    vid_anls_frame_merged["analysis_folder"] = analysis_folder_root
    vid_anls_frame_merged["videos_folder"] = [
        str(Path(videos_folder) / entry["folder"])
        for index, entry in vid_anls_frame_merged.iterrows()
    ]
    data_obj = HighmagDataset(vid_anls_frame_merged, analysis_folder_root, videos_folder)
    return(data_obj)