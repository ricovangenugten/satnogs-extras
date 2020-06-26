# LRPT processor post observation script

See scripts/process_meteor.py

This script picks up LRPT IQ recordings from wherever a satnogs flowgraph 
puts them, processes them and places output images in the satnogs recorded 
data directory, where satnogs-client will pick them up and upload them to the
corresponding observation.

You can use any satnogs flowgraph that produces IQ data with a wide enough
bandwidth, I used the satnogs FSK flowgraph since it outputs IQ data at a
sample rate of 4 times the baud rate which is 7200 * 4 = 28800 for Meteor M2,
more than enough for LRPT. To configure the flowgraph that is used for LRPT
edit the satnogs-client settings.py. There is a map describing which
flowgraph to use for which modulation. Copy the map item with the key 'FSK', leave
copied value the same and change the copied key to 'LRPT'.

This script can be directly run as a post observation script. It depends on
meteor_demod and medet, so be sure to install those on your system and configure
the paths to the binaries below. Also update the data paths to suit your system.
Then, in satnogs_setup enable iq dumping to the path as specified in IQ_NEW_PATH
Do not use /var/tmp to store the IQ files on a Raspberry Pi, as this is a ramdisk 
that could potentially be filled up quickly. Then configure this script as post
observation script using the following line:

/path/to/process_meteor.py --id {{ID}} --tle {{TLE}}
