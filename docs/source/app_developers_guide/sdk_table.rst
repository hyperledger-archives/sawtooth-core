*************************
Summary of Available SDKs
*************************

The Sawtooth SDKs are in the following repositories:

* C++:
  `hyperledger/sawtooth-sdk-cxx
  <https://github.com/hyperledger/sawtooth-sdk-cxx>`__

* Go:
  `hyperledger/sawtooth-sdk-go
  <https://github.com/hyperledger/sawtooth-sdk-go>`__

* Java:
  `hyperledger/sawtooth-sdk-java
  <https://github.com/hyperledger/sawtooth-sdk-java>`__

* JavaScript:
  `hyperledger/sawtooth-sdk-javascript
  <https://github.com/hyperledger/sawtooth-sdk-javascript>`__

* Python:
  `hyperledger/sawtooth-sdk-python
  <https://github.com/hyperledger/sawtooth-sdk-python>`__

* Rust:
  `hyperledger/sawtooth-sdk-rust
  <https://github.com/hyperledger/sawtooth-sdk-rust>`__

* Swift:
  `hyperledger/sawtooth-sdk-swift
  <https://github.com/hyperledger/sawtooth-sdk-swift>`__

The following table summarizes the Sawtooth SDKs. It shows the feature completeness,
API stability, and maturity level for the client signing, transaction
processors, and state delta features.

+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
|            | **Client Signing**                 | **Transaction Processor**          | **State Delta**                    |
+            +-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
|            | Complete? | Stable API? | Maturity | Complete? | Stable API? | Maturity | Complete? | Stable API? | Maturity |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Python     | |yes|     | |yes|       |   1      | |yes|     | |yes|       |   1      | |yes|     | |yes|       |  1       |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Go         | |yes|     | |yes|       |   1      | |yes|     | |yes|       |   1      | |yes|     | |yes|       |  1       |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| JavaScript | |yes|     | |yes|       |   1      | |yes|     | |yes|       |   2      | |yes|     | |yes|       |  2       |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Rust       | |yes|     |             |   1      | |yes|     |             |   1      | |yes|     |             |  1       |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Java       |           |             |   3      |           |             |   3      |           |             |  3       |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| C++        |           |             |   3      |           |             |   3      |           |             |  3       |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+
| Swift      |           |             |   3      | N/A       | N/A         |  N/A     | N/A       | N/A         | N/A      |
+------------+-----------+-------------+----------+-----------+-------------+----------+-----------+-------------+----------+

A stable API means that the Sawtooth development team is committed to backward
compatibility for future changes. Other APIs could change, which would
require updates to application code.

The Maturity column shows the general maturity level of each feature:

  1.  Recommended: Well supported and heavily used
  2.  Community support only (core maintainers do not update these SDKs)
  3.  Experimental: Might have known issues and future API changes


.. |yes| unicode:: U+2713 .. checkmark

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
