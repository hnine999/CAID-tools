# docker build -t webgme-depi-vsix .
# This image builds vsix inside docker image - and the cleans up the code.
# Use this image in a multi-stage Dockerfile and copy /webgme-depi.vsix
# COPY --from=0 /webgme-depi.vsix <target>
FROM node:hydrogen
RUN apt-get update && apt-get install -y git
RUN npm install --global @vscode/vsce

RUN mkdir /vsix-source
COPY vscode-webgme-depi /vsix-source/vscode-webgme-depi
COPY install-and-build-vsix.sh /vsix-source/install-and-build-vsix.sh

RUN cd /vsix-source && ./install-and-build-vsix.sh

RUN mv /vsix-source/vscode-webgme-depi/webgme-depi*.vsix /webgme-depi.vsix

RUN rm -rf /vsix-source