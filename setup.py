# Minimal setup script to build Cython extensions

from setuptools import setup, Extension
from Cython.Build import cythonize
import pathlib

# Discover the .pyx file(s) in the engine package
engine_path = pathlib.Path(__file__).parent / "src" / "chronosmatch" / "engine"
extensions = [
    Extension(
        name="chronosmatch.engine.cython_lob",
        sources=[str(engine_path / "cython_lob.pyx")],
    )
]

setup(
    name="chronosmatch",
    ext_modules=cythonize(extensions, language_level=3),
    zip_safe=False,
)
