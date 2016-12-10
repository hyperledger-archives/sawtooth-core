/**
 * Copyright 2016 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * No license under any patent, copyright, trade secret or other intellectual
 * property right is granted to or conferred upon you by disclosure or delivery
 * of the Materials, either expressly, by implication, inducement, estoppel or
 * otherwise. Any license under such intellectual property rights must be
 * express and approved by Intel(R) in writing.
 */
var page = require('webpage').create();
var system = require('system');

if (system.args.length < 2) {
  console.log('Expected a target URL parameter.');
  phantom.exit(1);
}

var RETRY_WAIT_MILLIS = 200;
var numRetries = 10;
var url = system.args[system.args.length -1];

function _nextTickExit(exitCode) {
  setTimeout(function() { // https://github.com/ariya/phantomjs/issues/12696
    phantom.exit(exitCode);
  }, 0);
}


page.onConsoleMessage = function (message) {
  console.log("Test console: " + message);
};

page.onError = function(msg, trace) {
    console.log(msg);
    trace.forEach(function (item) {
        console.log('  ', item.file, ':', item.line);
    });
};

console.log("Loading URL: " + url);

function checkResults() {
    numRetries--;

    try {
        var testResult = page.evaluate(function() {
            return  test_suite.all.test_result();
        });

        if(testResult) {
            console.log("Test report received..." + (testResult.succeeded ? "success" : "failed"));
            phantom.exit(!testResult.succeeded ? 31: 0);
        } else if (numRetries === 0) {
            console.log('Timeout while waiting for test report. Exiting...');
            phantom.exit(255); // no results in time, we'll fail the process.
        } else {
            console.log('Test report not available. Trying again in ' + RETRY_WAIT_MILLIS + "ms...");
            setTimeout(checkResults, RETRY_WAIT_MILLIS);
        }

    } catch (e) {
        console.log("An error occurred while querying the test results!");
        console.log(e);
        phantom.exit(63);
    }
}

page.open(url, function (status) {
  if (status != "success") {
    console.log('Failed to open ' + url);
    _nextTickExit(127);
    return;
  }

  try {
      var result = page.evaluate(function() {
        console.log("Running tests in page...");
        return test_suite.all.run();
      });
  } catch(e) {
      console.log("An uncaught error occurred while running the test suite!");
      console.log(e);
      _nextTickExit(128);
      return;
  }

  setTimeout(checkResults, 1000);

});
