from setuptools import find_packages, setup

setup(
    name='neptune_perception', version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/neptune_perception']),
        ('share/neptune_perception', ['package.xml']),
        ('share/neptune_perception/config', [
            'config/inspection_objects.yaml', 'config/orientation_a.yaml', 'config/pipe_fusion.yaml']),
        ('share/neptune_perception/launch', [
            'launch/inspection_objects.launch.py', 'launch/orientation_a.launch.py', 'launch/dual_models.launch.py']),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Project Neptune', maintainer_email='neptune@example.com',
    description='Observation-only Inspection Objects inference.', license='Apache-2.0',
    extras_require={'test': ['pytest']},
    entry_points={'console_scripts': [
        'inspection_objects = neptune_perception.detector:main',
        'orientation_a = neptune_perception.orientation_a:main',
        'pipe_fusion = neptune_perception.fusion_node:main',
    ]},
)
