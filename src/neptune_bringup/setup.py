from setuptools import find_packages, setup

setup(
    name='neptune_bringup', version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/neptune_bringup']),
        ('share/neptune_bringup', ['package.xml']),
        ('share/neptune_bringup/launch', ['launch/perception_demo.launch.py']),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Project Neptune', maintainer_email='neptune@example.com',
    description='Neptune Demo V0 bringup and observational GUI.', license='MIT',
    extras_require={'test': ['pytest']},
    entry_points={'console_scripts': [
        'demo_readiness = neptune_bringup.demo_readiness:main',
        'demo_gui = neptune_bringup.demo_gui:main',
    ]},
)
