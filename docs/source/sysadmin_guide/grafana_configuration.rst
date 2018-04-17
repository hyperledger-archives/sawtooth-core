********************************
Configuring Grafana and InfluxDB
********************************

InfluxDB
========

The Sawtooth team provides Docker files for Grafana and InfluxDB for reporting statistics and monitoring network health.

First we will build the InfluxDB docker container

.. code-block:: console

  $ cd sawtooth-core/docker
  $ docker build . -f influxdb/sawtooth-stats-influxdb -t sawtooth-stats-influxdb

Next we will start the InfluxDB Docker container with persistent storage on the local file system and port 8086 exposed to the network. Make a note of the hash this command prints, we will use that in the next step.

.. code-block:: console

  $ sudo mkdir /var/lib/influx-data
  $ docker run -d -p 8086:8086 -v ~/influx-data:/var/lib/influxdb --name sawtooth-stats-influxdb sawtooth-stats-influxdb

Now we need to log into the container to create some InfluxDB users and enable authentication, without this step anybody can read or write data to Influxdb.
The above 'docker run' command printed a hash ID of the running InfluxDB container, we will use that here to identify the container we wish to spawn a shell inside.

.. code-block:: console

  $ docker exec -it {hash from run command} /bin/bash

Enter the InfluxDB client shell and create the admin user and a less privileged  user used to submit stats by Grafana the Sawtooth network.

.. code-block:: console

  $ influx
  > CREATE USER admin WITH PASSWORD 'test' WITH ALL PRIVILEGES
  > CREATE USER lrdata WITH PASSWORD 'example'
  > GRANT ALL ON "metrics" TO "lrdata"
  > quit
  $

Now enable authentication for InfluxDB

.. code-block:: console

  $ vi /etc/influxdb/influxdb.conf

Add the following.

.. code-block:: console

  [http]
    enabled = true
    bind-address = ":8086"
    auth-enabled = true
    log-enabled = true
    write-tracing = false
    pprof-enabled = false
    https-enabled = false

Exit the InfluxDB docker container

.. code-block:: console

  $ exit

Now restart the InfluxDB Docker container to make those changes live

.. code-block:: console

  $ docker stop sawtooth-stats-influxdb
  $ docker start sawtooth-stats-influxdb

Grafana
=======

First, build the Grafana Docker container.

.. code-block:: console

  $ cd sawtooth-core/docker
  $ docker build . -f grafana/sawtooth-stats-grafana -t sawtooth-stats-grafana
  $ docker run -d -p 3000:3000 --name sawtooth-stats-grafana sawtooth-stats-grafana

Grafana should now be accessible by IP address or FQDN at http://{host}:3000

.. note::

  The default login credentials are admin:admin

To change the password click the Grafana spiral icon at the top left of the web page and go to the Admin / Profile page, click on "Change Password"

Next configure Grafana to use InfluxDB as a data source

Click on the Grafana spiral icon at the top left of the web page and go to "Data Sources", then click on "Metrics". Change the URL to to the IP or FQDN of the server running InfluxDB.
Under "InfluxDB Details" enter the non admin user and password used in the influx section, then click "Save & Test".

.. note::

  Sawtooth 1.0.* requires the dashboard from the sawtooth 1-0 branch, while sawtooth 1.1.* can use the dashboard included in the Grafana Docker container.

If you are running sawtooth 1.1+ then you can use the included dashboard, however if deploying sawtooth 1.0.* then we must import the 1.0 dashboard. This dashboard can be retrieved from sawtooth-core/docker/grafana/dashboards/sawtooth_performance.json in the 1-0 branch, or downloaded from GitHub directly `sawtooth_performance.json <https://github.com/hyperledger/sawtooth-core/blob/1-0/docker/grafana/dashboards/sawtooth_performance.json>`_.

To import the dashboard click Grafana spiral logo on top left of page and go to "Dashboards/Import" and click "Upload .json file" navigate to the path where sawtooth_performance.json was saved, select "metrics" in the drop down menu and click "Import"

Sawtooth Configuration
======================

Sawtooth metrics are reported by the validator process its self and the configuration lives in /etc/sawtooth/validator.toml. If this file doesn't exist yet you can copy the template from /etc/sawtooth/validator.toml.example.

Fill in these values with the configurations used above. opentsdb_url is the ip / FQDM:port to the InfluxDB instance, opentsdb_db in this guide will be "metrics", then fill in the non admin user and password.

.. code-block:: console

  # The host and port for Open TSDB database used for metrics
  opentsdb_url = ""

  # The name of the database used for storing metrics
  opentsdb_db = ""

  opentsdb_username = ""

  opentsdb_password = ""

Restart sawtooth-validator for these changes to take effect.

Telegraph Configuration
=======================

Telegraph is used for OS / Hardware metrics

To configure Telegraph edit /etc/telegraf/telegraf.conf and modify urls, database, username, and password with the values used to configure sawtooth-validator, and restart the telegraph service.

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/
