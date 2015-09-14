#!/usr/bin/env python

import os
import sys

import pipebuilder as pb
from pipebuilder import tracking

#affine_iterations = '10000x10000x10000x10000x10000'
affine_iterations = '1x1x1'

CLOBBER_EXISTING_OUTPUTS = False

INPUT_PATH = config.config.get('data_locations', 'input_path')
ATLAS_PATH = config.config.get('data_locations', 'atlas_construction_path')
REGISTRATION_PATH = config.config.get('data_locations', 'registration_path')

if __name__ == '__main__':

    ########################
    ### Argument parsing ###
    ########################
    subj = sys.argv[1]

    run_server = (len(sys.argv) > 2 and sys.argv[2] == '--server')

    #############################
    ### Set up atlas and data ###
    #############################

    ## Atlas
    atlas = pb.Dataset(ATLAS_PATH, 'atlas{extension}', None)
    atlas.add_mandatory_input()

    ## Subject data
    dataset = pb.Dataset(
                REGISTRATION_PATH,
                # How are the inputs to the pipeline stored?
                os.path.join(INPUT_PATH , '{subj}{feature}{extension}'),
                # How should intermediate files be stored?
                '{subj}/{subj}{feature}{extension}',
                # Where should logs be stored?
                '{subj}/logs/',
                )

    # This specifies that all inputs are mandatory (i.e., PipeBuilder will
    # fail fast if any input doesn't exist on the filesystem).
    dataset.add_mandatory_input()
    #############################
    ### Registration pipeline ###
    #############################
    atlas_img = atlas.get_original(extension='.nii.gz')
    subj_img = dataset.get_original(subj=subj, feature='', extension='.nii.gz')
    subj_label = dataset.get_original(subj=subj, feature='_partialLungLabelMap', extension='.nii.gz')

    ### Step I
    affine_atlas_reg = pb.ANTSCommand("affine registration of subj to atlas",
            moving=subj_img,
            fixed=atlas_img,
            output_folder=dataset.get_folder(subj=subj),
            metric='CC',
            radiusBins=5,
            affine_iterations=affine_iterations,
            other='--use-Histogram-Matching --MI-option 32x16000',
            method='affine')

    affine_subj = pb.ANTSWarpCommand.make_from_registration_sequence(
            "Warp subj_img AFFINELY to atlas",
            moving = subj_img,
            reference = atlas_img,
            reg_sequence = [affine_atlas_reg],
            inversion_sequence = ['forward'],
            output_folder = dataset.get_folder(subj=subj),
            useNN = False)


    for path in [dataset.get_folder(subj=subj),
            dataset.get_log_folder(subj=subj)]:
        try:
            print(path)
            os.mkdir(path)
        except:
            pass

    ### Generate script file and SGE qsub file
    tracker = tracking.Tracker(pb.Command.all_commands, pb.Dataset.all_datasets)

    ###
    tracker.compute_dependencies()
    # tracker = None
    log_folder = dataset.get_log_folder(subj=subj)
    if run_server:
        tracking.run_server()

    else:
        pb.Command.generate_code_from_datasets([dataset, atlas], log_folder, subj, sge=True,
                wait_time=1)
    

