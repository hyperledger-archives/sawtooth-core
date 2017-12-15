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
# ------------------------------------------------------------------------------

CMAKE_MINIMUM_REQUIRED(VERSION 3.2 FATAL_ERROR)
PROJECT(libpoet-bridge C CXX)

# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Source Code
# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
IF(MSVC)
    SET(PLATFORM_DIR_NAME windows)
ELSE()
    SET(PLATFORM_DIR_NAME linux)
ENDIF()

SET(C11_SUPPORT ../../../common/c11_support)

FILE(GLOB PROJECT_HEADERS *.h ../libpoet_shared/*.h ../libpoet_shared/${PLATFORM_DIR_NAME}/*.h ${C11_SUPPORT}/${PLATFORM_DIR_NAME}/*.h)
FILE(GLOB PROJECT_SOURCES *.cpp ${PLATFORM_DIR_NAME}/*.cpp ../libpoet_shared/*.cpp ../libpoet_shared/${PLATFORM_DIR_NAME}/*.cpp ${C11_SUPPORT}/${PLATFORM_DIR_NAME}/*.cpp)
SOURCE_GROUP("Source" FILES ${PROJECT_HEADERS} ${PROJECT_SOURCES})

INCLUDE_DIRECTORIES(. ${C11_SUPPORT} ${C11_SUPPORT}/${PLATFORM_DIR_NAME})
INCLUDE_DIRECTORIES(../libpoet_shared ../libpoet_shared/${PLATFORM_DIR_NAME})

IF(MSVC)
    SET(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} /Zi")
    SET(CMAKE_SHARED_LINKER_FLAGS_RELEASE "${CMAKE_SHARED_LINKER_FLAGS_RELEASE} /DEBUG /OPT:REF /OPT:ICF")
ELSE()
    # These compiler and linker flags for g++/gcc were derived from the make
    # files provided with the SGX sample apps
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -m64")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIC")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-attributes")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -m64")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -O2")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--no-undefined")
ENDIF()

SGX_EDGE_UNTRUSTED(${LIBPOET_ENCLAVE_EDL} PROJECT_EDGE_SOURCES)
SOURCE_GROUP("Generated" FILES ${PROJECT_EDGE_SOURCES})

ADD_DEFINITIONS(-D LIBPOET_BUILD)
SET_RUNTIME(DYNAMIC)

# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Compile targets
# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# CMake likes to prepend "lib" to project name when creating library...since we
# already have lib in the project name, liblibpoet-bridge is stupid.  Stop CMake
# from doing it.
IF(NOT MSVC)
    SET(CMAKE_SHARED_LIBRARY_PREFIX "")
ENDIF()

ADD_LIBRARY(${PROJECT_NAME} SHARED ${PROJECT_EDGE_SOURCES} ${PROJECT_HEADERS} ${PROJECT_SOURCES})

# If we are using MSVC then it is fine to simply set the target link libraries.
# However, if we are using Linux, then find the libraries to get the absolute
# path and add them that way and DO NOT add the linker path using
# LINK_DIRECTORIES as it will add the -rpath option to the linker and this is
# bad as when installing the SDK the version of libsgx_uae_service.so in the SDK
# lib64 directory is different than the one in /usr/lib
IF(MSVC)
    TARGET_LINK_LIBRARIES( ${PROJECT_NAME} PRIVATE  ${SGX_LIBS_UNTRUSTED})
ELSE()
    FOREACH(lib ${SGX_LIBS_UNTRUSTED})
        FIND_LIBRARY(ABS-${lib} NAMES ${lib} PATHS "$ENV{SGXSDKInstallPath}/lib64")
        SET(ABSOLUTE_SGX_LIBS_UNTRUSTED ${ABSOLUTE_SGX_LIBS_UNTRUSTED} ${ABS-${lib}})
    ENDFOREACH(lib)
    TARGET_LINK_LIBRARIES( ${PROJECT_NAME} PRIVATE ${ABSOLUTE_SGX_LIBS_UNTRUSTED})
ENDIF()


ADD_CUSTOM_COMMAND(
    TARGET ${PROJECT_NAME}
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "${DEPS_DIR}/bin"
    COMMAND ${CMAKE_COMMAND} -E make_directory "${DEPS_DIR}/lib"
    COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:${PROJECT_NAME}>" "${DEPS_DIR}/bin"
    COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_LINKER_FILE:${PROJECT_NAME}>" "${DEPS_DIR}/lib"
)
