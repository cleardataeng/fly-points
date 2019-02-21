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
import sys

import fly_points.routes

parser = argparse.ArgumentParser('Validate a YAML route table for fly-points')
parser.add_argument('file', nargs='?', type=argparse.FileType('r'),
                    default=sys.stdin,
                    help='file to validate, default to stdin')
args = parser.parse_args()


if __name__ == '__main__':
    raw_route_data = args.file.read()
    fly_points.routes.load_routes(raw_route_data)
