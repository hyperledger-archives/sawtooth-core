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
# -----------------------------------------------------------------------------

IF(NOT TARGET lint)
  ADD_CUSTOM_TARGET(lint)
ENDIF()

# Add a target that runs cpplint.py
#
# Parameters:
# - TARGET_NAME the name of the target to add
# - SOURCES_LIST a complete list of source and include files to check
FUNCTION(cpplint TARGET_NAME)
  SET(SOURCES_LIST ${ARGN})
  ADD_CUSTOM_TARGET(lint_${TARGET_NAME} lint
    COMMAND "${CMAKE_COMMAND}" -E
            chdir ${CMAKE_CURRENT_SOURCE_DIR}
            "cpplint"
            "--filter=${STYLE_FILTER}"
            "--counting=detailed"
            "--extensions=cpp,hpp,h"
            "--linelength=80"
            ${SOURCES_LIST}
    DEPENDS ${SOURCES_LIST}
    COMMENT "Linting ${TARGET_NAME}"
    VERBATIM)

endfunction()