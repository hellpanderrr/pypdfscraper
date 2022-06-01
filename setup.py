from setuptools import setup

setup(
    name='pypdfscraper',
    version='0.1.0',
    packages=['tests', 'pdfscraper', 'pdfscraper.layout'],
    url='',
    license='',
    author='hellpanderrr',
    author_email='hellpanderrr@gmail.com',
    description='',
    install_requires = ['typing_extensions '],
    extras_require = {
        "pdfminer": ["pdfminer.six"],
        "pymupdf": ['pymupdf'],
    }
)
