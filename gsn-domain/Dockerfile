# docker build -t depi-vsix .
# This image contains the vsix
# Use this image in a multi-stage Dockerfile and copy /gsn-assurance.vsix
# COPY --from=0 /gsn-assurance.vsix <target>
FROM node:hydrogen
COPY /gsn-vscode-xtext/vscode-extension-self-contained/build/vscode/vscode-extension-self-contained-*.vsix /gsn-assurance.vsix