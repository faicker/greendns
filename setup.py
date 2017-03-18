import sys
from setuptools import setup, find_packages

APP_VERSION = '0.3'

py_ver = sys.version[:3]
requires = []
if py_ver == '2.6':
    requires = ['argparse', 'dnslib==0.8.3']
elif py_ver == '2.7':
    requires = ['dnslib']
else:
    raise Exception("python version %s not supported" % (py_ver))

setup(name='pychinadns',
      version=APP_VERSION,
      url='https://github.com/faicker/pychinadns',
      license='MIT',
      author='faicker.mo',
      author_email='faicker.mo@gmail.com',
      description='A nonpoisonous and CDN-friendly Recursive DNS Resolver',
      classifiers=[
          'Development Status :: 1 - Production/Stable',
          'Intended Audience :: Developers',
          'Topic :: Software Development :: Libraries',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
      ],
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
