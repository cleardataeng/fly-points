FROM debian:stretch-slim

RUN apt-get update -q && \
    DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
    				   	   	   dumb-init \
    				   	   	   python3-dev \
    				   	   	   python3-pip \
						   python3-setuptools \
						   python3-wheel

COPY requirements.txt /tmp

RUN pip3 install -r /tmp/requirements.txt

COPY . /srv
WORKDIR /srv

VOLUME ["/etc/fly-points", "/etc/svc-acct"]

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/usr/bin/python3", "fp_ingress.py", "/etc/fly-points/routes.yaml"]
