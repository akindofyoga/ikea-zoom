FROM nvidia/cuda:10.1-cudnn7-devel-ubuntu18.04
MAINTAINER Satyalab, satya-group@lists.andrew.cmu.edu

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update --fix-missing \
    && apt-get upgrade -y \
    && apt-get install -y \
    --no-install-recommends \
    apt-utils

RUN apt-get install -y \
    build-essential \
    libopencv-dev \
    python3 \
    python3-dev \
    python3-pip \
    libprotobuf-dev \
    libleveldb-dev \
    libsnappy-dev \
    libhdf5-serial-dev \
    libatlas-base-dev \
    protobuf-compiler \
    libboost-all-dev \
    libgflags-dev \
    libgoogle-glog-dev \
    liblmdb-dev \
    wget

# fix bug for hdf5 for Caffe. See https://github.com/NVIDIA/DIGITS/issues/156
RUN cd /usr/lib/x86_64-linux-gnu && ln -s libhdf5_serial.so libhdf5.so && \
    ln -s libhdf5_serial_hl.so libhdf5_hl.so

RUN python3 -m pip install --upgrade pip
