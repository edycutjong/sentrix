.PHONY: test

test:
	PYTHONPATH=src pytest --cov=sentrix
