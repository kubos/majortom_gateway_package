#!/bin/bash -e

docker build -t gateway_api_test_container -f Dockerfile.test .
docker run \
    --tty \
    --rm \
    gateway_api_test_container $@