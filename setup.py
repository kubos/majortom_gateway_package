import setuptools
import os

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'VERSION')) as version_file:
    version = version_file.read().strip()

with open("README.md", "r") as readme:
    readme_content = readme.read()


setuptools.setup(
    name="majortom_gateway",
    version=version,
    author="Kubos",
    author_email="open-source@kubos.com",
    description="A package for interacting with Major Tom's Gateway API.",
    long_description=readme_content,
    long_description_content_type="text/markdown",
    url="https://github.com/kubos/majortom_gateway_package",
    packages=setuptools.find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent"
    ],
    python_requires='>=3.6',
    keywords='majortom major_tom gateway kubos major tom satellite',
    install_requires=[
        "websockets",
        "requests",
        "asgiref"
    ]
)
