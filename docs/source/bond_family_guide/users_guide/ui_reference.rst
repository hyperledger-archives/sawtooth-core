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

************
UI Reference
************

Overview
========

This is the reference guide for the Sawtooth Lake Bond Family graphical user
interface (UI). 


Menu Bar
========

Use the menu bar at the top of the Sawtooth Lake Bond UI to navigate
between the functions supported by the UI.

.. image:: images/ref_menu_bar_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Main page              Welcome page
b      Bonds                  List or search for bonds
c      Create Bond            Create a new bond listing
d      Orders                 View orders and settle matched orders
e      Issue Quote            Issue a quote if your participant is associated with a pricing source
f      Create Organization    Create a new organization
g      Portfolio              View holdings and transactions
h      Update Participant     Click to view and modify account settings
i      Sign Out               After you sign out, you need your WIF key to sign back in
=====  ===================    =============

Bonds
=====

The **Bonds** page allows you to view all the bonds in the system, or to search for
bonds based on specific criteria.

.. image:: images/ref_bonds_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Search field           Enter search criteria here
b      Go                     Click to search for bonds
c      Clear                  Click to clear search field
d      ISIN/CUSIP             The ISIN or CUSIP of the bond
e      Bond description       Detailed information on bond
f      Market Prices          The current bid and ask prices of the bond
g      Market Yields          The yield of the bond based on the current market price
h      Time of Quote          The time of the last quote for the bond
i      View Quotes            Click to view all quotes for the bond
=====  ===================    =============


Create Bond
===========

The **Create Bond** page allows you to create a bond, if your user account has
the necessary role.

.. image:: images/ref_create_bond_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Issuer                 Drop-down menu selects the issuer of the bond
b      Industry               The industry of the bond issuer
c      Ticker                 The ticker symbol of the bond issuer
d      Moody's                The Moody's rating for the bond
e      S&P                    The S&P rating for the bond
f      Fitch                  The Fitch rating for the bond
g      CUSIP                  The CUSIP identifier of the bond
h      ISIN                   The ISIN identifier of the bond
i      1st Settle Date        The first settle date of the bond
j      Maturity Date          Maturity date of the bond
k      Face Value             The face value of the bond
l      Amount Outstanding     The amount outstanding on the bond
m      Type                   Choose fixed or floating 
n      Frequency              The frequency of payments
o      1st Date               The first payment date
p      Rate                   The interest rate paid by the bond
q      Benchmark              The benchmark used to set the rate, if rate is floating
r      Create Bond            Click to create the bond based on the entered values
s      Reset                  Click to clear all fields 
=====  ===================    =============

Orders
======

The **View Orders** page allows you to view all orders in the system, and to settle
orders that have been matched with a quote.

.. image:: images/ref_view_orders_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Filter options         Show all orders, or only your orders
b      Order Time             Displays date and time of order
c      Trader                 Name of the trader or market participant that placed the order
d      ISIN/CUSIP             The ISIN or CUSIP of the bond
e      Bond description       Detailed information on bond
f      Order Status           The status of the order
g      Type                   The order type (e.g. market, limit, etc.)
h      Quantity               The quantity of bonds to buy or sell
i      settle                 Click to settle a matched order
=====  ===================    =============

Issue Quote
===========

The **Issue Quote** page allows you to issue a quote if your user account is
associated with a pricing source.


.. image:: images/ref_issue_quote_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Pricing Source         The pricing source of the bond, tied to the participant creating the quote.
b      ISIN/CUSIP             The ISIN or CUSIP identifier of the bond
c      Issuer                 Ticker symbol of the issuer
d      Maturity date          Date on which the principal amount is due
e      Prior Quote            Info on prior quote for the same bond
f      Bid Price              Bid price for the bond
g      Ask Price              Ask price for the bond 
h      Bid Quantity           The number of bonds that must be purchased
i      Ask Quantity           The number of bonds that must be offered
j      Issue                  Click to issue the quote
k      Reset                  Click to clear fields and start over
=====  ===================    =============



Create Organization
===================

The **Create Organization** page allows you to create a new organization. 

.. image:: images/ref_create_org_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Name                   Name of the organization to create
b      Industry               The industry of the organization (optional)
c      Ticker                 The ticker symbol of the organization (if applicable)               
d      Pricing Source         The pricing source to associate with the organization (if applicable)         
e      Create                 Click to create the new organization
f      Reset                  Click to reset all fields and start over
=====  ===================    =============


Portfolio
=========

The **Portfolio** page allows you to view your holdings and transactions.

.. image:: images/ref_portfolio_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Holdings               Click to see holdings
b      Receipts               Click to see receipts
c      Settlements            Click to see settlements
d      Data display area      Shows your holdings, receipts, or settlements             
=====  ===================    =============


Update Participant
==================

The **Update Participant** page allows you to update your account information.

.. image:: images/ref_account_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Name                   Participant username
b      Firm                   Organization associated with participant
c      Role                   Role of participant (market maker or trader)
d      Update                 Click to update account 
e      Reset                  Click to reset fields            
=====  ===================    =============


View Quotes
===========

The **View Quotes** page allows you to view all the quotes associated with a bond.
To navigate to this page, click **Bonds**, then **View Quotes** for a bond.

.. image:: images/ref_view_quotes_anot.*

=====  ===================    =============
Item   Description            Note
=====  ===================    =============
a      Buy                    Click to buy this bond
b      Sell                   Click to sell this bond
c      PSC                    Pricing Source                    
d      Firm Name              Name of the firm selling the bond
e      Bid / Ask Prices       The bid price followed by the ask price for the bond       
f      Bid / Ask Yields       The bid and ask yields based on the bid and ask prices
g      Bid / Ask Sizes (M)    The number of bonds that must be purchased or sold based on this quote
h      Time of Quote          The time the quote was generated
=====  ===================    =============




