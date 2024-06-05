# docker build -t git-monitor -f ./monitors/Dockerfile .
FROM python:3.11-buster

RUN apt-get update && apt-get install -y git python3-dev default-libmysqlclient-dev build-essential pkg-config

RUN mkdir /proto
ADD ./proto /proto/

# copy app source
RUN mkdir /app
ADD ./monitors /app/
WORKDIR /app

RUN pip install .

CMD ["python", "-u", "./src/depi_monitors/git_monitor.py"]