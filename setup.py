import sys
from setuptools import setup, find_packages

APP_VERSION = '0.3'

py_ver = sys.version[:3]
requires = ['dnslib', 'six']
if py_ver == '2.6':
    requires += ['argparse']

setup(name='pychinadns',
      version=APP_VERSION,
      url='https://github.com/faicker/pychinadns',
      license='MIT',
      platforms=['unix', 'linux', 'osx', 'cygwin', 'win32'],
      author='faicker.mo',
      author_email='faicker.mo@gmail.com',
      description='A non-poisonous and CDN-friendly Recursive DNS Resolver',
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
          '2 2.6 2.7 3 3.3 3.4 3.5 3.6'.split()],
      entry_points={
          'console_scripts': [
              'pychinadns = pychinadns.chinadns:main'
          ],
      },
      packages=find_packages(exclude=['tests', 'util', 'etc']),
      data_files=[('etc/pychinadns/', ['etc/pychinadns/chnroute.txt']),
                  ('etc/pychinadns/', ['etc/pychinadns/iplist.txt'])],
      long_description=open('README.md').read(),
      zip_safe=False,
      install_requires=requires)
