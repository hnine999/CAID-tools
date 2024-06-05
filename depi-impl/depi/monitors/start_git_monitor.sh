#!/bin/sh
python $(dirname $0)/src/depi_monitors/git_monitor.py --depi localhost:5150 --user mark --password mark --toolid git --port 3003$*
