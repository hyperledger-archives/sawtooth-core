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
PROJECT(sawtooth C CXX)

SET (CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

INCLUDE(cpplint)

SET(EXECUTABLE_OUTPUT_PATH ${CMAKE_BINARY_DIR}/bin)
SET(LIBRARY_OUTPUT_PATH ${CMAKE_BINARY_DIR}/lib)

FIND_PACKAGE (Threads REQUIRED)
FIND_LIBRARY(ZMQ_LIB zmq)

FILE(GLOB src "src/*.cpp" "src/*.h" )
SOURCE_GROUP("Src" FILES ${src})

FILE(GLOB inc "include/sawtooth/*.h" )
SOURCE_GROUP("Include" FILES ${inc})

INCLUDE_DIRECTORIES(${CMAKE_CURRENT_BINARY_DIR})

IF( UNIX )
    SET(CMAKE_CXX_FLAGS "-std=c++11" ${CMAKE_CXX_FLAGS})
ENDIF()

INCLUDE_DIRECTORIES("include")

ADD_SUBDIRECTORY(proto)

#cpplint(${PROJECT_NAME} ${src} ${inc
ADD_LIBRARY(${PROJECT_NAME} STATIC ${src} ${inc} ${protos} ${PROTO_HDRS} ${PROTO_SRCS})
TARGET_LINK_LIBRARIES(${PROJECT_NAME} PUBLIC proto )
TARGET_LINK_LIBRARIES(${PROJECT_NAME} INTERFACE protobuf )
TARGET_LINK_LIBRARIES(${PROJECT_NAME} INTERFACE zmq)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} INTERFACE zmqpp)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} INTERFACE log4cxx)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} INTERFACE cryptopp)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} PRIVATE Threads::Threads)

add_subdirectory(../examples/intkey_cxx examples/intkey_cxx)