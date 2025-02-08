# Building Documentation

To build documentation, download the dependencies, then build.

```bash
poetry install --with docs --no-root
cd docs
make html
```

Now, you should be able to open `docs/build/html/index.html` to view the documentation.

After installing the documentation dependenices and if you have added any new dependencies in your feature 
change, make sure to run
```bash
pip freeze > docs/docs_requirements.txt
```

> Yes, having a separate `docs_requirements.txt` is awful, but sadly `readthedocs.io` can't read `pyproject.toml`. 