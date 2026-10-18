"""Guards the Vercel entrypoint (vercel.json: "entrypoint": "index:app").
`ruff --fix` has previously treated api/index.py's import as an unused
import and deleted it, which breaks the deployed API -- see the
per-file-ignore in pyproject.toml. This test fails if index.py goes back
to being empty or stops exposing `app`."""

from __future__ import annotations

import importlib


def test_index_module_exposes_the_fastapi_app() -> None:
    import index

    importlib.reload(index)

    from proofline.app import app as proofline_app

    assert index.app is proofline_app
