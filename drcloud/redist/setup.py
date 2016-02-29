#!/usr/bin/env python

from datetime import datetime
import os
from setuptools import setup
from subprocess import check_output, CalledProcessError


def version():
    from_file, from_git = None, None
    receipt = 'drcloud/VERSION'
    default = datetime.utcnow().strftime('%Y%m%d') + '+src'
    if os.path.exists('.git'):
        try:
            branch = check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
            branch = branch.strip()
            tag = check_output(['git', 'describe'])
            dotted = tag.strip().replace('-', '.', 1).split('-')[0]
            from_git = dotted + ('' if branch == 'master' else '+' + branch)
        except CalledProcessError:
            pass
    if os.path.exists(receipt):
        with open(receipt) as h:
            txt = h.read().strip()
            if txt != '':
                from_file = txt
    version = from_git or from_file or default
    with open(receipt, 'w+') as h:
        h.write(version + '\n')
    return version


conf = dict(name='drcloud',
            version=version(),
            install_requires=['attrs',
                              'awacs',
                              'boto3',
                              'click',
                              'enum34',
                              'ipython',
                              'netaddr',
                              'nose',
                              'oset',
                              'psycopg2',
                              'ptpython',
                              'pytz',
                              'schematics',
                              'sh',
                              'sqlparse',
                              'tabulate',
                              'troposphere',
                              'tzlocal'],
            extras_require={'node': ['python-iptables', 'inotify']},
            setup_requires=['setuptools'],
            tests_require=['flake8', 'nose', 'tox'],
            description='Dr. Cloud, the programmable PaaS.',
            packages=['drcloud',
                      'drcloud.cloud',
                      'drcloud.cloud.aws',
                      'drcloud.protocol',
                      'drcloud.redist',
                      'drcloud.rx',
                      'drcloud.test',
                      'drcloud.test.integration',
                      'drcloud.unix_conf_snippets',
                      'drcloud.sql'],
            package_data={'drcloud': ['VERSION'],
                          'drcloud.sql': ['*.sql']},
            entry_points={'console_scripts':
                          ['drcloud = drcloud.__main__:main']},
            classifiers=['Environment :: Console',
                         'Intended Audience :: Developers',
                         'Operating System :: Unix',
                         'Operating System :: POSIX',
                         'Programming Language :: Python',
                         'Topic :: System',
                         'Topic :: System :: Systems Administration',
                         'Topic :: Software Development',
                         'Development Status :: 4 - Beta'])


if __name__ == '__main__':
    setup(**conf)
