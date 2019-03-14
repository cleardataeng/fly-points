==========
fly-points
==========

fly-points is a simple kubernetes application to enable responsive
automation in GCP.  It does this by consuming log messages from
Stackdriver and routing them to different destinations.  Highlights:

* Messages are received via a Cloud Pub/Sub topic

* Messages can be delivered to Pub/Sub and HTTP endpoints

* Flexible routing config in YAML


The idea is to enable developers to write small services which respond
to specific Stackdriver log messages.  But without requiring lots of
granular exports, and without needing to filter messages in the
services.


Architecture
============

``fly-points-ingress`` is the main container.  It subscribes to a
Pub/Sub topic which has been configured as a Stackdriver export
destination.  A common subscription is used so that load can be spread
across multiple pods.  Two environment variables are provided for
configuration:

* ``PUBSUB_TOPIC``: the path to the Pub/Sub topic.  For example,
  ``projects/wooo-project/topics/log-sink``.

* ``PUBSUB_SUBSCRIPTION``: the path to the Pub/Sub subscription.  For
  example, ``projects/wooo-project/subscriptions/fly-points-ingress``

The subscription will be automatically created if it doesn't exist.


Routing configuration
=====================

``fly-points`` needs a YAML config file that defines its routes.  The
format is::

    routes:
      - name: <name>
        target:
          name: <pubsub topic name, put url target>
          type: <pubsub, put>
        matchers:
          - path: <jmespath>
            regexes:
              - <regex1>
              - <regex2>
	    literals:
	      - <literal1>
	      - <literal2>


The top-level key is always ``routes`` and it is always a list of
routes.  A route has two main parts, a target, and a list of matchers.

Targets define where to send messages.  ``fly-points`` can deliver
messages via Pub/Sub or HTTP PUT.

Matchers define which messages to send.  The ``path`` field indicates
which field in the Stackdriver logs should be considered.  jmespath is
used to specify the path, so you can easily look at embedded parts of
the log message.  You can provide regular expressions and string
literals to match against the content extracted from the messages at
``path``.  ``regexes`` is a list of regular expressions, ``literals``
is a list of string literals.  Either may be empty, but at least one
regex or literal must be provided.  Literals are intended to match
null/None values or regular expression special characters that appear
in logs.

Importantly: matchers are ANDed together, regexes/literals are ORed.
That is:
- at least one regex or literal must match in order for a matcher to match.
- every matcher must match for the route to trigger.


Here is a useful example::

  routes:
    - name: demo-put-target
      target:
        name: http://demo-put-target.fly-points.svc.cluster.local/
        type: put
      matchers:
        - path: logName
          regexes:
            - .*

    - name: demo-pubsub-target
      target:
        name: projects/wooo-yeah/topics/fly-points-demo-pubsub-target
        type: pubsub
      matchers:
        - path: protoPayload.methodName
          regexes:
            - google\.container\.v[a-z0-9]+.ClusterManager\.CreateCluster
	- path: operation.last
	  regexes:
	    - "True"


The first example is very simple.  It configures an HTTP PUT target
that receives every message sent from Stackdriver.

The second example is more interesting.  It configures a pubsub target
that only receives a subset of messages.  This target receives a
message if two conditions hold:

#. the GKE API was invoked to create a GKE cluster.
   ``protoPayload.methodName`` contains the name of the GCP method
   that was invoked, and ``CreateCluster`` is the method that creates
   clusters.
   
#. the cluster is done being created.  ``CreateCluster`` starts a
   long-running operation.  When that operation completes, Stackdriver
   receives a second create cluster log with ``operation.last`` set to
   ``True``.  (The regex is quoted to force the YAML parser to load it
   as a string instead of a boolean.)


Most anything that shows up in your Stackdriver logs can be extracted
and routed to a responding service using these techniques.  Since most
GCP services send detailed log messages to Stackdriver, you can build
automation to respond to almost any event that happens in your GCP
projects.


Demo targets
------------

The repo contains two demo targets that just print the messages they
receive.

* ``demo_pubsub_target``: this directory contains an example Cloud
  Pub/Sub target that receives messages from a given topic.

* ``demo_put_target``: this directory contains an example HTTP PUT
  target.  The example manifest deploys the service with `Knative's
  <https://github.com/knative/serving>`_ serving functionality.

   
Deploying
=========

This section explains how to deploy a simple two project test
environment.  One project is used to host ``fly-points``, the other is
the project that's exporting logs.

***NB:*** Be careful to avoid sending logs from ``fly-points`` to
 ``fly-points``!  This will create a infinite feedback loop.  Fun, but
 it won't be cheap if you leave it running for very long.  :)
 

Preliminary GCP setup
---------------------

Create your projects::

  $ export SOURCE_PROJECT=example-event-source
  $ export FLYPOINTS_PROJECT=fly-points-ingress
  $ gcloud projects create $SOURCE_PROJECT ...
  $ gcloud projects create $FLYPOINTS_PROJECT ...


Create a Pub/Sub topic to receive Stackdriver logs::

  $ export FLYPOINTS_TOPIC
  $ gcloud pubsub topic create $FLYPOINTS_TOPIC --project=$FLYPOINTS_PROJECT


Create and configure a logging sink to deliver data.  This involves
granting access the Stackdriver writer access to publish to the pubsub
topic::

  $ gcloud logging sinks create fly-points pubsub.googleapis.com/projects/$FLYPOINTS_PROJECT/topics/$FLYPOINTS_TOPIC --project=$SOURCE_PROJECT
  $ WRITER=$(gcloud logging sinks describe fly-points --project=$SOURCE_PROJECT --format="value(writerIdentity)")
  $ gcloud beta pubsub topics add-iam-policy-binding $FLYPOINTS_TOPIC --member=$WRITER --role=roles/pubsub.publisher --project=$FLYPOINTS_PROJECT


At this point, the Pub/Sub topic will be receiving all of the
Stackdriver logs from the source project.  Now you're ready to deploy
``fly-points``.


App deployment
--------------

Create a GKE cluster and activate it::

  $ gcloud container clusters create test-1 --project=$FLYPOINTS_PROJECT ...
  $ gcloud container clusters get-credentials test-1 --project=$FLYPOINTS_PROJECT ...


Create a namespace for ``fly-points``::

  $ kubectl create namespace fly-points


When running on GKE, ``fly-points`` needs a service account to
subscribe to the topic.  This service account will also need publisher
access to any downstream Pub/Sub targets that you create::

  $ gcloud iam service-accounts create fly-points
  $ gcloud beta pubsub topics add-iam-policy-binding $FLYPOINTS_TOPIC --member=serviceAccount:fly-points@$FLYPOINTS_PROJECT.iam.gserviceaccount.com --role=roles/pubsub.subscriber --project=$FLYPOINTS_PROJECT


To use this service account, the pods will need a key::

  $ gcloud iam service-accounts keys create key.json --iam-account=fly-points@$FLYPOINTS_PROJECT.iam.gserviceaccount.com
  $ kubectl -n fly-points create secret generic svc-acct --from-file=key.json
  $ rm key.json


Now you must create your ``routes.yaml`` file.  Before deploying, you
can check its syntax::

  $ cat routes.yaml | docker run -i cleardata/fly-points-ingress fp_validate_routes.py


If that exits successfully, add the routes as a ConfigMap::

  $ kubectl -n fly-points create configmap fly-points-config --from-file=routes.yaml


Tweak the deployment in ``fp-ingress-example.yml`` to your
satisfaction and deploy::

  $ kubectl -n fly-points apply -f fp-ingress-example.yml
