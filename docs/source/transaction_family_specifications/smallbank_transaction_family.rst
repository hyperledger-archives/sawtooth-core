****************************
Smallbank Transaction Family
****************************

Overview
========
The Smallbank transaction family is based on the H-Store Smallbank
benchmark originally published as part of the H-Store database benchmarking
project.

    http://hstore.cs.brown.edu/documentation/deployment/benchmarks/smallbank/

This transaction family is intended for use in benchmarking and performance
testing activities in the hopes of providing a somewhat cross-platform
workload for comparing the performance of blockchain systems.

The Smallbank Transaction Family consists of a single Account datatype, one
transaction which creates accounts and five transactions which modify account
values based on a set of rules. The H-Store benchmark included a sixth
transaction for reading balances which does not make sense in the context
of blockchain transactions.

Smallbank Transaction payloads consist of a serialized protobuf wrapper
containing the type and data payload of the sub transaction types.

State
=====

This section describes in detail how Smallbank transaction information
is stored and addressed.

Smallbank Account values are stored in state as serialized protobufs
containing generated customer IDs, customer names, and savings and
checking balances. The 'primary key' of the data is the unique customer_id.

.. code-block:: protobuf

    message Account {
        // Customer ID
        uint32 customer_id = 1;

        // Customer Name
        string customer_name = 2;

        // Savings Balance (in cents to avoid float)
        uint32 savings_balance = 3;

        // Checking Balance (in cents to avoid float)
        uint32 checking_balance = 4;
    }


Addressing
----------
Smallbank Account data is stored in state using addresses which are
generated from the Smallbank namespace prefix and the unique customer_id
of the Account entry. Addresses will adhere to the following format:

- Addresses must be a 70 character hexadecimal string
- The first 6 characters of the address are the first 6 characters
  of a sha512 hash of the Smallbank namespace prefix: "smallbank"
- The following 64 characters of the address are the last 64 characters
  of a sha512 hash of the value of customer_id

For example, a Smallbank address could be generated as follows:

.. code-block:: pycon

    >>> customer_id = 42
    >>> hashlib.sha512('smallbank'.encode('utf-8')).hexdigest()[0:6] + hashlib.sha512(str(customer_id).encode('utf-8')).hexdigest()[-64:]
    '3325143ff98ae73225156b2c6c9ceddbfc16f5453e8fa49fc10e5d96a3885546a46ef4'

Transaction Payload
===================

Smallbank transaction request payloads are defined by the following
protobuf structure:

.. code-block:: protobuf

    message SmallbankTransactionPayload {
        enum PayloadType {
            CREATE_ACCOUNT = 1;
            DEPOSIT_CHECKING = 2;
            WRITE_CHECK = 3;
            TRANSACT_SAVINGS = 4;
            SEND_PAYMENT = 5;
            AMALGAMATE = 6;
        }
        PayloadType payload_type = 1;
        CreateAccountTransactionData create_account = 2;
        DepositCheckingTransactionData deposit_checking = 3;
        WriteCheckTranasctionData write_check = 4;
        TransactSavingsTransactionData transact_savings = 5;
        SendPaymentTransactionData send_payment = 6;
        AmalgamateTransactionData amalgamate = 7;
    }

Based on the selected type, the data field will contain the appropriate
transaction data (these messages would be defined within
SmallbankTransactionPayload):

.. code-block:: protobuf

    message CreateAccountTransactionData {
        // The CreateAccountTransaction creates an account

        // Customer ID
        uint32 customer_id = 1;

        // Customer Name
        string customer_name = 2;

        // Initial Savings Balance (in cents to avoid float)
        uint32 initial_savings_balance = 3;

        // Initial Checking Balance (in cents to avoid float)
        uint32 initial_checking_balance = 4;
    }

    message DepositCheckingTransactionData {
        // The DepositCheckingTransction adds an amount to the customer's
        // checking account.

        // Customer ID
        uint32 customer_id = 1;

        // Amount
        uint32 amount = 2;
    }

    message WriteCheckTransactionData {
        // The WriteCheckTransaction removes an amount from the customer's
        // checking account.

        // Customer ID
        uint32 customer_id = 1;

        // Amount
        uint32 amount = 2;
    }

    message TransactSavingsTransactionData {
        // The TransactSavingsTransaction adds an amount to the customer's
        // savings account. Amount may be a negative number.
    
        // Customer ID
        uint32 customer_id = 1;

        // Amount
        int32 amount = 2;
    }

    message SendPaymentTransactionData {
        // The SendPaymentTransaction transfers an amount from one customer's
        // checking account to another customer's checking account.

        // Source Customer ID
        uint32 source_customer_id = 1;

        // Destination Customer ID
        uint32 dest_customer_id = 2;

        // Amount
        uint32 amount = 3;
    }

    message AmalgamateTransactionData {
        // The AmalgamateTransaction transfers the entire contents of one
        // customer's savings account into another customer's checking
        // account.

        // Source Customer ID
        uint32 source_customer_id = 1;

        // Destination Customer ID
        uint32 dest_customer_id = 2;
    }


Transaction Header
==================

Inputs and Outputs
------------------

The inputs for Smallbank family transactions must include:

* Address of the customer_id being accessed for CreateAccount,
  DepositChecking, WriteCheck, and TransactSavings transactions, and
  both the source and destination customer_ids being accessed for
  SendPayment and Amalgamate transactions.

The outputs for Smallbank family transactions must include:

* Address of the customer_id being modified for CreateAccount,
  DepositChecking, WriteCheck, and TransactSavings transactions, and
  both the source and destination customer_ids being modified for
  SendPayment and Amalgamate transactions.

Dependencies
------------

* List of transaction *header_signatures* that are required dependencies
  and must be processed prior to processing this transaction

.. note:: While any CreateAccount transaction signatures should probably
  be listed in any other modification transactions that reference those
  accounts, it may be sufficient to submit a set of CreateAccount transactions,
  ensure they are committed to the chain and then proceed without explicit
  dependencies.


Family
------
- family_name: "smallbank"
- family_version: "1.0"

Execution
=========

A CreateAccount transaction is only valid if: 

- customer_id is specified
- there is not already an existing account at the address associated with
  that customer_id
- customer_name is specified (not an empty string)
- initial_savings_balance is specified
- initial_checking_balance is specified

The result of a successful CreateAccount transaction is that the new Account
object is set in state.

A DepositChecking transaction is only valid if:

- customer_id is specified
- there is an account at the address associated with that customer_id
- amount is specified
- amount + Account.checking_balance doesn't result in an overflow of uint32

The result of a successful DepositChecking transaction is that the specified
Account.checking_balance = Account.checking_balance + amount.

A WriteCheck transaction is only valid if:

- customer_id is specified
- there is an account at the address associated with that customer_id
- amount is specified
- Account.checking_balance - amount doesn't result in a value < 0

The result of a successful WriteCheck transaction is that the specified
Account's checking balance is decremented by amount.

A TransactSavings transaction is only valid if:

- customer_id is specified
- there is an account at the address associated with that customer_id
- amount is specified
- Account.savings_balance + amount doesn't result in a value < 0 or a value
  which overflows uint32

The result of a successful TransactSavings transaction is that the
specified Account's savings balance is modified by the addition of amount
(which may be negative).

A SendPayment transaction is only valid if:

- both source_customer_id and dest_customer_id are specified
- there is an account at both locations
- source.checking_balance - amount doesn't result in a value < 0
- dest.checking_balance + amount doesn't result in a value which overflows
  uint32

The result of a successful SendPayment transaction is that the source's
checking balance is decremented by amount and the destination's checking
balance is incremented by amount.

An Amalgamate transaction is only valid if:

- both source_customer_id and dest_customer_id are specified
- there is an account at both locations
- source.savings_balance is > 0
- dest.checking_balance + source.savings_balance does not overflow uint32

The result of a successful Amalgamate transaction is that the destination's
checking balance is incremented by the value of the source's savings balance
and that the source's savings balance is set to zero.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
