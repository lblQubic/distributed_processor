# syntax=docker/dockerfile:1
FROM ubuntu:20.04

#configure verilator
RUN apt-get update
RUN apt-get install -y git perl python3 make autoconf g++ flex bison ccache
RUN apt-get install -y libgoogle-perftools-dev numactl perl-doc
RUN apt-get install -y libfl2  # Ubuntu only (ignore if gives error)
RUN apt-get install -y libfl-dev  # Ubuntu only (ignore if gives error)
RUN apt-get install -y zlibc zlib1g zlib1g-dev  # Ubuntu only (ignore if gives error)
RUN git clone https://github.com/verilator/verilator --branch v4.106 --depth 1
WORKDIR ./verilator
RUN autoconf
RUN ./configure
RUN make
RUN make install
WORKDIR /

#configure python+cocotb
RUN apt-get install -y pip
RUN pip install cocotb numpy matplotlib ipdb
