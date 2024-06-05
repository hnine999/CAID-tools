#!/bin/sh
python $(dirname $0)/git_monitor.py --depi localhost:5150 --user mark --password mark --toolid git-gsn --port 3002 $*
