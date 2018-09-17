********************************
Configuring Grafana and InfluxDB
********************************

This procedure is for a Linux (Ubuntu) environment. For a Sawtooth network in
Docker containers, additional steps are needed to change the configuration of
the validator containers. These steps are not described in this procedure.

.. note::

   This procedure is for a Linux (Ubuntu) environment. For a Sawtooth network
   in Docker containers, additional steps are needed to change the
   configuration of the validator containers. These steps are not described in
   this procedure.

Requirements
============

This guide assumes Docker Engine is installed and one or more Sawtooth
validator nodes have been configured.

Download `sawtooth-core <https://github.com/hyperledger/sawtooth-core>`_
from the Hyperledger GitHub repository.

.. code-block:: console

   $ git clone https://github.com/hyperledger/sawtooth-core.git

InfluxDB
========

#. First, pull the InfluxDB Docker image from Docker Hub.

   .. code-block:: console

      $ docker pull influxdb

#. Create an InfluxDB data directory to provide persistent storage on the local
   file system.

   .. note::

      Depending on the host operating system /var/lib/influx-data may not be
      appropriate, modify this path accordingly.

   .. code-block:: console

      $ sudo mkdir /var/lib/influx-data

#. Next, start an InfluxDB Docker container. This command uses the persistent
   storage on the local file system and exposes port 8086 to the network. It
   also configures the database name and the ``admin`` and ``lrdata`` users for
   InfluxDB.

   .. code-block:: console

      $ docker run -d -p 8086:8086 -v /var/lib/influx-data:/var/lib/influxdb \
       -e INFLUXDB_DB=metrics -e INFLUXDB_HTTP_AUTH_ENABLED=true \
       -e INFLUXDB_ADMIN_USER=admin -e INFLUXDB_ADMIN_PASSWORD='{admin-pw}' \
       -e INFLUXDB_USER=lrdata -e INFLUXDB_USER_PASSWORD='{lrdata-pw}' \
       --name sawtooth-stats-influxdb influxdb

   .. note::

      Also, remember to properly escape any special characters, such as
      ``,@!$``.

Grafana
=======

#. First, build the Grafana Docker image from the Dockerfile included in the
   sawtooth-core repository.

   .. code-block:: console

      $ cd sawtooth-core/docker
      $ docker build . -f grafana/sawtooth-stats-grafana \
       -t sawtooth-stats-grafana

#. Run the Grafana container.

   .. code-block:: console

      $ docker run -d -p 3000:3000 --name sawtooth-stats-grafana \
       sawtooth-stats-grafana

#. Next, open the Grafana web page at ``http://{host}:3000``.

   .. note::
      Be sure to replace {host} with the IP or Fully Qualified Domain Name
      (FQDN) of the system running the Grafana Docker container.

#. Log in as user ``admin`` with the password ``admin``.

#. Change the admin password. First, click on the Grafana spiral icon at the
   top left of the web page and go to "Admin / Profile". Next, click on
   "Change Password".

#. Configure Grafana to use InfluxDB as a data source.

   a. Click on the Grafana spiral icon at the top left of the web page and go to
      "Data Sources".

   #. Click on "Metrics".

   #. Change the URL to the host server (IP or FQDN) running the InfluxDB
      Docker container.

   #. Under "InfluxDB Details", set INFLUXDB_USER to ``lrdata``. For
      INFLUXDB_USER_PASSWORD, enter the ``lrdata`` password that was defined in
      "Configure InfluxDB", above.

   #. Click "Save & Test".

#. For Sawtooth 1.0.* only, import the 1.0 dashboard. (Sawtooth 1.1.* can use
   the dashboard included in the Grafana Docker container from git master.)

   a. Get the 1.0 dashboard from either
      sawtooth-core/docker/grafana/dashboards/sawtooth_performance.json in the
      1-0 branch or download from GitHub directly at `sawtooth_performance.json
      <https://raw.githubusercontent.com/hyperledger/sawtooth-core/1-0/docker/grafana/dashboards/sawtooth_performance.json>`_.

   #. Click Grafana spiral logo and mouse over "Dashboards", then click
      "Import".

   #. Click "Upload .json file".

   #. Navigate to the location of `` sawtooth_performance.json``.

   #. Select "metrics" in the drop-down menu and click "Import".

Sawtooth Validator Configuration
================================

Sawtooth validator metrics are reported by the sawtooth-validator process, and
are configured in the file /etc/sawtooth/validator.toml.

#. If the validator configuration file doesn't exist yet, copy the template
   from ``/etc/sawtooth/validator.toml.example`` to
   ``/etc/sawtooth/validator.toml``.

#. Fill in the following values with the configurations used above.
   ``opentsdb_url`` is the IP / FQDN:port to the InfluxDB instance,
   ``opentsdb_db`` is the value of INFLUXDB_DB, then fill in the INFLUXDB_USER
   for ``opentsdb_username`` and INFLUXDB_USER_PASSWORD for
   ``opentsdb_password`` created above.

   .. code-block:: ini

      # The host and port for Open TSDB database used for metrics
      opentsdb_url = "http://{host}:3000"

      # The name of the database used for storing metrics
      opentsdb_db = "metrics"

      opentsdb_username  = "lrdata"

      opentsdb_password  = "test"

   .. note::
      Be sure to replace  {host} with the IP or Fully Qualified Domain Name
      (FQDN) of the system running the InfluxDB Docker container.

#. Restart sawtooth-validator for these changes to take effect.

   If started via systemd:

   .. code-block:: console

      $ sudo systemctl restart sawtooth-validator

Sawtooth REST API Configuration
===============================

Sawtooth REST API metrics are reported by the the ``sawtooth-rest-api`` process.

#. If the REST API configuration file doesn't exist yet, copy the template from
   ``/etc/sawtooth/rest_api.toml.example`` to ``/etc/sawtooth/rest_api.toml``.

#. Modify ``opentsdb_url``, ``opentsdb_db``, ``opentsdb_username``, and
   ``opentsdb_password`` to match the values used for the validator and the
   DB created above.

   .. code-block:: ini

      opentsdb_url = "http://{host}:3000"

      # The name of the database used for storing metrics
      opentsdb_db = "metrics"

      opentsdb_username = "lrdata"
      opentsdb_password = "test"

#. Restart ``sawtooth-rest-api`` for these changes to take effect.

   If started via systemd:

   .. code-block:: console

      $ sudo systemctl restart sawtooth-rest-api

Telegraf Configuration
=======================

Telegraf is used on the Sawtooth validator nodes for sending OS and hardware
metrics to InfluxDB.

#. Install Telegraf from the InfluxData repository.

   .. code-block:: console

      $ curl -sL https://repos.influxdata.com/influxdb.key |  sudo apt-key add -
      $ sudo apt-add-repository "deb https://repos.influxdata.com/ubuntu xenial stable"
      $ sudo apt-get update
      $ sudo apt-get install telegraf

#. To configure Telegraf, edit ``/etc/telegraf/telegraf.conf``.

   .. code-block:: console

      $ sudo vi /etc/telegraf/telegraf.conf

#. Under ``[[outputs.influxdb]]``, change the following settings to match the
   values used above.

   .. code-block:: ini

      urls = ["http://{host}:8086"]
      database = "metrics"
      username = "lrdata"
      password = "{lrdata-pw}"

   .. note::
      Be sure to replace {host} with the IP or Fully Qualified Domain Name
      (FQDN) of the system running the InfluxDB Docker container.

#. Restart Telegraf.

   .. code-block:: console

      $ sudo systemctl restart telegraf

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
