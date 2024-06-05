# docker build -t webgme .
# docker run --name webgme -p 8888:8888 -e NODE_ENV='docker' webgme

FROM node:hydrogen
RUN apt-get update
RUN apt-get install -y git

RUN mkdir /usr/app

WORKDIR /usr/app

# copy app source
ADD . /usr/app/

# Install node-modules
RUN npm install

CMD ["npm", "start"]
