#!/usr/bin/env python
#
#   Meteor Decoder Processor
#   Initial version for Meteor M2:
#   Mark Jessop <vk5qi@rfhead.net> 2017-09-01
#   This version:
#   Rico van Genugten @PA3RVG 2019-11-19
#
#   This script picks up LRPT IQ recordings from wherever a satnogs flowgraph 
#   puts them, processes them and places output images in the satnogs recorded 
#   data directory, where satnogs-client will pick them up and upload them to the
#   corresponding observation.
#
#   You can use any satnogs flowgraph that produces IQ data with a wide enough
#   bandwidth, I used the satnogs FSK flowgraph since it outputs IQ data at a
#   sample rate of 4 times the baud rate which is 7200 * 4 = 28800 for Meteor M2,
#   more than enough for LRPT. To configure the flowgraph that is used for LRPT
#   edit the satnogs-client settings.py. There is a map describing which
#   flowgraph to use for which modulation. Copy the map item with the key 'FSK', leave
#   copied value the same and change the copied key to 'LRPT'.
#
#   This script can be directly run as a post observation script. It depends on
#   meteor_demod and medet, so be sure to install those on your system and configure
#   the paths to the binaries below. Also update the data paths to suit your system.
#   Then, in satnogs_setup enable iq dumping to the path as specified in IQ_NEW_PATH
#   Do not use /var/tmp to store the IQ files on a Raspberry Pi, as this is a ramdisk 
#   that could potentially be filled up quickly. Then configure this script as post
#   observation script using the following line:
#
#   /path/to/this/script.py --id {{ID}} --tle {{TLE}}
#
#

from glob import glob
import subprocess
import os
import shutil
from time import sleep
import argparse
import re


# main path where all meteor files are. The following subdirs
# are expected: /new_iq, /intermediate, /complete, /bin
DATA_PATH         = "/datadrive/meteor"

# Where to place the complete images.
DESTINATION_DIR   = "/tmp/.satnogs/data"

# Whether you want to delete input files when complete
DELETE_COMPLETE_FILES = False

# Paths to binaries we need. If these binaries are not on $PATH, change the
# paths below to point to the appropriate place.
MEDET_PATH        = DATA_PATH + "/bin/medet_arm"
METEOR_DEMOD_PATH = DATA_PATH + "/bin/meteor_demod"
CONVERT_PATH      = "convert"

# Derived paths
IQ_NEW_PATH       = DATA_PATH + "/new_iq/last_obs.iq"
INTERMEDIATE_DIR  = DATA_PATH + "/intermediate"
COMPLETE_DIR      = DATA_PATH + "/complete"

# NORAD IDs
METEOR_M2_1_ID = 40069
METEOR_M2_2_ID = 44387

# Constants for the color channels, BGR order to match medet output
CH_R = 2
CH_G = 1
CH_B = 0

# Which APIDs to look for
APIDS = {
  CH_R: '68',
  CH_G: '65',
  CH_B: '64'
}

# Color mapping to produce false color image
VIS_IMAGE_CHS = {
  CH_R: CH_G,
  CH_G: CH_G,
  CH_B: CH_B}

# Which channel to use for ir image
IR_IMAGE_CH = CH_R

# medet default arguments to produce separate images for each individual channel
MEDET_DEF_ARGS = ['-q', '-s',
                  '-r', APIDS[CH_R], '-g', APIDS[CH_G], '-b', APIDS[CH_B]]

# medet extra arguments per sat
MEDET_EXTRA_ARGS = {
  METEOR_M2_1_ID: [],
  METEOR_M2_2_ID: ['-diff']}

# meteor_demod args to produce an s-file from an iq-file for M2 2
METEOR_DEMOD_DEF_ARGS = ['-B', '-R', '1000', '-f', '24', '-b', '300',
                         '-s', '288000', '-r', '72000', '-d', '1000']

# meteor demod args per sat
METEOR_DEMOD_EXTRA_ARGS = {
  METEOR_M2_1_ID: [],
  METEOR_M2_2_ID: ['-m', 'oqpsk']}

# Wait for a bit before processing, to avoid clashing with waterfall processing
# and running out of RAM.
WAIT_TIME = 120

def convert_images(output_name):
    """
    Use the 'convert' utility (from imagemagick) to convert
    a set of resultant METEOR images.
    """

    fc_file = output_name + "_fc.png"
    ir_file = output_name + "_ir.png"

    convert_cmd_fc = [CONVERT_PATH,
                      "%s_%d.bmp" % (output_name, VIS_IMAGE_CHS[CH_R]),
                      "%s_%d.bmp" % (output_name, VIS_IMAGE_CHS[CH_G]),
                      "%s_%d.bmp" % (output_name, VIS_IMAGE_CHS[CH_B]),
                      "-channel", "RGB", "-combine",
                      fc_file]

    convert_cmd_ir = [CONVERT_PATH,
                      "%s_%d.bmp" % (output_name, IR_IMAGE_CH),
                      ir_file]
    print(convert_cmd_fc)
    return_code = subprocess.call(convert_cmd_fc)
    print("convert fc returned %d " % return_code)

    print(convert_cmd_ir)
    return_code = subprocess.call(convert_cmd_ir)
    print("convert ir returned %d " % return_code)

    generated_images = []
    if os.path.isfile(fc_file):
        generated_images.append(fc_file)

    if os.path.isfile(ir_file):
        generated_images.append(ir_file)

    return generated_images


def run_medet(source_file, output_name, extra_args):
    """
    Attempt to run the medet meteor decoder over a file.
    """

    medet_command = [MEDET_PATH, source_file, output_name]
    medet_command.extend(MEDET_DEF_ARGS)
    medet_command.extend(extra_args)
    print(medet_command)
    return_code = subprocess.call(medet_command)

    print("medet returned %d " % return_code)

    return return_code


def generate_s_file(iq_file, sat_id):
    """
    Attempt to run meteor_demod over an iq file to obtain an s-file
    """

    s_file = os.path.splitext(iq_file)[0] + ".s"
    dem_cmd = [METEOR_DEMOD_PATH]
    dem_cmd.extend(METEOR_DEMOD_DEF_ARGS)
    dem_cmd.extend(METEOR_DEMOD_EXTRA_ARGS[sat_id])
    dem_cmd.extend(['-o', s_file, iq_file])

    print(dem_cmd)

    with open(os.path.dirname(s_file) + "/" + 'demodulate.log', 'w') as f_out:
        return_code = subprocess.call(dem_cmd, stdout=f_out)

    print("meteor_demod returned %d " % return_code)

    if os.path.isfile(s_file):
        print("meteor_demod produced s file")
    else:
        print("meteor_demod did not produce s file")
        s_file = None

    return s_file


def process_s_file(s_file, sat_id):
    """
    Process an s file and place the generated images in the satnogs data folder
    """

    output_name = os.path.splitext(s_file)[0]

    medet_ret = run_medet(s_file, output_name, MEDET_EXTRA_ARGS[sat_id])

    output_files = []
    if medet_ret == 0:
        output_files = convert_images(output_name)

    if len(output_files) > 0:
        print("Images are created")
        for output_file in output_files:
            shutil.move(output_file, DESTINATION_DIR)
    else:
        print("No images are created")


def handle_complete_files(file_base):
    """
    Move or delete files that we are done processing
    """
    for complete_file in glob("%s*" % file_base):
      if DELETE_COMPLETE_FILES:
          os.remove(complete_file)
      else:
          shutil.move(complete_file, COMPLETE_DIR)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=int, required=True)
    parser.add_argument('--tle', nargs='*')
    parser.add_argument('--sat_id', type=int)
    args = parser.parse_args()

    sat_id = None
    wait_time = 0

    if args.tle:
        tle = " ".join(args.tle)
        match = re.search(r"1 (\d*)U", tle)
        if match is not None:
            sat_id = int(match.group(1))
        wait_time = WAIT_TIME

    if args.sat_id:
        sat_id = args.sat_id
        wait_time = 0

    if sat_id is None:
        parser.print_help()
        exit(-1)

    print("Post observation script for sat id %d" % sat_id)

    if sat_id in [METEOR_M2_1_ID, METEOR_M2_2_ID]:
        pid = os.fork()
        if pid > 0:
            print("Forked, parent quitting")
            exit(0)
    else:
        print("No processing to be done for sat id %d" % sat_id)
        exit(0)

    # Sleep for a bit.
    print("Waiting for %d seconds before processing." % wait_time)
    sleep(wait_time)

    # Search for iq files.
    new_iq_files = glob(IQ_NEW_PATH)

    print("METEOR M2 2: looking for %s " % IQ_NEW_PATH)

    # handle iq files
    for new_iq_file in new_iq_files:

        print("Processing %s " % new_iq_file)

        intermediate_file_base = "%s/data_%d" % (INTERMEDIATE_DIR, args.id)
        moved_iq_file = "%s.iq" % (intermediate_file_base)
        shutil.move(new_iq_file, moved_iq_file)

        # Generate s file
        generated_s_file = generate_s_file(moved_iq_file, sat_id)

        # Process s file if there is one
        if generated_s_file is not None:
            process_s_file(generated_s_file, sat_id)

        # Move or delete processed iq file
        handle_complete_files(intermediate_file_base)

