from setuptools import setup

setup(name='grappled',
      version='0.1.0',
      description='Grapple GitHub Webhook Listener',
      long_description='Listens to webhooks sent by GitHub and runs custom actions. Supports multiple endpoints for different projects, IP filtering, etc.',
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 Only',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
      ],
      url='https://github.com/gauravmm/grappled',
      author='Gaurav Manek',
      author_email='gaurav@gauravmanek.com',
      license='MIT',
      packages=['grappled'],
      install_requires=[
          'Flask',
          'ipaddress',
          'requests',
          'expiringdict',
      ],
      include_package_data=True)