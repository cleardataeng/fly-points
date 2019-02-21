# Copyright 2019 ClearDATA Networks, Inc.. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import collections
import json
import os
import pprint
import signal
import time
import warnings

import google.cloud.error_reporting
import google.cloud.logging
import google.cloud.pubsub

import fly_points.routes

parser = argparse.ArgumentParser('route events from the stackdriver topic')
parser.add_argument('--local', action='store_true',
                    help='Tweak to run locally.  This manages a new subscription and suppresses stackdriver logging & error reporting.')
parser.add_argument('routes_file',
                    help='YAML file with routing rules to load.')
args = parser.parse_args()

# silence app default credentials warning
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    error_reporting = google.cloud.error_reporting.Client()
    subscriber = google.cloud.pubsub.SubscriberClient()
    pubsub_publisher = google.cloud.pubsub.PublisherClient()
    stackdriver_log = google.cloud.logging.Client().logger('fly-points-ingress')

# status flag, goes false on SIGTERM to cleanly exit
run = True

# global metrics
global_metrics = collections.defaultdict(int)

# routing table
routes = None

# publisher object
publisher = None


def main():
    global publisher, routes, run

    # install handler for sigterm for clean shutdown
    signal.signal(signal.SIGINT, handle_sigterm)

    # load the routes
    with open(args.routes_file) as f:
        raw_route_data = f.read()
    log_text('Loaded raw route data:')
    log_text(raw_route_data)

    routes = fly_points.routes.load_routes(raw_route_data)
    log_text('Resulting route table:')
    log_text(repr(routes))

    # setup the pubsub subscription & callback
    subscription = get_pubsub_subscription()

    # instantiate the publisher abstraction
    publisher = fly_points.routes.Publisher(pubsub_publisher)

    # the main app loop just logs the metrics & sleeps
    try:
        while run:
            log_struct({
                'metrics': {
                    'global': dict(global_metrics),
                    'per_route': {r.name: dict(r.metrics) for r in routes},
                },
            })
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    except Exception:
        report_exception()

    log_text('Cancelling subscription...')
    subscription.cancel()

    # local runs need to nuke the subscription
    if args.local:
        sub_name = subscription.subscription
        log_text('Deleting subscription %s' % sub_name)
        subscriber.delete_subscription(subscription.subscription)

    print('done!')


def callback(message):
    '''Receive a message pulled from the pubsub subscription'''
    global publisher, routes

    global_metrics['received'] += 1

    # decode the message.  If it fails, record the failure and return
    try:
        decoded = json.loads(message.data.decode('utf-8'))
    except Exception:
        global_metrics['decode_errors'] += 1
        report_exception()
        message.ack()
        return

    # for each route, attempt to handle
    for route in routes:
        try:
            if route(decoded):
                publisher(decoded, route)
                global_metrics['transmitted'] += 1
        except Exception:
            global_metrics['routing_errors'] += 1
            report_exception()

    message.ack()


def handle_sigterm(signum, frame):
    global run
    log_text('Received SIGTERM, shutting down...')
    run = False


def get_pubsub_subscription():
    topic_name = os.getenv('PUBSUB_TOPIC')
    if not topic_name:
        raise ValueError('PUBSUB_TOPIC must be set')

    subscription_name = os.getenv('PUBSUB_SUBSCRIPTION_NAME')
    if not subscription_name:
        raise ValueError('PUBSUB_SUBSCRIPTION_NAME must be set')

    # local runs needs to create a separate subscription
    if args.local:
        subscription_name += '-local-%d' % time.time()

    # Someone needs to create the subscription, but it can only be
    # created once.  Do it at startup, and ignore errors.
    #
    # NB: unless you're decomming this app, don't delete this
    # subscription.  There's probably other pods using it.
    try:
        subscriber.create_subscription(subscription_name, topic_name)
        log_text('Successfully created subscription %s' % subscription_name)
    except google.api_core.exceptions.AlreadyExists:
        log_text('Found existing subscription')

    log_text('Opening subscription...')
    return subscriber.subscribe(subscription_name, callback)


def log_struct(struct):
    if args.local:
        pprint.pprint(struct)
    else:
        stackdriver_log.log_struct(struct)


def log_text(text):
    if args.local:
        print(text)
    else:
        stackdriver_log.log_text(text)


def report_exception():
    if not args.local:
        error_reporting.report_exception()


if __name__ == '__main__':
    main()
