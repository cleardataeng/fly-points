FROM debian:stretch-slim

RUN apt-get update -q && \
    DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
    				   	   	   dumb-init \
						   python3-dev \
						   python3-pip \
						   python3-setuptools \
						   python3-wheel

RUN pip3 install google-cloud-pubsub

COPY . /srv
WORKDIR /srv

CMD ["/usr/bin/dumb-init", "--", "/usr/bin/python3", "demo_pubsub_target.py" ]
