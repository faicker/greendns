import sys
from setuptools import setup, find_packages
from greendns import __version__

try:
    import pypandoc
    long_description = pypandoc.convert_file('README.md', 'rst')
except ImportError:
    long_description = open('README.md').read()

py_ver = sys.version[:3]
requires = ['dnslib', 'six']
if py_ver == '2.6':
    requires += ['argparse']

setup(name='greendns',
      version=__version__,
      url='https://github.com/faicker/greendns',
      license='MIT',
      platforms=['unix', 'linux', 'osx', 'cygwin', 'win32'],
      author='faicker.mo',
      author_email='faicker.mo@gmail.com',
      description='A non-poisonous and CDN-friendly Recursive DNS Resolver',
      long_description=long_description,
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: System Administrators',
          'Topic :: Internet :: Name Service (DNS)',
          'Topic :: System :: Networking',
          'License :: OSI Approved :: MIT License',
          'Operating System :: POSIX',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: MacOS :: MacOS X'] + [
          ('Programming Language :: Python :: %s' % x) for x in
          '2 2.7 3 3.4 3.5 3.6 3.7'.split()],
      entry_points={
          'console_scripts': [
              'greendns = greendns.greendns:main'
          ],
      },
      packages=find_packages(exclude=['tests', 'tools', 'etc']),
      data_files=[('etc/greendns/', ['etc/greendns/localroute.txt']),
                  ('etc/greendns/', ['etc/greendns/iplist.txt'])],
      zip_safe=False,
      install_requires=requires)
