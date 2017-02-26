from setuptools import setup, find_packages

setup(name='pychinadns',
      version='0.1',
      url='https://github.com/faicker/pychinadns',
      license='MIT',
      author='faicker.mo',
      author_email='faicker.mo@gmail.com',
      description='Nonpoisonous and CDN-friendly Recursive DNS Resolver',
      classifiers=[
          'Development Status :: 1 - Production/Stable',
          'Intended Audience :: Developers',
          'Topic :: Software Development :: Libraries',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
      ],
      entry_points = {
          'console_scripts' : [
          'pychinadns = pychinadns.chinadns:main'
          ],
      },
      packages=find_packages(exclude=['tests', 'util', 'etc']),
      data_files=[('etc/pychinadns/', ['etc/pychinadns/chnroute.txt']),
                  ('/etc/pychinadns/', ['etc/pychinadns/iplist.txt'])],
      long_description=open('README.md').read(),
      zip_safe=False,
      setup_requires=['argparse', 'dnslib'])
