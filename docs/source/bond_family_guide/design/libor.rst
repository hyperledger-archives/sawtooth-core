Sawtooth LIBOR
==============

Sawtooth London Interbank Offered Rate (LIBOR) is a transaction family and
sample client for the Intercontinental Exchange (ICE) LIBOR, the world's most
widely-used benchmark for short-term interest rates.  LIBOR's primary function
is to serve as the benchmark reference rate for government and corporate bonds,
mortgages, etc.

The ICE LIBOR has interest rates for five currencies:

  - CHF (Swiss Franc)
  - EUR (Euro)
  - GBP (Pound Sterling)
  - JPY (Japanese Yen)
  - USD (US Dollar)

Each currency has interest rates for seven maturities:

  - Overnight
  - One Week
  - One Month
  - Two Month
  - Three Month
  - Six Month
  - One Year

More information about LIBOR can be found at:

  http://www.investopedia.com/terms/l/libor.asp

  https://www.theice.com/iba/libor

The Sawtooth LIBOR transaction family currently only supports interest rates
for the USD.

To use the Sawtooth LIBOR transaction family, it must be added to the list of
transaction families in txnvalidator.js:

.. code-block:: javascript

   "TransactionFamilies" : [
      "libor"
   ],

txnvalidator must be able to find the Sawtooth LIBOR transaction family
implementation, which can be done by adding this repository directory to the
PYTHONPATH environment variable.

The Sawtooth LIBOR client, libor, simulates obtaining current LIBOR data from
ICE by screen scraping the Wall Street Journal web site that publishes the
data:

  http://online.wsj.com/mdc/public/page/2_3020-libor.html

The Sawtooth LIBOR client has two sub-commands:  submit and list.

Submitting New LIBOR Data
-------------------------

To submit new LIBOR data:

.. code-block:: console

   $ ./bin/libor submit --keyfile ./libor/key/libor.wif --wait
   Submitting LIBOR for effective date: 2016-06-09
   OneMonth => 0.44705
   ThreeMonth => 0.65605
   SixMonth => 0.94390
   Overnight => 0.38560
   OneYear => 1.27425
   TwoMonth => 0.54015
   OneWeek => 0.41075

The submit sub-command supports the following command-line parameters:

.. program:: libor submit

.. option:: --wait

   Waits for the transaction to successfully be committed.  The default is to
   not wait for the transaction to be committed.

.. option:: --keyfile KEYFILE

   Specifies the file that contains the key used to sign the LIBOR data.  The
   key must correspond to the address 1UrR1WTfkMaWmY8z6DxwEE2MYFXA6rdzZ.  The
   key file, ./libor/key/libor.wif, contains the appropriate key.  This
   parameter is *required*.

.. option:: --url URL

   The URL of the validator to which the transaction will be submitted.  If
   not specified, the default URL is http://localhost:8800.

.. option:: --date DATE

   The date, in ISO-8601 format (YYYY-MM-DD), for which LIBOR data should be
   fetched.  Note that for a specific date on the WSJ site, the effective date
   is actually the previous day, which will be used as the date in the
   transaction.  If the :option:`--date` parameter is not present, the
   most-recent LIBOR data is fetched.

.. note::

   If a transaction already exists for the date submitted, the
   transaction will fail.

Listing LIBOR Data
------------------

To list LIBOR data:

.. code-block:: console

   $ ./bin/libor list
   +----------+---------+--------+--------+--------+--------+--------+--------+
   |   Date   |Overnight| 1 Week | 1 Month| 2 Month| 3 Month| 6 Month| 1 Year |
   +----------+---------+--------+--------+--------+--------+--------+--------+
   |2016-06-08|   0.3876|  0.4080|  0.4453|  0.5373|  0.6580|  0.9470|  1.2784|
   |2016-06-09|   0.3856|  0.4108|  0.4471|  0.5402|  0.6561|  0.9439|  1.2743|
   +----------+---------+--------+--------+--------+--------+--------+--------+
   $
   $ ./bin/libor list --date 2016-06-08
   |---------------------+
   |LIBOR for 2016-06-08 |
   |------------+--------+
   |Overnight:  |  0.3876|
   |------------+--------+
   |1 Week:     |  0.4080|
   |------------+--------+
   |1 Month:    |  0.4453|
   |------------+--------+
   |2 Month:    |  0.5373|
   |------------+--------+
   |3 Month:    |  0.6580|
   |------------+--------+
   |6 Month:    |  0.9470|
   |------------+--------+
   |1 Year:     |  1.2784|
   |------------+--------+

The list sub-command supports the following command-line parameters:

.. program:: libor list

.. option:: --url URL

   The URL of the validator from which LIBOR transactions will be queried.  If
   not specified, the default URL is http://localhost:8800.

.. option:: --date DATE

   The date, in ISO-8601 format (YYYY-MM-DD), for which LIBOR data should be
   queried.  If the :option:`--date` parameter is not present, all available
   LIBOR data is returned.
