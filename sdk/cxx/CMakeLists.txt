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

FILE(GLOB inc "include/*.h" "include/sawtooth/*.h" )
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

INSTALL(DIRECTORY ${LIBRARY_OUTPUT_PATH} DESTINATION .)

FILE(GLOB inc_sdk "include/*.h")
INSTALL(FILES ${inc_sdk} DESTINATION include/sawtooth_sdk)
INSTALL(FILES ../../LICENSE DESTINATION include/sawtooth_sdk)

SET(CPACK_PACKAGE_NAME "sawtooth-cxx-sdk")
SET(CPACK_PACKAGE_VENDOR "Hyperledger: https://hyperledger.org")
SET(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Hyperledger Sawtooth C++ SDK, https://sawtooth.hyperledger.org")
SET(CPACK_PACKAGE_VERSION "$ENV{sawtooth_version}")
SET(CPACK_PACKAGE_VERSION_MAJOR "$ENV{sawtooth_major}")
SET(CPACK_PACKAGE_VERSION_MINOR "$ENV{sawtooth_minor}")
SET(CPACK_PACKAGE_VERSION_PATCH "$ENV{sawtooth_patch}")

SET(CPACK_PACKAGE_INSTALL_DIRECTORY "Sawtooth_SDK_CXX")
SET(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_CURRENT_SOURCE_DIR}/../../LICENSE")


SET(CPACK_GENERATOR "DEB")
SET(CPACK_DEBIAN_PACKAGE_MAINTAINER "Hyperledger - https://hyperledger.org")
# setting arch below causses dependency issues because libs are often build with amd64
# SET(CPACK_DEBIAN_PACKAGE_ARCHITECTURE "x86_64")
SET(CPACK_DEBIAN_PACKAGE_HOMEPAGE https://sawtooth.hyperledger.org)

# uncomment line below if a custom preinst(all) script is needed
#SET(CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA "${CMAKE_CURRENT_SOURCE_DIR}/preinst")

SET(CPACK_DEBIAN_PACKAGE_DEPENDS libcrypto++-dev,liblog4cxx-dev,libzmqpp-dev,libtool,libssl-dev,protobuf)

#This one must be the last
INCLUDE(CPack)


