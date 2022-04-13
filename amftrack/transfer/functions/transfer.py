from tqdm.autonotebook import tqdm
import dropbox
import os

from zipfile import ZipFile, ZIP_DEFLATED
import os
from os.path import basename
import requests
# create a ZipFile object
from subprocess import call

from time import sleep
def zip_file(origin,target,depth=2):
    with ZipFile(target, 'w',compression=ZIP_DEFLATED) as zipObj:
       # Iterate over all the files in directory
        tot=0
        for folderName, subfolders, filenames in os.walk(origin):
            for filename in filenames:
                tot+=1
        with tqdm(total=tot, desc="zipping", leave=False) as pbar:
            for folderName, subfolders, filenames in os.walk(origin):
                for filename in filenames:
                    #create complete filepath of file in directory
                    filePath = os.path.join(folderName, filename)
                    filePath = os.path.normpath(filePath)
                    # Add file to zip
                    place = filePath.replace(origin,'')
                    zipObj.write(filePath, place)
                    pbar.update(1)
                    
def unzip_file(origin,target,depth=2):
    with ZipFile(origin, 'r') as zipy:
        zipy.extractall(target)
        
def upload(
    access_token,
    file_path,
    target_path,
    timeout=900,
    chunk_size=4 * 1024 * 1024,
):
    dbx = dropbox.Dropbox(access_token, timeout=timeout)
    with open(file_path, "rb") as f:
        file_size = os.path.getsize(file_path)
        while True:
            try:
                if file_size <= chunk_size:
                    dbx.files_upload(f.read(), target_path, mode=dropbox.files.WriteMode.overwrite)
                    #Overwriting files by default
                else:

                        with tqdm(total=file_size, desc="Uploaded", leave=False) as pbar:
                            upload_session_start_result = dbx.files_upload_session_start(
                                f.read(chunk_size)
                            )
                            pbar.update(chunk_size)
                            cursor = dropbox.files.UploadSessionCursor(
                                session_id=upload_session_start_result.session_id,
                                offset=f.tell(),
                            )
                            commit = dropbox.files.CommitInfo(path=target_path, mode=dropbox.files.WriteMode.overwrite) #Overwriting files by default
                            while f.tell() < file_size:
                                if (file_size - f.tell()) <= chunk_size:
                                    dbx.files_upload_session_finish(
                                            f.read(chunk_size), cursor, commit
                                    )
                                else:
                                    dbx.files_upload_session_append(
                                        f.read(chunk_size),
                                        cursor.session_id,
                                        cursor.offset,
                                    )
                                    cursor.offset = f.tell()
                                pbar.update(chunk_size)
            except (requests.exceptions.RequestException,dropbox.exceptions.ApiError) as e:
                print("error")
                sleep(60)
                continue
            break
            
                
                    
def download(
    access_token,
    file_path,
    target_path,
end = ''):
    dbx = dropbox.Dropbox(access_token)
    while True:
        try:
            with open(target_path, "wb") as f:
                metadata, res = dbx.files_download(path=f'{file_path}{end}')
                f.write(res.content)
        except (requests.exceptions.RequestException,dropbox.exceptions.ApiError) as e:
            sleep(60)
            continue
        break
        
def sync_fold(origin,target):
    cmd = f'rsync --update -avh {origin} {target}'
    # print(cmd)
    call(cmd,shell=True)