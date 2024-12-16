import docker
import os
from pathlib import Path


print("1\n")
script_directory_path = Path(__file__).parent.absolute()
print("2\n")
os.chdir(script_directory_path)

print("3\n")
theia_docker = os.getenv("theiaDocker")

print(f"theia_docker = {theia_docker}\n")
docker_client = docker.from_env()

print("5\n")
docker_client.images.pull(theia_docker)

print("6\n")
theia_image = docker_client.images.get(theia_docker)

print("7\n")
theia_image_metadata = theia_image.attrs

print("8\n")
theia_entrypoint = theia_image_metadata["Config"]["Entrypoint"]

print("9\n")
cmd_file_directory_path = Path(script_directory_path, "Context", "Files")

print("10\n")
cmd_file_directory_path.mkdir(exist_ok=True)

print("11\n")
cmd_file_path = Path(cmd_file_directory_path, "start.sh")

print(f"cmd_file_path = \"{cmd_file_path}\"\n")
with cmd_file_path.open("w") as output_fp:
    output_fp.write(
f'''#!/bin/bash

cd /home/project || exit 1
bash clone_repos.sh

{" ".join(theia_entrypoint)} /home/project --hostname=0.0.0.0 --port=4000

''')
