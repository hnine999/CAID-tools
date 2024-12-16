# source versions && docker build -f Dockerfile.front-end --build-arg "DEPI_IMPL=$DEPI_IMPL" --build-arg "WEBGME_DEPI=$WEBGME_DEPI" --build-arg "GSN_ASSURANCE=$GSN_ASSURANCE" -t caid-front-end .
# docker run --rm --name caid-fe -p 4000:4000 --network="host" caid-front-end

ARG DEPI_IMPL
ARG WEBGME_DEPI
ARG GSN_ASSURANCE
ARG theiaDocker

FROM git.isis.vanderbilt.edu:5050/aa-caid/depi-impl/depi-vsix:${DEPI_IMPL} AS depi-vsix
FROM git.isis.vanderbilt.edu:5050/aa-caid/webgme-depi/webgme-depi-vsix:${WEBGME_DEPI} AS webgme-depi-vsix
FROM git.isis.vanderbilt.edu:5050/aa-caid/gsn-domain/gsn-assurance-vsix:${GSN_ASSURANCE} AS gsn-assurance-vsix

# PRETTY_NAME="Debian GNU/Linux 11 (bullseye)"
# NAME="Debian GNU/Linux"
# VERSION_ID="11"
# VERSION="11 (bullseye)"
FROM $theiaDocker

RUN mkdir -p /home/theia/.theia-ide/plugins

# Copy over vsix-es
COPY --from=depi-vsix /depi.vsix /home/theia/.theia-ide/plugins/depi.vsix
COPY --from=webgme-depi-vsix /webgme-depi.vsix /home/theia/.theia-ide/plugins/webgme-depi.vsix
COPY --from=gsn-assurance-vsix /gsn-assurance.vsix /home/theia/.theia-ide/plugins/gsn-assurance.vsix

# Add all the repositores (currently localhost only)
RUN mkdir /home/project/.theia
COPY --chown=theia Files/settings.json /home/project/.theia/settings.json
COPY --chown=theia clone_repos.sh /home/project/clone_repos.sh

RUN git config --global user.email "demo@mail.com"
RUN git config --global user.name "demo"

USER root
COPY Files/start.sh /usr/local/bin/start.sh
RUN chmod 755 /usr/local/bin/start.sh

USER theia
WORKDIR /home/projects

ENTRYPOINT []
CMD [ "bash", "/usr/local/bin/start.sh" ]
