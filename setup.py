from setuptools import setup
import toml

with open("pyproject.toml", "r") as f:
    requirements = toml.loads(f.read())

prod = requirements["tool"]["poetry"]["dependencies"]
dev = requirements["tool"]["poetry"]["dev-dependencies"]

prod.pop("python")

install_requires = [x + prod[x].replace("^", "==") if prod[x] != "*" else x for x in prod]
extras_require = {"dev": [x + dev[x].replace("^", "==") if dev[x] != "*" else x for x in dev]}

setup(
    name=requirements["tool"]["poetry"]["name"],
    version=requirements["tool"]["poetry"]["version"],    
    description=requirements["tool"]["poetry"]["description"],
    url=requirements["tool"]["poetry"].get("url", ""),
    author=requirements["tool"]["poetry"]["authors"][0].split(" <")[0],
    author_email=requirements["tool"]["poetry"]["authors"][0].split(" <")[0].replace(">", ""),
    license=requirements["tool"]["poetry"].get("license", "None"),
    packages=[requirements["tool"]["poetry"]["name"].replace("-", "_")],
    install_requires=install_requires,
    extras_require=extras_require,
)
