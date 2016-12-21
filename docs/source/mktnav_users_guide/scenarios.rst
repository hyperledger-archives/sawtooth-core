*********
Scenarios
*********

- `Basic Cookie Market`_

   + `Building the Market`_
   + `Making a Baker`_
   + `Making a Buyer`_

- `International Cookie Arbitrage`_

   + `Expanding the Market`_
   + `Baking Biscotti`_
   + `Buying Biscotti`_


Basic Cookie Market
===================

This scenario mirrors the one in the :doc:`CLI tutorial <../tutorial>`, and is a good way to both explore the basics of Marketplace Navigator and to compare how to do similar tasks between the CLI and GUI. It walks through the creation of a controlled market, participants, and goods, as well as the exchange of those goods.

Building the Market
-------------------

In most markets, you will want the creation of *Assets* to be centrally controlled so that everyone can't just make infinite goods, similar to how the Federal Reserve controls how and when money is printed. Let's build that Market authority now.

#. The Market works like any other *Participant*, so we will start by generating a new WIF key.

   .. image:: images/market_wif.*

#. Download the key, and then click **Create Participant**. You may want to rename the file something meaningful, like *"market.wif"*.

   .. image:: images/market_save.*

#. Name the market "Market", write a short description, and then click **Submit**.

   .. image:: images/market_create.*

#. The first thing a market needs is a currency, so click on the **+** button next to the **Assets** list.

   .. image:: images/asset_button.*

#. We're going to make both a new *AssetType* (currency), and a new *Asset* (usd). We will make both *"restricted"*, since we do not want other participants making counterfeit currency. USD will also be *"divisible"*, since it is possible to trade fractions of a dollar.

   .. image:: images/usd_create.*

#. Now that dollars exist as a concept, we need to create some for the market. Wait for the transation to be committed to the blockchain, and once USD appears on the sidebar, click the **+** next to the **Holdings** list.

   .. note:: Waiting for the blockchain to commit will be a common experience throughout this scenario and won't be explicitly mentioned again. If you feel the need to check the status of recent transactions, you can do so by clicking on the **Block** name in the menu bar.

#. We're going to create a strategic reserve of $1,000,000, which we will later distribute to the other participants in our market.

   .. image:: images/reserve_create.*

#. We're going to use the pre-made reusable *"token"* asset to create our distribution offer, but first we'll need a *Holding* for that too.

   .. image:: images/verification_create.*

#. Finally, we'll create our offer to provision each participant with $1,000. Click the **+ Create Offer** button in the menu bar.
#. Set the offer to take in tokens and payout usd at a 1:1000 ratio. We only want this exchange to be possible once per person, so set both the minimum and maximum input to 1, and limit it to **Execute Once per Participant**.

   .. image:: images/provision_create.*

#. Our market is all set and ready to go! Select **Sign Out** from the **Hi, Market** dropdown, and let's make a new participant.

Making a Baker
----------------

Now we're going to create Abby, an entrepeneur who will bake some cookies to sell on the market.

#. Follow the same steps as above to generate and save a new WIF key. Then fill out Abby's info and click **Submit**.

   .. image:: images/abby_create.*

#. You can see that USD already exists in the list of *Assets*. Let's add cookies. Click the **+** next to **Assets**.
#. We'll make the cookie *AssetType* and chocolate chip cookie *Asset* similar to how we made USD, but this time they will not be *"restricted"*, since almost anyone can come up with new recipes for cookies, or physically bake new chocolate chip cookies.

   .. image:: images/cookie_create.*

#. Now that chocolate chip cookies are a thing, let's bake a batch. Click the **+** next to **Holdings**, and make a holding with 24 cookies.

   .. image:: images/batch_create.*

#. The last thing we need to do before we can create a sell offer is to make a holding of US dollars to send our payments to. We could create an empty one, but why not take advantage of that market provision? Start by creating an authorization token by clicking the **+** next to **Holdings**.
#. Tokens are unrestricted, so we can create a holding prepopulated with one, and since they are not consumable, one is all we need.

   .. image:: images/token_create.*

#. Select **Dashboard** from the **Hi, Abby** dropdown menu.
#. Click on **Latest Open Offers**
#. Click the **Accept** button to the right of the provisioning offer.
#. We can create a new savings account in the process of accepting the Market's provisioning offer. We just have to select **New Holding** from the **Output Holding** dropdown, and we're good to go.

   .. image:: images/provision_accept.*

#. Finally we can create our offer to sell cookies. This will look similar to the provisioning offer the Market created earlier, but we won't limit how many times it can be executed. Let's sell the cookies for $2 each.

   .. image:: images/cookie_offer.*

#. We're done with our baker Abby, so go ahead and **Sign out**.

Making a Buyer
--------------

Finally we will create Ben, a discerning cookiehead looking for the absolute best chocolate chip. He will take the Market's USD provision, and use it to purchase Abby's cookies. You should be familiar with all the steps by now.

#. Generate and save a WIF key, and then create Ben's account.

   .. image:: images/ben_create.*

#. Create a token holding.

   .. image:: images/token_create.*

#. Use that token to accept the Market's USD provisioning offer and create a USD holding (get there by clicking on **Dashboard** > **Latest Open Offers** > **Accept**).

   .. image:: images/provision_accept.*

#. We're ready buy some cookies! Return to the **Dashboard** and click on **Latest Open Offers** one more time. This time though the offer we will be accepting is Abby's.

   .. image:: images/abby_offer.*

#. Let's get a dozen cookies! We've earned it.

   .. image:: images/get_cookies.*

International Cookie Arbitrage
==============================

Let's build off our previous scenario to showcase one of the more powerful features of of the Navigator UI: *arbitrage*. Say we have a new baker cooking some authentic Italian biscotti, but they only accept Euros. So long as a *USD -> Euro* exchange exists, there is no need to force American buyers to tediously create new holdings and manually execute a long series of exchanges.

Expanding the Market
--------------------

#. First we need to log our Market back in. If you are still signed in as Ben, sign out and this time click **Import WIF**, instead of generating a new one.

   .. image:: images/market_wif.*

#. The easiest way to enter Market's WIF key is to upload the *market.wif* file we generated earlier (you still have that right?). Click **Upload WIF File**, select the file, and then click **Submit**.

   .. image:: images/upload_wif.*

#. Now that you are logged back in as Market, let's create a new currency asset: Euros. Click the **+** to the right of **Assets**, and fill out the form.

   .. image:: images/euro_create.*

#. We'll need a holding with a strategic reserve of €1,000,000 as well. Add the holding with the **+** to the right of **Holdings**.

   .. image:: images/euro_reserve.*

#. Finally we'll create an offer to exchange USD for Euros. Click **+ Create Offer** in the menu bar above. As of this writing, the exchange rate was €0.96 to $1. A quirk of this UI is you can only enter whole integer amounts even if the asset is divisible, but we can get around that by making our offer $100 for €96.

   .. image:: images/exchange_create.*

#. Now that we've expanded our Market to handle foreign currency, all that's left to do is **Sign out**.

Baking Biscotti
---------------

We're going to create a new participant, Claudio, who will bake some biscotti and put them on sale in our newly international market.

#. Go through the steps to generate a new WIF key and create a new participant detailed above.

   .. image:: images/claudio_create.*

#. Once Claudio is provisioned, create a new biscotti asset just like we did Euros.

   .. image:: images/biscotti_create.*

#. And just like Abby in the previous scenario, we will bake our first batch by creating a holding.

   .. image:: images/biscotti_batch.*

#. We'll also create an empty savings account for Claudio to keep the Euros that are sure to be pouring in soon.

   .. image:: images/claudio_savings.*

#. Finally, we'll put the biscotti up for sale by creating an offer that will take €3 for 2 biscotti.

   .. image:: images/biscotti_offer.*

#. Claudio is all set, so let's go ahead and **Sign out**.

Buying Biscotti
---------------

Almost finished. We'll log back in as Ben who, always craving new cookie experiences, will purchase some biscotti from Claudio.

#. Log Ben in by importing his WIF key just like we did with Market above.
#. Click on **Latest Open Offers**.
#. Click the **Accept** button to the right of Claudio's biscotti offer.
#. Now we could have a problem. Claudio is asking for Euros, and we can see if we click on **Initial Holding** that we don't have any of those. But fear not, *arbitrage* to the rescue! Click on the **+ Offer** button to right of the initial holding dropdown. From the pop-up that appears, you can select the Market's USD for Euro exchange offer.

   .. image:: images/add_offer.*

#. Now we are free to select our USD savings account as the initial holding, and route those dollars through the Market's exchange to our intended biscotti target, which we will keep in a new */jar* holding.

   .. image:: images/execute_arbitrage.*

   .. note:: This exchange exposes some of the quirks of the **Quantity** field that may not be immediately obvious. It represents the number of times the *smallest possible integer representation* of the initial exchange is going to be executed. So for example, in this case our *$100 -> €96* exchange has been reduced to *$25 -> €24* (the smallest integer representation). That €24 buys you 16 biscotti, so by entering a 2 into the **Quantity** field, we will spend $50, and receive 32 biscotti. It is generally best when making exchanges to double check the calculated holding amounts before clicking **Accept**.

#. Click **Accept** and enjoy those sweet sweet digital biscotti.
