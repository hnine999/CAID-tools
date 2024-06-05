#!/bin/sh
cd $(dirname $0)
#rlwrap python bb_client.py --depi localhost:5150 --user mark --password mark --project gittest 
rlwrap python bb_client.py --depi localhost:5150 --user patrik --password patrik --project gittest 
