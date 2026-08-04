"""Sphinx configuration for chardet documentation."""

import chardet

project = "chardet"
copyright = "2026, chardet contributors"
author = "chardet contributors"
release = chardet.__version__
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

autosummary_generate = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "plans", "adr"]

html_theme = "furo"
# No custom static assets; docs/_static/ is gitignored, and pointing
# html_static_path at a missing directory fails `sphinx-build -W` on a
# fresh checkout.

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

autodoc_member_order = "bysource"
autodoc_typehints = "description"
