from setuptools import setup, find_packages

setup(
    name='jupyterhub-idle-culler',
    version='0.1',
    packages=find_packages(),
    license='3-BSD',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    entry_points={
        'console_scripts': [
            'cull_idle_servers.py = jupyterhub_idle_culler:main',
            'jupyterhub-idle-culler = jupyterhub_idle_culler:main'
        ]
    },
    install_requires=[
        'tornado',
        'python-dateutil'
    ]
)