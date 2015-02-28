from setuptools import setup, find_packages
import sys

if sys.version_info >= ( 2, 7 ):
    requires.remove( 'ordereddict>=1.1' )
    
setup(
    
    name='net-config.py',
    version=0.9,
    license='BSD',
    author='Yee-Ting Li',
    author_email='ytl@slac.stanford.edu',
    description=doclines[0],
    long_description="\n".join(doclines[2:]),
    zip_safe=False,
    classifiers =[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',        
    ],
    platform='any',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    namespace_packages=['netconfig'],
    
)