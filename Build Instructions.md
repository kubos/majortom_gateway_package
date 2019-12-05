# Building Package

1. Make sure you've updated the version in `setup.py` as appropriate

1. Run the following in the root directory of the repo to upload Pypi:

```
python3 setup.py sdist bdist_wheel

python3 -m twine upload dist/*
```

You'll need your pypi username and password.

[Reference](https://packaging.python.org/tutorials/packaging-projects/)
