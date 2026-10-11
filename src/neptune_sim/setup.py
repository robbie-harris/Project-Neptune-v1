from setuptools import setup
from glob import glob
from pathlib import Path
setup(name='neptune_sim', version='0.1.0', packages=['neptune_sim'], data_files=[("share/ament_index/resource_index/packages", ["resource/neptune_sim"]), ("share/neptune_sim", ["package.xml"])] + [("share/neptune_sim/launch", glob("launch/*.py"))] + [("share/neptune_sim/" + str(p.relative_to(Path('../../Simulation'))), [str(f) for f in p.iterdir() if f.is_file()]) for p in Path('../../Simulation').rglob('*') if p.is_dir()],
 install_requires=['setuptools'], zip_safe=True, description='Neptune prototype',
 license='GPL-3.0-only', entry_points={'console_scripts':['bridge = neptune_sim.bridge:main', 'rig_adapter = neptune_sim.rig_adapter:main', 'error_adapter = neptune_sim.error_adapter:main', 'operator_state = neptune_sim.operator_state:main']})
