from setuptools import setup
import autoDownload

setup(
    name="autoDownload",
    version=autoDownload.__version__,
    keywords=["requests", "download", "http", "thread"],
    description="A simple, efficient, general-purpose Python multithreaded download library",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="kuankuan",
    author_email="2163826131@qq.com",
    url="https://github.com/auto-download/",
    install_requires=["requests", "rich", "exceptiongroup", "Deprecated"],
    packages=["autoDownload"],
    license="Mulan PSL v2",
    platforms=["windows", "linux", "macos"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "License :: OSI Approved :: Mulan Permissive Software License v2 (MulanPSL-2.0)",
        "Typing :: Typed",
    ],
    entry_points={
        "console_scripts": [
            "auto-download = autoDownload.__main__:main",
        ],
    },
)
