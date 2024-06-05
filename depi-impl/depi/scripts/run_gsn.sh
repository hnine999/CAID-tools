#!/bin/sh
#python $(dirname $0)/git_adaptor.py --depi localhost:5150 --user mark --password mark --toolid git --repo `pwd` $*
python $(dirname $0)/gsn_adaptor.py --depi localhost:5150 --user patrik --password patrik --toolid git-gsn --repo `pwd` $*
