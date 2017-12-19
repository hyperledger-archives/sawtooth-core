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
cmake_minimum_required (VERSION 3.5)
PROJECT(intkey_tp_cxx)

SET(EXECUTABLE_OUTPUT_PATH ${CMAKE_BINARY_DIR}/bin)
#SET(LIBRARY_OUTPUT_PATH ${CMAKE_BINARY_DIR}/../../../cxx/build/lib)
#SET(LIBRARY_OUTPUT_PATH ../../../cxx/build/lib)

FILE(GLOB src "*.cpp" "*.h" "*.hpp" "../proto/cxx/*.cc" "../proto/cxx/*.h")
SOURCE_GROUP("Src" FILES ${src})

#INCLUDE_DIRECTORIES(${CMAKE_BINARY_DIR}/../../../cxx/build/)
INCLUDE_DIRECTORIES(${CMAKE_BINARY_DIR}/../../../cxx/include/)
INCLUDE_DIRECTORIES(/usr/include/sawtooth_sdk) # YYY - dev specific


IF( UNIX )
    SET(CMAKE_CXX_FLAGS "-std=c++11" ${CMAKE_CXX_FLAGS})
ENDIF()

#link_directories(/project/sawtooth-core/sdk/cxx/build/lib)
link_directories(${CMAKE_BINARY_DIR}/../../../cxx/build/lib)




ADD_EXECUTABLE(${PROJECT_NAME} ${src} )

TARGET_LINK_LIBRARIES(${PROJECT_NAME} sawtooth )

TARGET_LINK_LIBRARIES(${PROJECT_NAME} proto )
TARGET_LINK_LIBRARIES(${PROJECT_NAME} protobuf )
TARGET_LINK_LIBRARIES(${PROJECT_NAME} zmq)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} zmqpp)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} log4cxx)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} cryptopp)
TARGET_LINK_LIBRARIES(${PROJECT_NAME} pthread)
