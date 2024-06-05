# docker build -t depi-vsix .
# This image builds vsix inside docker image - and the cleans up the code.
# Use this image in a multi-stage Dockerfile and copy /depi.vsix
# COPY --from=0 /depi.vsix /depi.vsix
FROM node:hydrogen
RUN apt-get update && apt-get install -y git
RUN npm install --global @vscode/vsce

RUN mkdir /vsix-source
COPY blackboard-graph /vsix-source/blackboard-graph
COPY vscode-depi /vsix-source/vscode-depi
COPY ./install-and-build-vsix.sh /vsix-source/install-and-build-vsix.sh

RUN cd /vsix-source && ./install-and-build-vsix.sh

RUN mv /vsix-source/vscode-depi/depi*.vsix /depi.vsix

RUN rm -rf /vsix-source