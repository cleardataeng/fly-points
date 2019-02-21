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
import os
import signal
import time
import warnings

import google.cloud.pubsub

parser = argparse.ArgumentParser('received demo events from a topic')
args = parser.parse_args()

# silence app default credentials warning
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    subscriber = google.cloud.pubsub.SubscriberClient()

# status flag, goes false on SIGTERM to cleanly exit
run = True


def main():
    global run

    # install handler for sigterm for clean shutdown
    signal.signal(signal.SIGINT, handle_sigterm)

    # setup the pubsub subscription & callback
    subscription = get_pubsub_subscription()

    try:
        while run:
            time.sleep(10)
    except KeyboardInterrupt:
        pass

    print('Closing subscription...')
    subscription.close()

    # This is just here to clean up after the demo.  In a real target,
    # you don't want to delete the subscription on exit.  It needs to
    # keep existing for other copies of the target!
    subscriber.delete_subscription(subscription.name)

    print('done!')


def callback(message):
    '''Receive a message pulled from the pubsub subscription'''
    print(message.data.decode('utf-8'))
    message.ack()


def handle_sigterm(signum, frame):
    global run
    print('Received SIGTERM, shutting down...')
    run = False


def get_pubsub_subscription():
    topic_name = os.getenv('PUBSUB_TOPIC')
    if not topic_name:
        raise ValueError('PUBSUB_TOPIC must be set')

    subscription_name = os.getenv('PUBSUB_SUBSCRIPTION_NAME')
    if not subscription_name:
        raise ValueError('PUBSUB_SUBSCRIPTION_NAME must be set')

    try:
        subscriber.create_subscription(subscription_name, topic_name)
        print('Successfully created subscription %s' % subscription_name)
    except google.api_core.exceptions.AlreadyExists:
        print('Found existing subscription')

    print('Opening subscription...')
    return subscriber.subscribe(subscription_name, callback)


if __name__ == '__main__':
    main()
