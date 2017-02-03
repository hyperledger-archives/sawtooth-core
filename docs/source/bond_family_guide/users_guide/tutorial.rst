..
   Copyright 2017 Intel Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

********
Tutorial
********

Overview
========

This tutorial is a guide to the use of the Sawtooth Lake Bond Family user
interface (UI).


Considerations
==============

The Sawtooth Bond Family UI runs in a cloud-based instance that is installed,
configured and maintained by Intel. You do not need to install any specialized
sofware on your  computer.

Supported Browsers
==================

The following web browsers are supported:

#. Firefox version 47.0+
#. Chrome version 52.0+
#. Safari version 9.1+
#. Internet Explorer version 11+

Supported Tasks
===============

You can perform the following tasks in the Sawtooth Bond Family UI:

Account Creation and Updates
----------------------------

- `Create an Account`_
- `Sign in with Existing Account`_
- `Update User Account`_


Buying and Selling 
------------------

- `View Bonds`_
- `View Quotes`_
- `Issue a Quote`_
- `Create an Order`_
- `Settle a Matched Order`_


Holdings and Transactions
-------------------------

- `View Portfolio`_


Administrative 
--------------

- `Create Organization`_
- `Create Bond`_


Tasks Not Supported by the UI
=============================

Certain tasks are not supported by the UI,  
but can be performed using the command-line interface (CLI).
For example, bond redemption can be accomplished with the CLI.

See the :doc:`CLI reference guide <cli>` for information on performing tasks
not supported by the UI, but which are supported by the CLI.

Create an Account
===================

The first time you sign in to the Sawtooth Lake Bond UI, you need to
create your account. During this process, you generate a new wallet import
format (WIF) key, or import an existing WIF key. Your key is used to identify
participants and sign transactions.

.. note:: If you sign out, or need to sign in from
          another browser, simply follow the procedure below entitled
          `Sign in with Existing Account`_. 


Creating an Account with a New Key
----------------------------------

To create an account with a new WIF key:

#. Navigate to the URL of the Bond UI instance.

#. Click **Generate WIF**.

#. Save your WIF key using one of the following methods:

   - Click **Download Key** to download the WIF key to your local filesystem.
      + Sarafi does not support downloading the WIF key.
   - Alternatively, copy the WIF key to your clipboard by clicking **Copy Key
     to Clipboard**.

#. Store your WIF key in safe location. It is needed in order to:

   - Sign in to the UI from another browser or computer
   - Sign in after deleting the site cookie

#. Click **Create Participant**.

   - The **Create Participant** page loads:

   .. image:: images/create_participant.*
      :alt: Create participant

#. Create a username.

#. Select a firm from the **Firm** dropdown. 

#. Click the **Create Participant** button.

   - To leave the **Create Participant** page without creating an account, click **Cancel.**
   - During account creation, the browser displays:

   .. image:: images/account_creation_loading.*
      :alt: Create participant transaction submitted

#. The main Bond UI page loads.


Creating an Account with an Existing Key
----------------------------------------

To create an account with an existing WIF key:

#. Navigate to the URL of the Bond UI instance.


#. Click **Import WIF**.

   - The **Import WIF Key** page loads:

   .. image:: images/import_wif_key.*
      :alt: Import WIF key


#. Input your WIF key using one of two methods:

   - Paste the WIF key into the text box.

   - Click **Upload WIF File**, navigate to the WIF key file, then select the file.

         .. note:: The **Upload WIF File** button does not work in Firefox. Use
                   the paste option if you use Firefox.

#. Click **Submit**.

   - The **Create Participant** page loads:

   .. image:: images/create_participant.*
      :alt: Create participant

#. Create a username. 

#. Select a firm from the **Firm** dropdown. 

#. Click the **Create Participant** button.

   - To leave the **Create Participant** page without creating an account, click **Cancel.**
   - During account creation, screen will display:

   .. image:: images/account_creation_loading.*
      :alt: Create participant transaction submitted

#. The main Bond UI page loads.

.. _`signed in`:

Sign in with Existing Account 
============================= 

You can sign in to the Bond UI as an existing user.

To sign in as an existing user:

#. Navigate to the URL of the Bond UI instance.
#. Click **Import WIF**.

   - The **Import WIF Key** page loads:

   .. image:: images/import_wif_key.*
      :alt: Import WIF key

#. Input the WIF key associated with the existing user using one of two 
   methods:

   - Paste the WIF key into the text box
   - Click **Upload WIF File**, navigate to the WIF key file, then select the 
     file.

      .. note:: The **Upload WIF File** button does not work in Firefox. Use
                the paste option if you use Firefox.

#. Click **Submit**.

   - You are now signed in as the existing user or participant. 

.. note:: The tasks below assume that you are already `signed in`_ as a
      participant.


View Bonds
==========

The UI allows you to view bonds,  and to search for bonds based on various
search criteria.

View All Bonds
--------------

You can view all bonds stored in the distributed ledger by following these 
steps:

#. Select **Bonds** from the top menu bar. 

   .. image:: images/menu_bar_bonds.*
      :alt: Menu bar

#. The list of bonds is displayed:

   .. image:: images/list_of_bonds.*
      :alt: List of bonds


Search For Specific Bonds 
-------------------------

You can search for bonds based on the following criteria:

   - ISIN
   - CUSIP
   - Ticker Symbol

To search for bonds based based on your search criteria:

#. Enter the ISIN, CUSIP, or ticker symbol in the **Search** field.
#. Click **Go**.

   - The list of matching bonds is displayed:

   .. image:: images/list_of_bonds_search.*
      :alt: List of bonds from search


To start a new search:

   #. Click **Clear**.
   #. Enter the new search term.
   #. Click **Go**.

.. note:: From the **Bonds** page, you can `view quotes`_.


Create Bond
===========

If you have the market maker role, you can create bonds:

#. Select **Create Bond** from the top menu bar. 

   .. image:: images/menu_bar_create_bond.*
      :alt: Menu bar

#. Fill in the required fields on the **Create Bonds** page, then press the **Create Bond** button, or press **Reset** to clear fields:
   
   .. image:: images/create_bond.*
      :alt: Create bond



Issue a Quote
=============

You can can issue quotes, which are submitted to the distributed ledger. They
can then be matched with orders submitted by other particpants.


To issue a quote:

1. Select **Issue Quote** from the top menu bar. 

   .. image:: images/menu_bar_issue_quote.*
      :alt: menu bar 

2. Select a bond from the **CUSIP/ISIN** drop-down.

   .. image:: images/isin_drop_down.*
      :alt: Select ISIN

3. Fill in the following text boxes under **Quote Details**:

   - Bid Price
   - Ask Price
   - Bid Quantity
   - Ask Quantity

   .. image:: images/quote_details.*
      :alt: Quote details

4. Click **Issue** to submit the quote.

    - To cancel the quote and reset the page, click **Reset**.

5. The **View Quotes** page displays the newly issued quote:

.. image:: images/view_quote.*
   :alt: View quotes after submitting a quote

.. _`view quotes`:

.. _`view the quotes`:

View Quotes
===========

You can view quotes from the **Bonds** page.

To view the quotes associated with a bond:

#. Select **Bonds** from the top menu bar.

   .. image:: images/menu_bar_bonds.*
      :alt: Menu bar

   - A list of available bonds is displayed. 

#. Click the **View Quotes** link:

   .. image:: images/view_quotes_link.*
      :alt: View quotes link

#. The **View Quotes** page for the chosen bond is displayed:

   .. image:: images/view_quotes_multiple.*
      :alt: View quotes page


Create an Order
===============

Participants can create buy and sell orders, which are then be matched against
quotes that meet the order's criteria.

To create an order:

1. Follow the steps above to `view the quotes`_ available for the bond you want
   to buy or sell.

2. Click the **buy** or **sell** button from the **View Quotes** page:

   .. image:: images/view_quotes_buy_sell.*
      :alt: View quotes for buy and sell

   - The **Buy/Sell Order** page loads:

   .. image:: images/buy_sell_bonds.*
      :alt: Buy/Sell order page

3. Fill in the following fields:

   - Quantity
   - Best Price (optional)
   - Best Yield (optional)

4. Click **Create Order**

   - The **View Orders** page is displayed, and includes your submitted order:

   .. image:: images/view_orders.*
      :alt: View orders


Settle a Matched Order
======================

When an order and a quote are matched by the bond transaction family, the order
can be settled by an authorized participant.

To settle a matched order:

#. Select **Orders** from the top menu bar.

   .. image:: images/menu_bar_orders.*
      :alt: Menu bar

   - The **View Orders** page is displayed:

   .. image:: images/view_orders_settle.*
      :alt: View orders for settlement

   - If an order is matched with a quote, a **settle** button appears in the
     last column of the order's row.

#. Click the **settle** button for each matched order that you want to settle. 

   - The settlement request is submitted. 
   - Once the request is accepted, the **View Orders** page is refreshed, and
     the list of orders available for settlement is updated:

   .. image:: images/view_orders_settle_update.*
      :alt: View orders after settlement


Create Organization
===================

To create a new organization:

#. Select **Create Organization** from the top menu bar.

   .. image:: images/menu_bar_create_org.*
      :alt: Menu bar

   - The **Create Organization** page is displayed.

   .. image:: images/create_organization.*
      :alt: Create organization

#. Fill in the following fields:

   - Name
   - Industry (Optional)

#. Enter one of the two following fields:

   - Ticker

      + Entering a ticker creates an issuing org.
      + Bonds are issued against orgs with tickers.

   - Pricing Source

      + Entering a pricing source creates a trading firm.
      + Trading firms can issue quotes, perform trades, etc.

.. note:: If you create a trading firm, your participant will be be removed 
          from any previous trading firm, and placed in the new one.


Update User Account
===================

You can update your user account.
To update your account:

#. Click your username from the top menu bar.

   .. image:: images/menu_bar_account.*

   - The **Update Participant** page is displayed:

   .. image:: images/update_participant.*
      :alt: Update participant


#. Update desired fields in the available text boxes, then press **Update**.


View Portfolio
==============

You can view your holdings and transactions from the **Portfolio** page.

#. Select **Portfolio** from the top menu bar:

   .. image:: images/menu_bar_portfolio.*
      :alt: Menu bar

   - the **Portfolio** page loads:

   .. image:: images/portfolio.*
      :alt: View portfolio 

#. Select one of the following categories to view:

   - Holdings
   - Receipts
   - Settlements

#. The selected category is displayed.


