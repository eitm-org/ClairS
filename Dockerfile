FROM ubuntu:16.04

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PATH=/opt/bin:/opt/conda/bin:$PATH

# update ubuntu packages
RUN apt-get update --fix-missing && \
    yes|apt-get upgrade && \
    apt-get install -y \
        wget \
        bzip2 \
        make \
        g++ \
        time \
        libboost-graph-dev && \
    rm -rf /bar/lib/apt/lists/*

WORKDIR /opt/bin

# install anaconda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniconda3-latest-Linux-x86_64.sh && \
    conda config --add channels defaults && \
    conda config --add channels bioconda && \
    conda config --add channels conda-forge && \
    conda create -n clair_somatic -c pytorch -c conda-forge -c bioconda clair3 pytorch tqdm torchinfo -y && \
    rm -rf /opt/conda/pkgs/* && \
    rm -rf /root/.cache/pip

ENV PATH /opt/conda/envs/clair_somatic/bin:$PATH
ENV CONDA_DEFAULT_ENV clair_somatic

COPY . .

RUN /bin/bash -c "source activate clair_somatic" && cd /opt/bin/src/realign && \
    g++ -std=c++14 -O1 -shared -fPIC -o realigner ssw_cpp.cpp ssw.c realigner.cpp && \
    g++ -std=c++11 -shared -fPIC -o debruijn_graph -O3 debruijn_graph.cpp && \
    wget http://www.bio8.cs.hku.hk/clair_somatic/models/clair_somatic_models.tar.gz	 -P /opt/models && \
    mkdir -p /opt/conda/envs/clair_somatic/bin/somatic_models && \
    tar -zxvf /opt/models/clair_somatic_models.tar.gz -C /opt/conda/envs/clair_somatic/bin/somatic_models && \
    rm /opt/models/clair_somatic_models.tar.gz && \
    echo "source activate clair_somatic" > ~/.bashrc

