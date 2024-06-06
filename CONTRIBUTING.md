# Contributing

Contributions (pull requests) are very welcome!

First fork the library on GitHub. Then clone and install the library in development mode:

```bash
git clone https://github.com/your-username-here/patdb.git
cd patdb
pip install -e .
```

Then install the pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

These hooks use ruff to format and lint the code, and pyright to type-check it.

Then push your changes back to your fork of the repository:

```bash
git push
```

Finally, open a pull request on GitHub!
