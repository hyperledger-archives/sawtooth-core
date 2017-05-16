# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#------------------------------------------------------------------------------
CMAKE_MINIMUM_REQUIRED(VERSION 3.5)
PROJECT(sawtooth CXX)

FIND_PACKAGE(Protobuf REQUIRED)

FILE(GLOB protos "../../../protos/*.proto" )
SOURCE_GROUP("Proto" FILES ${src})
PROTOBUF_GENERATE_CPP(PROTO_SRCS PROTO_HDRS ${protos})
SOURCE_GROUP("Proto-Generated" FILES ${PROTO_SRCS} ${PROTO_HDRS})

INCLUDE_DIRECTORIES(${PROTOBUF_INCLUDE_DIR})

ADD_LIBRARY(proto ${PROTO_HDRS} ${PROTO_SRCS})
