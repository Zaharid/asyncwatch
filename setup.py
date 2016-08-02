from setuptools import setup, find_packages

with open('README.md') as f:
    long_description = f.read()


setup(
    name="asyncwatch",
    version='0.1',
    description="An asyncronous inotify wrapper based on curio",
    long_description = long_description,
    setup_requires=["cffi>=1.0"],
    cffi_modules=["asyncwatch/ffibuilder.py:I"],
    install_requires=["cffi>=1.0", "curio"],
    author="Zahari Kassabov",
    license="MIT",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
    ],
    packages=find_packages(),
)
