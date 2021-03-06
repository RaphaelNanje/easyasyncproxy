from setuptools import setup

setup(
    name='easyasyncproxy',
    version='3.0.0',
    packages=['easyasyncproxy', 'easyasyncproxy.proxy',
              'easyasyncproxy.proxy.tests',
              'easyasyncproxy.scraperapi',
              'easyasyncproxy.scraperapi.tests',
              'easyasyncproxy.scrapestack',
              'easyasyncproxy.scrapestack.tests'],
    url='https://github.com/RaphaelNanje/easyproxy',
    license='MIT',
    author='Raphael Nanje',
    author_email='rtnanje@gmail.com',
    description='',
    install_requires=[
        'requests',
        'requests[socks]',
        'yarl',
        'attrs',
        'urllib3'
    ],
    extras_require={
        'dev': ['python-dotenv']
    }
)
