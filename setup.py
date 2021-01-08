from setuptools import setup

setup(name='bean-to-ynab',
      version='1.0',
      description='Sync Beancount account balances to YNAB accounts.',
      author='Khanh Nguyen',
      packages=['bean_to_ynab'],
      install_requires=['beancount'],
      license='MIT',
      entry_points='''
        [console_scripts]
        bean-to-ynab=bean_to_ynab.bean_to_ynab:main
        '''
      )
