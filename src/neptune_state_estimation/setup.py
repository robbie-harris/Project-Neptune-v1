from setuptools import find_packages, setup

package_name = 'neptune_state_estimation'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'ground_truth_state = neptune_state_estimation.ground_truth_state:main',
            'pressure_depth = neptune_state_estimation.pressure_depth:main',
            'hybrid_state = neptune_state_estimation.hybrid_state:main',
            'dead_reckoning_state = neptune_state_estimation.dead_reckoning_state:main',
        ],
    },
)
