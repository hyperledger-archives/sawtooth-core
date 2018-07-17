FROM rust:latest

RUN apt-get update && apt-get install -y unzip libzmq3-dev

# For Building Protobufs
RUN curl -OLsS https://github.com/google/protobuf/releases/download/v3.5.1/protoc-3.5.1-linux-x86_64.zip \
 && unzip protoc-3.5.1-linux-x86_64.zip -d protoc3 \
 && rm protoc-3.5.1-linux-x86_64.zip
RUN apt-get update && apt-get install -y protobuf-compiler

WORKDIR /project/sawtooth-core
COPY . /project/sawtooth-core

ENV PATH=$PATH:/project/sawtooth-core/families/battleship/battleship_rust/target/debug/

RUN cd families/battleship/battleship_rust && cargo build

CMD battleship-tp
