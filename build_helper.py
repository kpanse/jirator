# -*- coding: utf-8 -*-

import json
import datetime
import os
import zipfile
import shutil
import argparse
from pathlib import Path


def insert_build_info_to_json(metafile):
    with open(metafile, 'r+') as json_data_file:
        cfg = json.load(json_data_file) 
        cfg['dev_build_date'] = timestamp
        dev_build_no = cfg['dev_build_no']
        cfg['dev_build_no'] = dev_build_no + 1
        dev_build_no = cfg['dev_build_no']    
        json_data_file.seek(0)
        json_data_file.truncate()
        json.dump(cfg, json_data_file)
        json_data_file.truncate()

    return dev_build_no


def get_build_info_to_json(metafile):
    with open(metafile, 'r+') as json_data_file:        
        cfg = json.load(json_data_file)         
        dev_build_no = cfg['dev_build_no']
    return dev_build_no


def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))


def zip_build(build_no):
    zip_name = '%s_%s.zip' % ('jirator', build_no)
    zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
    os.chdir('../build')
    zipdir('.', zipf)
    zipf.close()
    os.chdir('../app')

    if not Path('../release').exists():
        Path('../release').mkdir(parents=True, exist_ok=True)

    shutil.move(zip_name, '../release')



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build helper')

    parser.add_argument('-z', action="store_true", default=False)
    parser.add_argument('-j', action="store_true", default=False)
    parser.add_argument('METAFILE', default="app.json")
    args=parser.parse_args()

    global timestamp
    timestamp = datetime.datetime.now().isoformat()
    
    if args.j:
        insert_build_info_to_json(args.METAFILE)
        
    if args.z:
        build_no = get_build_info_to_json(args.METAFILE)
        zip_build(build_no)