# docker build -t depi -f ./server/Dockerfile .
# docker run --name depi -p 5150:5150 -e DEPI_CONFIG='mem_notls' depi
FROM python:3.11-buster

RUN apt-get update && apt-get install -y git python3-dev default-libmysqlclient-dev build-essential pkg-config default-mysql-client libc6

RUN mkdir /dolt
ADD ./doltamd /dolt/
ADD ./setup_dolt.sh /dolt/
ADD ./start_dolt.sh /dolt/
ADD ./depi_mysql.sql /dolt/

RUN /dolt/setup_dolt.sh

CMD ["/dolt/start_dolt.sh"]
