#!/bin/bash

sudo find gitea/data -mindepth 1 ! -name '.gitignore' -delete

sudo find webgme/data -mindepth 1 ! -name '.gitignore' -delete

rm -f depi/.depi_session_key
sudo rm -rf depi/.doltcfg
sudo rm -rf depi/.dolt
sudo rm -rf depi/.dolt_dropped_databases
