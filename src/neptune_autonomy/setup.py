from setuptools import find_packages, setup

package_name = 'neptune_autonomy'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        (
            'share/' + package_name,
            ['package.xml'],
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Project Neptune',
    maintainer_email='neptune@example.com',
    description='Project Neptune autonomous mission executive',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mission_executive = '
            'neptune_autonomy.mission_executive:main',
        ],
    },
)
