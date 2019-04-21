import sys
from setuptools import setup, find_packages
from greendns import __version__

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
      long_description=open('README.md').read(),
      long_description_content_type='text/markdown',
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
          '2 2.6 2.7 3 3.3 3.4 3.5 3.6 3.7'.split()],
      entry_points={
          'console_scripts': [
              'greendns = greendns.server:main'
          ],
      },
      packages=find_packages(exclude=['tests', 'tools', 'etc']),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires)
