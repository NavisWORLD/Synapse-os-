# Optional Beast runtime for Synapse OS

Synapse OS is the Debian Linux OS with its existing C, C++ and Rust SDK. This
integration adds an optional Python user-space runtime; it does not change the
native SDK ABI, boot path, installer, or disk-writing tools.

The source branch adds a `synapse-beast` entry point. Existing alpha ISO images
do not contain these unbuilt changes. No physical-device certification is implied.

## Install and run

Use an ordinary user account with Python 3.11+ and venv/ensurepip available. From
this checkout, create a user virtual environment and install the Synapse control
package (build tooling may require internet access):

```sh
python3 -m venv ~/.local/share/synapse-control-venv
~/.local/share/synapse-control-venv/bin/python -m pip install .
~/.local/share/synapse-control-venv/bin/synapse-beast install
~/.local/share/synapse-control-venv/bin/synapse-beast run init
~/.local/share/synapse-control-venv/bin/synapse-beast run chat "Remember the sunflower code is marigold"
~/.local/share/synapse-control-venv/bin/synapse-beast run inspect
~/.local/share/synapse-control-venv/bin/synapse-beast run chat "What is the sunflower code?"
```

The installer fetches only the published BeastBox v0.4.0 wheel, associated with
source commit `b6fd43a`, from:

https://github.com/NavisWORLD/The-beast-box-/releases/download/v0.4.0/cosmos_beast_box-0.4.0-py3-none-any.whl

It verifies SHA-256 before invoking pip:

```text
e0c2e5f55d594bfdfc0ba1d74ab9d9fd18f683cc0fb153aec3730b2ae428fdd3
```

Pip installs into a private hash-specific virtual environment with `--no-index
--no-deps`. Root execution is refused. The active selection changes only after a
successful installation. Repeating the same install preserves the environment and
runtime data. The launcher uses isolated Python mode to avoid importing a source
checkout instead of the installed wheel.

For an offline copy of this exact release:

```sh
synapse-beast install --wheel /path/cosmos_beast_box-0.4.0-py3-none-any.whl --sha256 e0c2e5f55d594bfdfc0ba1d74ab9d9fd18f683cc0fb153aec3730b2ae428fdd3
```

An explicitly supplied local wheel and hash are an intentional trust override;
verify the hash independently. The default published release hash cannot be
overridden without supplying a local wheel.

State persists in `$XDG_DATA_HOME/synapse-beast/runtime`, or
`~/.local/share/synapse-beast/runtime` by default. Keep the same user and XDG path
across restarts. `--data-dir` is managed by the launcher and cannot be overridden.
Back up this directory before changing runtime versions; no schema migration or
version downgrade compatibility is promised. There is no auto-start service.

## Verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_beast_runtime.py -v
SYNAPSE_BEAST_RELEASE_WHEEL=/path/cosmos_beast_box-0.4.0-py3-none-any.whl PYTHONPATH=src python3 -m unittest discover -s tests -p test_beast_runtime.py -v
make check
```

The tests cover failed-hash refusal, local hash requirements, actual root refusal,
clean wheel installation, idempotency and separate-process persistent state. In a
single-UID root container, the harness substitutes only the identity check for
installation tests; that is not evidence of a real non-root execution. CI runs the
same tests as an ordinary runner user with the real published wheel, plus the
existing native SDK and full source checks. CI does not build or certify an ISO.

Debian 13 may default to Python 3.13. Beast v0.4.0 supports Python 3.10–3.12;
provide an installed supported interpreter with `synapse-beast install --python
/path/to/python3.12`. The installer fails before changing the environment when
the selected interpreter is unsupported. This adapter does not replace the OS
Python or claim the published alpha ISO already includes these new files.
