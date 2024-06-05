#!/bin/sh
python $(dirname $0)/git_verifier.py --depi localhost:5150 --user mark --password mark --toolid git --port 3003$*
