#!/bin/bash

docker build -t gateway_api_test_container -f Dockerfile.test .
docker run -it \
    -v $(pwd):/app \
    gateway_api_test_container $1