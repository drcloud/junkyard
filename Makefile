.PHONY: test check flake8

test:
	tox

check: flake8

flake8:
	flake8 drcloud setup.py
