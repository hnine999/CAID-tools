# docker build -t depi -f ./server/Dockerfile .
# docker run --name depi -p 5150:5150 -e DEPI_CONFIG='mem_notls' depi
FROM python:3.11-buster

RUN apt-get update && apt-get install -y git python3-dev default-libmysqlclient-dev build-essential pkg-config

RUN mkdir /proto
ADD ./proto /proto/

# copy app source
RUN mkdir /app
ADD ./server /app/
WORKDIR /app

RUN pip install .

CMD ["python", "-u", "run_local.py"]