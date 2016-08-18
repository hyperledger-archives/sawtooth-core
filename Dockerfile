FROM ubuntu:trusty

RUN sh -c "echo deb http://archive.ubuntu.com/ubuntu trusty-backports main restricted universe multiverse >> /etc/apt/sources.list"
RUN sh -c "echo deb-src http://archive.ubuntu.com/ubuntu trusty-backports main restricted universe multiverse >> /etc/apt/sources.list"

RUN apt-get update && apt-get install -y -q \
   git \
   make \
   openssh-server \
   openjdk-7-jdk \
   python-pip \
   wget \
   zip \
   && apt-get clean \
   && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y -q \
   connect-proxy \
   g++ \
   libcrypto++-dev \
   libjson0 \
   libjson0-dev \
   python-all-dev \
   python-dev \
   python-enum \
   python-setuptools \
   python-stdeb \
   python-twisted \
   python-twisted-web \
   swig3.0 \
   python-numpy \
   && apt-get clean \
   && rm -rf /var/lib/apt/lists/*

RUN pip install sphinx && \
   pip install sphinxcontrib-httpdomain && \
   pip install nose2 && \
   pip install coverage && \
   pip install cov-core && \
   pip install pep8 && \
   pip install pylint && \
   pip install setuptools-lint && \
   pip install sphinx_rtd_theme

RUN ln -s /usr/bin/swig3.0 /usr/bin/swig

RUN pip install https://pypi.python.org/packages/source/c/cbor/cbor-0.1.24.tar.gz
RUN pip install https://pypi.python.org/packages/2.7/c/colorlog/colorlog-2.6.0-py2.py3-none-any.whl
RUN pip install https://pypi.python.org/packages/source/p/pybitcointools/pybitcointools-1.1.15.tar.gz

ENV PYTHONPATH=/project/sawtooth-core:/project/sawtooth-validator:/project/sawtooth-mktplace:/project/sawtooth-core/build/lib.linux-x86_64-2.7

COPY ./sawtooth-core /project/sawtooth-core
COPY ./sawtooth-validator /project/sawtooth-validator
COPY ./sawtooth-mktplace /project/sawtooth-mktplace
COPY ./sawtooth-docs /project/sawtooth-docs

WORKDIR /project/sawtooth-core
RUN python setup.py build

COPY ./sawtooth-validator /project/sawtooth-validator
WORKDIR /project/sawtooth-validator

RUN mkdir -p /var/log/sawtooth-validator
RUN mkdir -p /var/lib/sawtooth-validator

COPY ./sawtooth-dev-tools/entrypoint.sh /project/sawtooth-validator
ENTRYPOINT ["./entrypoint.sh"]

