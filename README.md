[![CircleCI](https://circleci.com/gh/kubos/majortom_gateway_package.svg?style=svg)](https://circleci.com/gh/kubos/majortom_gateway_package)

# Major Tom Gateway API Package
Python Package for interacting with Major Tom's Gateway API.

The Gateway API functions are accessible under the `GatewayAPI` class:

```python
from majortom_gateway import GatewayAPI
```

Use the `help()` function to see it's capability,
and check out our [demo gateway](https://github.com/kubos/example-python-gateway)
as an example of how to use it!

The `connect` or `connect_with_retries` functions must be called before any messages can be passed.

## Development

The Gateway API Package is currently in Beta,
so please [submit an issue](https://github.com/kubos/majortom_gateway_package/issues/new)
or [come talk to us](https://slack.kubos.com) if you have any comments/questions/feedback.

### Testing 

To run all tests, execute `./dockertest.sh` or push a branch and let the CI system do it.