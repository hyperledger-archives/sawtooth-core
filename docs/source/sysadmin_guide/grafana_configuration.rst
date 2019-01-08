*****************************************
Using Grafana to Display Sawtooth Metrics
*****************************************

This procedure describes how to display Sawtooth metrics with
`Grafana <https://grafana.com>`__, using
`InfluxDB <https://www.influxdata.com/time-series-platform/influxdb/>`__
to store the metrics data.

.. note::

   This procedure is for a Ubuntu environment. For a Sawtooth network in Docker
   containers, there are additional steps to change the configuration of the
   validator and REST API containers. This guide does not describe these steps.


Prerequisites
=============

* Docker Engine must be installed

* One or more Sawtooth nodes must be configured and in a runnable state

* Download the
  `hyperledger/sawtooth-core <https://github.com/hyperledger/sawtooth-core>`_
  repository from GitHub with this command:

  .. code-block:: console

     $ git clone https://github.com/hyperledger/sawtooth-core.git


Set Up InfluxDB
===============

InfluxDB is used to store Sawtooth metrics data.

#. Pull the InfluxDB Docker image from Docker Hub.

   .. code-block:: console

      $ docker pull influxdb

#. Create an InfluxDB data directory to provide persistent storage on the local
   file system.

   .. note::

      This step creates the directory ``/var/lib/influx-data``. If this path is
      not appropriate for your host operating system, change the path here and
      in the next command.

   .. code-block:: console

      $ sudo mkdir /var/lib/influx-data

#. Start an InfluxDB Docker container. This command exposes port 8086 to the
   network and uses the persistent storage created in the previous step. It also
   configures the database name (``metrics``) and creates two users for
   InfluxDB, ``admin`` and ``lrdata``.


   In the following command, replace ``{admin-pw}`` and ``{lrdata-pw}`` with
   unique passwords for the ``admin`` and ``lrdata`` users. Remember to properly
   escape any special characters in these passwords, such as ``,@!$``.

   .. code-block:: console

      $ docker run -d -p 8086:8086 -v /var/lib/influx-data:/var/lib/influxdb \
       -e INFLUXDB_DB=metrics -e INFLUXDB_HTTP_AUTH_ENABLED=true \
       -e INFLUXDB_ADMIN_USER=admin -e INFLUXDB_ADMIN_PASSWORD='{admin-pw}' \
       -e INFLUXDB_USER=lrdata -e INFLUXDB_USER_PASSWORD='{lrdata-pw}' \
       --name sawtooth-stats-influxdb influxdb


Install and Configure Grafana
=============================

#. Build the Grafana Docker image from the Dockerfile that is included in the
   ``sawtooth-core`` repository.

   .. code-block:: console

      $ cd sawtooth-core/docker
      $ docker build . -f grafana/sawtooth-stats-grafana \
       -t sawtooth-stats-grafana

#. Run the Grafana container.

   .. code-block:: console

      $ docker run -d -p 3000:3000 --name sawtooth-stats-grafana \
       sawtooth-stats-grafana

#. Open the Grafana web page at ``http://{host}:3000``.

   In this URL, replace ``{host}`` with the IP or Fully Qualified Domain Name
   (FQDN) of the system running the Grafana Docker container.

#. On the Grafana web page, log in as user ``admin`` with the password ``admin``.

#. Change the admin password. First, click on the Grafana spiral icon at the
   top left of the web page and go to "Admin / Profile". Next, click on
   "Change Password".

#. Configure Grafana to use InfluxDB as a data source.

   a. Click on the Grafana spiral icon at the top left of the web page and go to
      "Data Sources".

   #. Click on "Metrics".

   #. Change the URL to the host server (IP or FQDN) running the InfluxDB
      Docker container.

   #. Under "InfluxDB Details", set ``INFLUXDB_USER`` to ``lrdata``. For
      ``INFLUXDB_USER_PASSWORD``, enter the ``lrdata`` password that was defined
      when you set up InfluxDB.

   #. Click "Save & Test".

#. (Sawtooth 1.0.* releases only) Import the Grafana 1.0 dashboard.

   .. note::

      Skip this step for Sawtooth release 1.1 and later, which can use the
      dashboard that is included in the Grafana Docker container from git
      master.

   a. Use one of these methods to get the 1.0 dashboard:

      - Find the dashboard in the 1-0 branch at
        ``sawtooth-core/docker/grafana/dashboards/sawtooth_performance.json``

      - Download the dashboard from GitHub at this location:
        `hyperledger/sawtooth-core/1-0/docker/grafana/dashboards/sawtooth_performance.json
        <https://raw.githubusercontent.com/hyperledger/sawtooth-core/1-0/docker/grafana/dashboards/sawtooth_performance.json>`_

   b. Click on the Grafana spiral logo and mouse over "Dashboards", then click
      "Import".

   #. Click "Upload .json file".

   #. Navigate to the location of ``sawtooth_performance.json``.

   #. Select "metrics" in the drop-down menu and click "Import".


Configure the Sawtooth Validator for Grafana
============================================

The ``sawtooth-validator`` process reports metrics for the Sawtooth validator.
Use the validator configuration file, ``/etc/sawtooth/validator.toml``, to
specify the validator settings for Grafana.

#. If the validator configuration file doesn't exist yet, copy the template
   from ``/etc/sawtooth/validator.toml.example`` to
   ``/etc/sawtooth/validator.toml``. For more information, see
   :doc:`configuring_sawtooth/validator_configuration_file`.

   .. note::

      The default config directory is ``/etc/sawtooth/``. For information on
      finding the config directory in a non-default location, see
      :doc:`configuring_sawtooth/path_configuration_file`.

#. Edit ``/etc/sawtooth/validator.toml``. Change the following settings to the
   values that you defined when you set up InfluxDB:

   * ``opentsdb_url``: Enter the IP or FQDN:port to the InfluxDB instance
   * ``opentsdb_db``: Enter ``metrics`` (the value of ``INFLUXDB_DB``)
   * ``opentsdb_username``: Enter ``lrdata`` (the ``INFLUXDB_USER``)
   * ``opentsdb_password``: Enter the password for ``INFLUXDB_USER_PASSWORD``

   .. code-block:: ini

      # The host and port for Open TSDB database used for metrics
      opentsdb_url = "http://{host}:8086"

      # The name of the database used for storing metrics
      opentsdb_db = "metrics"

      opentsdb_username  = "lrdata"

      opentsdb_password  = "{lrdata-pw}"

   .. note::

      For ``opentsdb_url``, be sure to replace  the existing host name with the
      IP or FQDN of the system running the InfluxDB Docker container.

#. Restart the validator for these changes to take effect.

   * If the validator was started as a ``systemd`` service:

       .. code-block:: console

          $ sudo systemctl restart sawtooth-validator

   * To restart ``sawtooth-validator`` on the command line, see the appropriate
     procedure in the Application Developer's Guide: either
     :doc:`../app_developers_guide/ubuntu` or :ref:`proc-multi-ubuntu-label`.


Configure the Sawtooth REST API for Grafana
===========================================

The ``sawtooth-rest-api`` process reports metrics for the Sawtooth REST API.
Use the REST API configuration file, ``/etc/sawtooth/rest_api.toml``, to specify
the REST API settings for Grafana.

#. If the REST API configuration file doesn't exist yet, copy the template from
   ``/etc/sawtooth/rest_api.toml.example`` to ``/etc/sawtooth/rest_api.toml``.
   For more information, see
   :doc:`configuring_sawtooth/rest_api_configuration_file`.

   .. note::

      The default config directory is ``/etc/sawtooth/``. For information on
      finding the config directory in a non-default location, see
      :doc:`configuring_sawtooth/path_configuration_file`.

#. Modify ``opentsdb_url``, ``opentsdb_db``, ``opentsdb_username``, and
   ``opentsdb_password`` to match the values used for the validator.

   .. code-block:: ini

      opentsdb_url = "http://{host}:8086"

      # The name of the database used for storing metrics
      opentsdb_db = "metrics"

      opentsdb_username = "lrdata"
      opentsdb_password  = "{lrdata-pw}"

#. Restart the REST API (``sawtooth-rest-api``) for these changes to take effect.

   * If the REST API was started as a ``systemd`` service:

       .. code-block:: console

          $ sudo systemctl restart sawtooth-rest-api

   * To restart ``sawtooth-rest-api`` on the command line, see the appropriate
     procedure in the Application Developer's Guide: either
     :doc:`../app_developers_guide/ubuntu` or :ref:`proc-multi-ubuntu-label`.
     :ref:`proc-multi-ubuntu-label`.


Configure Telegraf
==================

`Telegraf <https://www.influxdata.com/time-series-platform/telegraf/>`_ runs on
the Sawtooth nodes to send operating system and hardware metrics to InfluxDB.

#. Install Telegraf from the InfluxData repository.

   .. code-block:: console

      $ curl -sL https://repos.influxdata.com/influxdb.key |  sudo apt-key add -
      $ sudo apt-add-repository "deb https://repos.influxdata.com/ubuntu xenial stable"
      $ sudo apt-get update
      $ sudo apt-get install telegraf

#. Edit ``/etc/telegraf/telegraf.conf`` to configure Telegraf.

   .. code-block:: console

      $ sudo vi /etc/telegraf/telegraf.conf

#. Under ``[[outputs.influxdb]]``, change the following settings to match the
   values that you defined when you set up InfluxDB.

   .. code-block:: ini

      urls = ["http://{host}:8086"]
      database = "metrics"
      username = "lrdata"
      password = "{lrdata-pw}"

   .. note::

      Be sure to replace ``{host}`` with the IP or FQDN of the system running
      the InfluxDB Docker container.

#. Restart the Telegraf service.

   .. code-block:: console

      $ sudo systemctl restart telegraf

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
