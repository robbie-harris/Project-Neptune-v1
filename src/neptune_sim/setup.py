from setuptools import find_packages, setup

setup(
    name='neptune_sim',
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/neptune_sim']),
        ('share/neptune_sim', ['package.xml', 'README.md']),
        ('share/neptune_sim/assets/perception', [
            'assets/perception/flange.obj',
            'assets/perception/valve.obj',
        ]),
        ('share/neptune_sim/scenarios/benchmarks', [
            'scenarios/benchmarks/03_port_pipe_perception.scn',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='Configurable simulator sensor degradation for Project Neptune.',
    license='TODO: License declaration',
    extras_require={'test': ['pytest']},
    entry_points={'console_scripts': [
        'sensor_degrader = neptune_sim.sensor_degrader:main',
    ]},
)
