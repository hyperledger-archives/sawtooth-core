# Marketplace Navigator Client

Front-end client for Marketplace Navigator, using ClojureScript and Sass.

## Development

Getting up and running with development.

### Prerequisites

* [Java 8](http://www.oracle.com/technetwork/java/javase/downloads/jdk8-downloads-2133151.html)
* [Leiningen](http://leiningen.org/)
* [Sass](http://sass-lang.com/)
* [Node JS 6 or above](https://nodejs.org/en/download/current/)
* [Yarn](https://yarnpkg.com/)

### Reading Materials

* [ClojureScript](https://github.com/clojure/clojurescript/)
* [Om](https://github.com/omcljs/om) (a ClojureScript library for React.js).
* [Figwheel](https://github.com/bhauman/lein-figwheel/)

### Running Figwheel

With a running backend server instance (instructions found in `../server`),
start the following script:

```
> scripts/figwheel.sh
```

This will start the process of building the site live development.  Both the
ClojureScript source and the sass source files will be autocompiled and
refreshed on the screen.

The client will be available [localhost:3449](http://localhost:3449).

### Running tests

Tests can be run in two ways.  The first is via the command-line:

```
> lein cljs:test
```

If you'd like to run the tests from a clean build, run `lein cljs:clean-test`.

The tests can also be run in the browser while running Figwheel.  After running
starting Figwheel as in the section above, you can open your browser to
[http://localhost:3449/test.html](http://localhost:3449/test.html) and the test will
automatically run between code changes.  The favicon will change between green and red
for success and failure, respectively.

When adding test namespaces, they will need to be added explicitly to `exchange.test_suite`
in order to be run.

## Production

Building the production materials uses the following script:

```
> scripts/build.sh
```
