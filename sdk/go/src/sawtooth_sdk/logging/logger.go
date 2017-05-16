/**
 * Copyright 2017 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

package logging

import (
	"fmt"
	"io"
	"log"
	"os"
)

const (
	CRITICAL = 50
	ERROR    = 40
	WARN     = 30
	INFO     = 20
	DEBUG    = 10
)

// Set the calldepth so we get the right file when logging
const (
	CALLDEPTH = 3
	FLAGS     = log.Lshortfile | log.LstdFlags | log.Lmicroseconds
)

type Logger struct {
	logger *log.Logger
	level  int
}

var _LOGGER *Logger = nil

func Get() *Logger {
	if _LOGGER == nil {
		_LOGGER = &Logger{
			logger: log.New(os.Stdout, "", FLAGS),
			level:  DEBUG,
		}
	}
	return _LOGGER
}

func (self *Logger) SetLevel(level int) {
	self.level = level
}

func (self *Logger) SetOutput(w io.Writer) {
	self.logger.SetOutput(w)
}

func (self *Logger) Debugf(format string, v ...interface{}) {
	if self.level <= DEBUG {
		self.logf("DEBUG", format, v...)
	}
}

func (self *Logger) Debug(v ...interface{}) {
	if self.level <= DEBUG {
		self.log("DEBUG", v...)
	}
}

func (self *Logger) Infof(format string, v ...interface{}) {
	if self.level <= INFO {
		self.logf("INFO", format, v...)
	}
}

func (self *Logger) Info(v ...interface{}) {
	if self.level <= INFO {
		self.log("INFO", v...)
	}
}

func (self *Logger) Warnf(format string, v ...interface{}) {
	if self.level <= WARN {
		self.logf("WARN", format, v...)
	}
}

func (self *Logger) Warn(v ...interface{}) {
	if self.level <= WARN {
		self.log("WARN", v...)
	}
}

func (self *Logger) Errorf(format string, v ...interface{}) {
	if self.level <= ERROR {
		self.logf("ERROR", format, v...)
	}
}

func (self *Logger) Error(v ...interface{}) {
	if self.level <= ERROR {
		self.log("ERROR", v...)
	}
}

func (self *Logger) Criticalf(format string, v ...interface{}) {
	if self.level <= CRITICAL {
		self.logf("CRITICAL", format, v...)
	}
}

func (self *Logger) Critical(v ...interface{}) {
	if self.level <= CRITICAL {
		self.log("CRITICAL", v...)
	}
}

func (self *Logger) logf(prefix string, format string, v ...interface{}) {
	self.logger.Output(CALLDEPTH, "["+prefix+"] "+fmt.Sprintf(format, v...))
}

func (self *Logger) log(prefix string, v ...interface{}) {
	self.logger.Output(CALLDEPTH, "["+prefix+"] "+fmt.Sprint(v...))
}
