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

from marshmallow import fields, post_load, Schema, validate, validates_schema
from marshmallow.exceptions import ValidationError
import yaml

from . import routes


'''This module defines schema used to validate & load route
definitions for fly_points.

To understand the details, start at the bottom of this file and work
up towards the more-specific schemas.

A basic overview of the format::

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

Matchers are ANDed together, regexes are ORed.  That is:

- at least one regex must match in order for a matcher to match.
- every matcher must match for the route to trigger.

'''


class YamlRenderer(object):
    '''Expose yaml module with json's interface

    Marshmallow assumes that render_module has the python json
    module's interface: load/dump for (de)serializing to a file-like
    object, and loads/dumps for (de)serializing to a str.

    PyYAML's interface supports file-like or str via load/dump.  So
    this just adds names to match the json module's interface.
    '''
    loads = yaml.safe_load
    dumps = yaml.safe_dump


class CustomSchema(Schema):
    class Meta:
        strict = True
        dateformat = 'iso'
        render_module = YamlRenderer


class MatcherSchema(CustomSchema):
    '''Schema for an individual Matcher

    Matchers pull data from the incoming message using the jmespath
    expression provided in the path config element.  Then, that data
    is matched against the provided regexes.

    '''
    path = fields.Str(required=True)  # TODO: validate jmespath
    regexes = fields.List(fields.Str)  # TODO: validate regex
    literals = fields.List(fields.Str(allow_none=True))

    # must have either regexes or literals, allow both
    @validates_schema
    def validate_matcher(self, data):
        if 'regexes' not in data and 'literals' not in data:
            raise ValidationError(
                'A matches must have either regexes or literals defined'
            )

    @post_load
    def make_matcher(self, data):
        return routes.Matcher(**data)


class TargetSchema(CustomSchema):
    '''Schema for a Route Target

    Supports HTTP PUT and Cloud Pub/Sub targets.

    '''
    type = fields.Str(validate=validate.OneOf(
        choices=('pubsub', 'put'),
        error='Target type {input} is not one of {choices}',
    ))
    name = fields.Str(required=True)  # TODO: validate target

    @post_load
    def make_target(self, data):
        return routes.Target(**data)


class RouteSchema(CustomSchema):
    '''Schema for an individual Route entry

    A Route consists of a Target and one or more Matchers.

    '''
    name = fields.Str(required=True)
    target = fields.Nested(TargetSchema, required=True)
    matchers = fields.Nested(MatcherSchema, required=True, many=True)

    @post_load
    def make_route(self, data):
        return routes.Route(**data)


class RoutesFileSchema(CustomSchema):
    '''Top-level schema for a routes config file'''
    routes = fields.Nested(RouteSchema, required=True, many=True)
