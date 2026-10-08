# Installing BeeswaxBind

BeeswaxBind is a single-file Python command-line tool. It has **no third-party
runtime dependencies** — the standard library is enough — so the fastest install
is no install at all.

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.8 or newer | `python3 --version`. The system Python is fine; no virtualenv is required. |
| pip (optional) | Only needed for the optional console-entry-point install in step 1 below. |

Nothing else is installed: no compilers, no system libraries, no database, no
services. `install.sh` never calls `sudo`, `apt`, `brew` or any other system
package manager.

## Package manager

This project uses **pip** with `requirements.txt` (and `pyproject.toml` for the
console entry point). Do not substitute poetry/pipenv/conda.

## Step 1 (optional) — install the dependencies and the `beeswaxbind` command

```bash
bash install.sh
```

`install.sh` upgrades pip/setuptools/wheel, installs `requirements.txt`, installs
the package in editable mode so the `beeswaxbind` command is on your PATH, runs an
import self-check, prints the version, and then **exits**. It does not start
anything in the background and it does not start a server.

Skip this step entirely if you only want to run the tool:

```bash
python3 beeswaxbind.py --help
```

## Step 2 — verify the install

```bash
python3 beeswaxbind.py --version      # beeswaxbind 1.0.0
python3 beeswaxbind.py --help         # usage, commands and examples
beeswaxbind --version                 # only if you ran step 1
```

## Step 3 — run it

```bash
python3 beeswaxbind.py needle --thread 18/3 --leather 4oz
python3 beeswaxbind.py tension --spi 6
python3 beeswaxbind.py wax --parts 5:1 --batch 100g
python3 beeswaxbind.py reference --search 18/3
python3 beeswaxbind.py                # wizard, on a terminal only
bash demo.sh                          # non-interactive tour of everything
```

## Step 4 — run the test suite

```bash
python3 -m unittest discover -s tests   # standard library only
pytest                                   # the same suite, if pytest is installed
```

The suite is offline, non-interactive, and creates no files outside a temporary
directory.

## Uninstall

```bash
python3 -m pip uninstall beeswaxbind     # only if you ran step 1
```

The tool writes nothing to disk while it runs, so there is no state to remove.
