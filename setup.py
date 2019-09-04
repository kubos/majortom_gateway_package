import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="majortom_gateway",
    version="0.0.3",
    author="Kubos",
    author_email="open-source@kubos.com",
    description="A package for interacting with Major Tom's Gateway API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kubos/majortom_gateway_package",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent"
    ],
    python_requires='>=3.7',
)
