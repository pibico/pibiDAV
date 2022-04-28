from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in pibidav/__init__.py
from pibidav import __version__ as version

setup(
	name="pibidav",
	version=version,
	description="WebDAV, CalDAV and CardDAV Integration between Frappe and NextCloud",
	author="pibiCo",
	author_email="pibico.sl@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
