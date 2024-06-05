#!/bin/bash

sudo find gitea/data -mindepth 1 ! -name '.gitignore' -delete

sudo find webgme/data -mindepth 1 ! -name '.gitignore' -delete
