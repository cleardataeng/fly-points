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

import collections
import json
import re

import jmespath
import requests

from . import route_schema


class Matcher(object):
    '''Represents one thing to match a route against.

    A Matcher has a path and a list of regexes.  If the value at path
    matches any one of the regexes, then the Matcher returns True.

    Args:
        path (str): a jmespath expression to extract data from a message
        regexes (list): a list of regexes to test the extracted data

    '''
    def __init__(self, path, regexes):
        if not isinstance(regexes, list) or len(regexes) < 1:
            raise ValueError('Invalid matcher: regexes must be a non-empty list')

        self.path = jmespath.compile(path)
        self.regexes = [re.compile(x) for x in regexes]

    def __call__(self, message):
        value = self.path.search(message)

        # only check the regexes if the path extracted something
        if value:
            for r in self.regexes:
                if r.search(str(value)):
                    return True

        return False

    def __repr__(self):
        return '%s(path=%s, regexes=%s)' % (
            self.__class__.__name__,
            self.path.expression,
            self.regexes,
        )


class Target(object):
    '''Represents a configured target for a route'''
    def __init__(self, name, type):
        self.name = name
        self.type = type

    def __repr__(self):
        return '%s(type=%s, name=%s)' % (
            self.__class__.__name__,
            self.type,
            self.name,
        )


class Route(object):
    '''Represents a possible target for log messages.

    A Route has at least one Matcher and a target.  If every Matcher
    matches a given message, then the message gets PUT to the target
    URL.  In this case, return True.  Otherwise, return False.

    Args:
        name (str): the name of this route
        matchers (list): a list of Matchers
        target (Target): the Target associated with this Route

    Return:
        bool, True on a match, False otherwise

    '''
    def __init__(self, name, target, matchers):
        self.name = name
        self.target = target
        self.matchers = matchers

        self.metrics = collections.defaultdict(int)

    def __call__(self, message):
        '''Check if this message matches this Route'''
        self.metrics['received'] += 1

        for matcher in self.matchers:
            if not matcher(message):
                self.metrics['msg_no_match'] += 1
                return False

        self.metrics['msg_matched'] += 1
        return True

    def __repr__(self):
        return '%s(name=%s, target=%s, matchers=%s)' % (
            self.__class__.__name__,
            self.name,
            repr(self.target),
            [repr(x) for x in self.matchers],
        )


class Publisher(object):
    '''Publish a message to a route

    This class provides an abstraction for the different target types.

    Args:
        pubsub_publisher: a pubsub PublisherClient instance to use for
            pubsub route targets

    '''

    def __init__(self, pubsub_publisher):
        self.pubsub_publisher = pubsub_publisher

    def __call__(self, message, route):
        '''Publish message to the route's target

        Args:
            message (object): json-serializable message to send
            route (Route): the route for delivery

        Returns:
            bool: True if transmission was successful, False on error

        '''
        try:
            self._publish(message, route.target)
            route.metrics['transmit_success'] += 1
        except Exception:
            route.metrics['transmit_errors'] += 1
            raise      # re-raise so the caller can detect the failure

        return True

    def _publish(self, message, target):
        '''Publish a message to a target

        Args:
            message (object): the event, a json-serializable object

        Raises:
            TypeError: if publisher is None and this is a pubsub target

        '''
        if target.type == 'put':
            requests.put(target.name, json=message, timeout=1)

        if target.type == 'pubsub':
            if self.pubsub_publisher is None:
                raise TypeError('Must provide pubsub publisher')

            self.pubsub_publisher.publish(
                target.name,
                json.dumps(message).encode('utf-8'),
            )


def load_routes(route_data):
    '''Build routes

    Args:
        route_data: raw data read in from a routes file

    Return:
        list of Routes

    '''

    route_file_schema = route_schema.RoutesFileSchema()
    route_info = route_file_schema.loads(route_data)
    return route_info['routes']  # no need to check, marshmallow did that
