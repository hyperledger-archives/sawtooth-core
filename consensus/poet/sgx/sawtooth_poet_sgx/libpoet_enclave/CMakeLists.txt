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
PROJECT(libpoet-enclave C CXX)

# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Source Code
# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
FILE(GLOB PROJECT_HEADERS *.h ../libpoet_shared/*.h)
FILE(GLOB PROJECT_SOURCES *.cpp *.c ../libpoet_shared/*.cpp)
FILE(GLOB PROJECT_EDL *.edl)
FILE(GLOB PROJECT_KEY $ENV{POET_ENCLAVE_PEM})
FILE(GLOB PROJECT_CONFIG *.xml)
SOURCE_GROUP("Source" FILES ${PROJECT_HEADERS} ${PROJECT_SOURCES} ${PROJECT_EDL})

SET (LIBPOET_ENCLAVE_EDL ${PROJECT_EDL} PARENT_SCOPE) 
SET (LIBPOET_ENCLAVE_INCLUDE ${CMAKE_CURRENT_SOURCE_DIR} PARENT_SCOPE) 

INCLUDE_DIRECTORIES(../libpoet_shared ../libpoet_shared/enclave)

# If are compiling for Linux, then we have special linking for the trusted
# runtime service
IF (NOT MSVC)
    IF(${SGX_USE_SIMULATOR})
        SET(TRTS_LIBRARY_NAME "sgx_trts_sim")
        SET(SERVICE_LIBRARY_NAME "sgx_tservice_sim")
    ELSE()
        SET(TRTS_LIBRARY_NAME "sgx_trts")
        SET(SERVICE_LIBRARY_NAME "sgx_tservice")
    ENDIF()
ENDIF()

SGX_EDGE_TRUSTED(${PROJECT_EDL} PROJECT_EDGE_SOURCES)
SOURCE_GROUP("Generated" FILES ${PROJECT_EDGE_SOURCES})

IF(MSVC)
    SET(CMAKE_LINKER_FLAGS  "${CMAKE_LINKER_FLAGS} /NODEFAULTLIB")
    STRING( REPLACE "/RTC1" "" CMAKE_CXX_FLAGS_DEBUG ${CMAKE_CXX_FLAGS_DEBUG} )
ELSE()
    # These compiler and linker flags for g++/gcc were derived from the make
    # files provided with the SGX sample enclave
    # To generate a proper enclave, it is recommended to follow below guideline
    # to link the trusted libraries:
    #    1. Link sgx_trts with the `--whole-archive' and `--no-whole-archive'
    #       options, so that the whole content of trts is included in the
    #       enclave.
    #    2. For other libraries, you just need to pull the required symbols.
    #       Use `--start-group' and `--end-group' to link these libraries.
    # Do NOT move the libraries linked with `--start-group' and `--end-group'
    # within `--whole-archive' and `--no-whole-archive' options.  Otherwise,
    # you may get some undesirable errors.

    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -m64")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -nostdinc")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fvisibility=hidden")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fpie")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fstack-protector")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -nostdinc++")

    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -m64")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -O2")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--no-undefined")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -nostdlib")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -nodefaultlibs")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -nostartfiles")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-Bstatic")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-Bsymbolic")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--no-undefined")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-pie,-eenclave_entry")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--export-dynamic")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--defsym,__ImageBase=0")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/poet_enclave.lds")
    SET(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,-L,$ENV{SGXSDKInstallPath}lib64")
ENDIF()

ADD_DEFINITIONS(-D POET_ENCLAVE)

# Remove all the default windows libraries (kernel32, etc)
SET(CMAKE_C_STANDARD_LIBRARIES_INIT "")
SET(CMAKE_C_STANDARD_LIBRARIES "")
SET(CMAKE_CXX_STANDARD_LIBRARIES "")
 
# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# Compile targets
# XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# CMake likes to prepend "lib" to project name when creating library...since we
# already have lib in the project name, liblibpoet-enclave is stupid.  Stop
# CMake from doing it.
IF(NOT MSVC)
    SET(CMAKE_SHARED_LIBRARY_PREFIX "")
ENDIF()

ADD_LIBRARY(${PROJECT_NAME} SHARED  ${PROJECT_HEADERS} ${PROJECT_SOURCES} ${PROJECT_EDGE_SOURCES} ${PROJECT_EDL})
SGX_SIGN_ENCLAVE(${PROJECT_NAME} ${PROJECT_KEY} ${PROJECT_CONFIG})
IF(MSVC)
    SET_TARGET_PROPERTIES(${PROJECT_NAME} PROPERTIES LINK_FLAGS "/NODEFAULTLIB /NOENTRY")
    TARGET_LINK_LIBRARIES(${PROJECT_NAME} ${SGX_LIBS_TRUSTED})
ELSE()
    TARGET_LINK_LIBRARIES(${PROJECT_NAME} -Wl,--whole-archive -l${TRTS_LIBRARY_NAME} -Wl,--no-whole-archive)
    TARGET_LINK_LIBRARIES(${PROJECT_NAME} -Wl,--start-group -lsgx_tstdc -lsgx_tstdcxx -lsgx_tcrypto -lsgx_tkey_exchange -l${SERVICE_LIBRARY_NAME} -Wl,--end-group)
ENDIF()
TARGET_INCLUDE_DIRECTORIES( ${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR} ${SGX_ENCLAVE_INCLUDE})

ADD_CUSTOM_COMMAND(
    TARGET ${PROJECT_NAME}
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "${DEPS_DIR}/bin"
    COMMAND ${CMAKE_COMMAND} -E copy "${SIGNED_ENCLAVE}" "${DEPS_DIR}/bin"
)
