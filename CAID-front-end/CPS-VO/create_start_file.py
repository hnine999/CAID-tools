import docker
import os
from pathlib import Path


script_directory_path = Path(__file__).parent.absolute()
os.chdir(script_directory_path)

theia_docker = os.getenv("theiaDocker")

print(f"theia_docker = {theia_docker}\n")
docker_client = docker.from_env()

docker_client.images.pull(theia_docker)

theia_image = docker_client.images.get(theia_docker)

theia_image_metadata = theia_image.attrs

theia_entrypoint = theia_image_metadata["Config"]["Entrypoint"]

cmd_file_directory_path = Path(script_directory_path, "Context", "Files")

cmd_file_directory_path.mkdir(exist_ok=True)

cmd_file_path = Path(cmd_file_directory_path, "start.sh")

print(f"cmd_file_path = \"{cmd_file_path}\"\n")
with cmd_file_path.open("w") as output_fp:
    output_fp.write(
f'''#!/bin/bash

cd /home/project || exit 1
bash clone_repos.sh

{" ".join(theia_entrypoint)} /home/project --hostname=0.0.0.0 --port=4000

''')
