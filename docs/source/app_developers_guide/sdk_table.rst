**************
Available SDKs
**************

The following table summarizes the Sawtooth SDKs. It shows the feature completeness,
API stability, and maturity level for the client signing, transaction
processors, and state delta features.

+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
|            | **Client Signing**                 | **Transaction Processor**          | **State Delta**                    |
+            +-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
|            | Complete? | Stable API? | Maturity | Complete? | Stable API? | Maturity | Complete? | Stable API? | Maturity |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Python     | |yes|     | |yes|       |   1      | |yes|     | |yes|       |   1      | |yes|     | |yes|       | 1        |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Go         | |yes|     | |yes|       |   1      | |yes|     | |yes|       |   1      | |yes|     | |yes|       | 1        |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| JavaScript | |yes|     | |yes|       |   1      | |yes|     | |yes|       |   2      | |yes|     | |yes|       | 2        |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Rust       | |yes|     |             |   1      | |yes|     |             |   1      | |yes|     |             | 1        |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Java       |           |             |   3      |           |             |   3      |           |             | 3        |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| C++        |           |             |   3      |           |             |   3      |           |             | 3        |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+

A stable API means that the Sawtooth development team is committed to backward
compatibility for future changes. Other APIs could change, which would
require updates to application code.

The Maturity column shows the general maturity level of each feature:

  1.  Recommended: Well supported and heavily used
  2.  Community support only (core maintainers do not update these SDKs)
  3.  Experimental: Might have known issues and future API changes

The available SDKs are in the following repositories:

* Python:
  `https://github.com/hyperledger/sawtooth-core/tree/master/sdk/python
  <https://github.com/hyperledger/sawtooth-core/tree/master/sdk/python>`_

* Rust:
  `https://github.com/hyperledger/sawtooth-core/tree/master/sdk/rust
  <https://github.com/hyperledger/sawtooth-core/tree/master/sdk/rust>`_

* Go:
  `https://github.com/hyperledger/sawtooth-sdk-go
  <https://github.com/hyperledger/sawtooth-sdk-go>`_

* JavaScript:
  `https://github.com/hyperledger/sawtooth-sdk-javascript
  <https://github.com/hyperledger/sawtooth-sdk-javascript>`_

* Java:
  `https://github.com/hyperledger/sawtooth-sdk-java
  <https://github.com/hyperledger/sawtooth-sdk-java>`_

* C++:
  `https://github.com/hyperledger/sawtooth-sdk-cxx
  <https://github.com/hyperledger/sawtooth-sdk-cxx>`_

.. |yes| unicode:: U+2713 .. checkmark

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
