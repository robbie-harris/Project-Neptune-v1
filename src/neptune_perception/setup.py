from setuptools import setup
from glob import glob
from pathlib import Path
setup(name='neptune_perception', version='0.1.0', packages=['neptune_perception'], data_files=[("share/ament_index/resource_index/packages", ["resource/neptune_perception"]), ("share/neptune_perception", ["package.xml"])] + [("share/neptune_perception/config", ["../../config/detector.yaml"])],
 install_requires=['setuptools'], zip_safe=True, description='Neptune prototype',
 license='GPL-3.0-only', entry_points={'console_scripts':['pipe_detector = neptune_perception.detector:main']})
