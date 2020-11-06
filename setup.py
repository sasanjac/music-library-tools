from setuptools import setup
import toml

with open("pyproject.toml", "r") as f:
    requirements = toml.loads(f.read())

prod = requirements["tool"]["poetry"]["dependencies"]
dev = requirements["tool"]["poetry"]["dev-dependencies"]

setup(
    install_requires=[x + prod[x].replace("^", "==") if prod[x] != "*" else x for x in prod],
    extras_require={"dev": [x + dev[x].replace("^", "==") if dev[x] != "*" else x for x in dev]},
)
