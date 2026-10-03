# Log aggregator parser fixtures

Run the deterministic standard-library suite from the repository root:

```sh
python -m unittest discover -s tests -p "test_*.py" -v
```

The checked-in `.log` files are small, hand-written examples. Expected parser
records are literal values in `test_log_aggregator.py`; the parser is never used
to generate expected data. The CLI test uses a temporary output file and does
not contact services or depend on the current time.
